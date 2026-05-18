"""SAIF 投研 简历推荐 离线测试 harness。

目标:
  - 用 LLM 生成 N 份多样化的 SAIF 投研学生模拟简历
  - 用 preferences = {tracks:['投研'], locations:['上海'], company_types:['金融机构']}
  - 跑 recommend_jobs_for_profile,看 top-10
  - 分类每个推荐:
      * 投研伞子集    (canonical ∈ {二级买方·基本面, 卖方研究·S&T, 一级市场, 量化})
      * 可迁移        (canonical ∈ transferable)
      * NULL+title 命中 (NULL but 严格 alias 在 title 里)
      * ambiguous     (1:N source, NULL)
      * 红线           (is_low_quality_role 命中)
      * 错位           (canonical 不在伞/可迁移,且 NULL 无 alias)
      * 不可投递       (无 detail_url)
  - 输出 hit rate / bad cases / 公司平台分布

用法:
  PYTHONPATH=. .venv/bin/python scripts/offline_test_saif_touyan.py [--n N] [--rerank/--no-rerank]
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.database import SessionLocal
from app.schemas_resume_copilot import (
    ResumeEducationItem,
    ResumeInternshipItem,
    ResumePreferencePayload,
    ResumeProfilePayload,
    ResumeProjectItem,
    ResumeSkillsPayload,
)
from app.services.resume_copilot.recommendation import (
    _classify_track_match,
    recommend_jobs_for_profile,
)
from app.services.taxonomy import (
    expand_track_to_canonicals,
    is_low_quality_role,
    transferable_for,
)
from tests.eval.clients import LLMClient, build_simulator_client


SAIF_BACKGROUND_HINTS = [
    "清华经管金融硕士,GPA 3.8/4.0,曾在中金 IBD / 高瓴 PE / 中信证券研究所 等顶级买卖方机构实习",
    "复旦经济学院金融硕士,GPA 3.7,有易方达基金行研助理 + 中信建投宏观研究的实习",
    "上海交大 SAIF 金融硕士,有招商证券机械军工组研究助理 + 兴证全球基金行研实习",
    "北大光华金融硕士,CFA Level III,实习: 国泰君安固收研究 + 嘉实基金权益投资部",
    "上海高金 SAIF 金融硕士,在中金研究所 + 摩根斯坦利 IBD 实习,擅长财务建模 (DCF / LBO / Comps)",
    "复旦数学硕士转金融,在九坤投资 + 明汯投资 量化研究实习,Python / SQL / 因子挖掘强",
    "北大经济金融双学位,在中信建投 IBD + 弘毅投资 PE 实习,精通行业研究 + 估值",
    "上海交大金融工程,实习: 国信证券固收研究 + 银华基金固收投资,CFA Level II",
    "清华五道口金融学院,在中投 + 国寿资管 实习,做过宏观 + 多资产研究",
    "复旦数学统计双学位,在 Jane Street + 灵均投资 实习,擅长策略研究 + Python",
    "复旦经济学硕士,实习: 中信证券TMT行研 + 高毅资产权益研究,长期跟踪互联网 / 半导体",
    "上海财大金融硕士,在国寿资管 + 平安资管 实习,固收 / 信用研究方向",
    "清华统计硕士,实习: 中信证券衍生品自营 + 华泰研究所 总量研究 (策略 + 衍生品)",
]


GENERATION_SCHEMA = {
    "type": "object",
    "properties": {
        "candidate_summary": {"type": "string"},
        "education": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "school": {"type": "string"},
                    "degree": {"type": "string"},
                    "major": {"type": "string"},
                    "start_date": {"type": "string"},
                    "end_date": {"type": "string"},
                    "highlights": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["school", "degree", "major"],
            },
        },
        "internships": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "company": {"type": "string"},
                    "role": {"type": "string"},
                    "start_date": {"type": "string"},
                    "end_date": {"type": "string"},
                    "bullets": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["company", "role", "bullets"],
            },
        },
        "projects": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "role": {"type": "string"},
                    "tech_stack": {"type": "array", "items": {"type": "string"}},
                    "bullets": {"type": "array", "items": {"type": "string"}},
                },
            },
        },
        "skills": {
            "type": "object",
            "properties": {
                "technical": {"type": "array", "items": {"type": "string"}},
                "tools": {"type": "array", "items": {"type": "string"}},
                "languages": {"type": "array", "items": {"type": "string"}},
            },
        },
        "languages": {"type": "array", "items": {"type": "string"}},
        "awards": {"type": "array", "items": {"type": "string"}},
        "inferred_roles": {"type": "array", "items": {"type": "string"}},
        "inferred_tracks": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["candidate_summary", "education", "internships", "inferred_tracks"],
}


SYSTEM_PROMPT = (
    "你是 SAIF (上海高金) 投研方向硕士生模拟简历生成器。"
    "请基于给定 background hint 生成一份**真实可信、多样化**的中文简历 JSON,要点:\n"
    "- 学校用真实的: 清华 / 北大 / 复旦 / 上交 / SAIF / 高金 / 五道口 / 上财 / 中财 / 人大等\n"
    "- 实习公司用真实的: 中金 / 中信 / 中信建投 / 国君 / 海通 / 华泰 / 招商 / 兴业 / 国信 / 中泰 等券商;"
    "  易方达 / 广发 / 富国 / 兴证全球 / 中欧 / 嘉实 / 招商 / 银华 等公募;高毅 / 景林 / 重阳 / 千合 等私募;"
    "  九坤 / 明汯 / 幻方 / 灵均 等量化;高瓴 / 红杉 / CDH / 弘毅 等 PE;GS / MS / JPM / UBS 等外资行\n"
    "- bullets 用 STAR / quant 量化表达,例如 \"覆盖 5 只跟踪股票,撰写 8 篇深度报告,1 篇被分析师采纳推送内部投委会\"\n"
    "- inferred_roles 写 ['投研实习生', '行业研究员', '量化研究员'] 这类,inferred_tracks 写 ['投研'] 或 ['行业研究'] 或 ['量化']\n"
    "- 输出严格符合给定 JSON schema,不要添加额外字段,不要 markdown 代码块包裹"
)


def generate_profile(
    client: LLMClient,
    hint: str,
    *,
    temperature: float = 0.85,
) -> ResumeProfilePayload:
    """调 LLM 生成一份模拟简历。"""
    raw = client.chat(
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": (
                    f"Background hint: {hint}\n\n"
                    "请生成一份完整简历,**严格** JSON 格式。\n"
                    f"Schema: {json.dumps(GENERATION_SCHEMA, ensure_ascii=False)}"
                ),
            },
        ],
        temperature=temperature,
        response_format={"type": "json_object"},
    )
    data = json.loads(raw)
    # Coerce into pydantic
    return ResumeProfilePayload(
        basic_info={"name": "测试同学", "email": "test@saif.edu.cn"},
        candidate_summary=data.get("candidate_summary", ""),
        education=[ResumeEducationItem(**e) for e in (data.get("education") or [])],
        internships=[ResumeInternshipItem(**i) for i in (data.get("internships") or [])],
        projects=[ResumeProjectItem(**p) for p in (data.get("projects") or [])],
        skills=ResumeSkillsPayload(**(data.get("skills") or {})),
        languages=data.get("languages") or [],
        awards=data.get("awards") or [],
        inferred_roles=data.get("inferred_roles") or [],
        inferred_tracks=data.get("inferred_tracks") or [],
    )


def classify_recommendation(item, preferences: ResumePreferencePayload) -> tuple[str, str]:
    """每个推荐分到一类 + 详细 label。

    返 (bucket, detail):
      bucket ∈ {'subset', 'transferable', 'ambiguous', 'low_quality',
                'mismatch', 'unreachable', 'unclassified'}
    """
    if not item.detail_url:
        return ('unreachable', 'no detail_url')
    if is_low_quality_role(item.job_title or ''):
        return ('low_quality', is_low_quality_role(item.job_title or '') or '')

    expanded = set()
    transferable = set()
    for pref in preferences.preferred_tracks:
        expanded.update(expand_track_to_canonicals(pref))
        transferable.update(transferable_for(pref))

    # 用 _classify_track_match 重用同一套逻辑 (需要 Job-like obj)
    class _Stub:
        pass
    stub = _Stub()
    stub.canonical_track = None  # 推荐 item 不存 canonical, 但 risks 里有 marker
    stub.job_title = item.job_title or ''
    stub.source = ''

    # 直接看 risks 标签 — recommendation.py 已经分好了
    risks = list(item.risks or [])
    if any('可迁移' in r for r in risks):
        return ('transferable', '可迁移角标')
    if any('信号不足' in r for r in risks):
        return ('ambiguous', 'ambiguous source')
    if any('赛道不符' in r for r in risks):
        return ('mismatch', '错位')

    # 没 mismatch 标签 → 说明 _classify_track_match 给的是 hit / null_hit
    return ('subset', 'hit/null_hit')


def run_one(
    db,
    profile: ResumeProfilePayload,
    preferences: ResumePreferencePayload,
    *,
    use_rerank: bool,
    top_n: int = 10,
) -> dict:
    items, _, _ = recommend_jobs_for_profile(
        db,
        profile,
        preferences=preferences,
        limit=top_n,
        ai_top_n=5 if use_rerank else 0,
    )
    breakdown = Counter()
    rows = []
    for it in items:
        bucket, detail = classify_recommendation(it, preferences)
        breakdown[bucket] += 1
        rows.append({
            "bucket": bucket,
            "detail": detail,
            "company": it.company,
            "title": it.job_title,
            "location": it.location,
            "final_score": it.final_score,
            "matched_track_label": it.matched_track_label,
        })
    return {"breakdown": dict(breakdown), "rows": rows}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--n", type=int, default=5, help="number of mock profiles to generate")
    parser.add_argument("--rerank", action="store_true", help="use LLM rerank (slower, more accurate)")
    parser.add_argument("--out", type=str, default="data/offline_test_results.json")
    parser.add_argument("--load-from", type=str, default="", help="reuse profiles from a prior run")
    args = parser.parse_args()

    client = build_simulator_client()
    preferences = ResumePreferencePayload(
        preferred_tracks=['投研'],
        preferred_locations=['上海'],
        preferred_company_types=['金融机构'],
        preferred_roles=['投研实习生'],
        all_skipped=False,
    )

    if args.load_from:
        loaded = json.loads(Path(args.load_from).read_text("utf-8"))
        profiles = [ResumeProfilePayload(**p) for p in loaded["profiles"]]
    else:
        profiles: list[ResumeProfilePayload] = []
        for i in range(args.n):
            hint = SAIF_BACKGROUND_HINTS[i % len(SAIF_BACKGROUND_HINTS)]
            print(f"[{i + 1}/{args.n}] generating profile from hint: {hint[:50]}...")
            try:
                p = generate_profile(client, hint)
                profiles.append(p)
            except Exception as exc:
                print(f"  ERROR: {exc!r} — skipping")

    db = SessionLocal()
    try:
        all_results = []
        agg = Counter()
        for i, profile in enumerate(profiles):
            print(f"[{i + 1}/{len(profiles)}] recommending (rerank={args.rerank})...")
            try:
                r = run_one(db, profile, preferences, use_rerank=args.rerank)
            except Exception as exc:
                print(f"  ERROR: {exc!r}")
                continue
            all_results.append({"hint": SAIF_BACKGROUND_HINTS[i % len(SAIF_BACKGROUND_HINTS)], **r})
            for k, v in r["breakdown"].items():
                agg[k] += v
    finally:
        db.close()

    # Report
    print("\n=== aggregate ===")
    total = sum(agg.values()) or 1
    for k in ('subset', 'transferable', 'ambiguous', 'low_quality', 'mismatch', 'unreachable'):
        v = agg.get(k, 0)
        print(f"  {k:13} {v:4} ({100*v/total:.1f}%)")
    hit = agg.get('subset', 0) + agg.get('transferable', 0)
    bad = agg.get('low_quality', 0) + agg.get('mismatch', 0) + agg.get('unreachable', 0)
    print(f"\n  HIT (subset + transferable): {100*hit/total:.1f}%")
    print(f"  BAD (low_quality + mismatch + unreachable): {100*bad/total:.1f}%")

    out = {
        "preferences": preferences.model_dump(),
        "use_rerank": args.rerank,
        "n_profiles": len(profiles),
        "aggregate": dict(agg),
        "profiles": [p.model_dump() for p in profiles],
        "results": all_results,
    }
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(out, ensure_ascii=False, indent=2), "utf-8")
    print(f"\nfull report → {out_path}")

    # Print a few bad cases to make iteration easy
    print("\n=== bad cases (top 10 per profile) ===")
    for i, r in enumerate(all_results):
        bads = [row for row in r["rows"] if row["bucket"] in ('mismatch', 'low_quality', 'unreachable')]
        if bads:
            print(f"\n--- profile {i + 1} ---")
            for b in bads[:5]:
                print(f"  [{b['bucket']:11}] {b['company'][:18]:18} | {b['title'][:35]:35} | final={b['final_score']}")


if __name__ == "__main__":
    main()
