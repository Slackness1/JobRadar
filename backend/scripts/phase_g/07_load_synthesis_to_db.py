"""T6 final: 读 data/_phase_g/synthesis/synth_*.json 全部 29 个 sub_cat 知识库 →
计算 DashScope text-embedding-v3 → upsert 到 knowledge_subcategories 表 + 写 md。

Embedding 输入: sub_cat + strategy_type + hard_requirements + soft_signals + interview_style
+ career_trajectory + verbatim_quotes (拼成一段 ~800-1500 字, 1024-dim 输出)

幂等: 按 sub_cat (unique) upsert, 重跑覆盖。
"""
from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

import app.config  # noqa: F401

from app.database import SessionLocal
from app.models import KnowledgeSubcategory
from app.services.podcasts.embed import embed_one, to_blob

BACKEND_ROOT = Path(__file__).resolve().parent.parent.parent
SYNTH_DIR = BACKEND_ROOT / "data" / "_phase_g" / "synthesis"
MD_DIR = BACKEND_ROOT.parent / "docs" / "sub_cat_knowledge"


def _build_embed_text(data: dict) -> str:
    parts = [
        f"赛道: {data.get('sub_cat')}",
        f"策略类型: {data.get('strategy_type')}",
        f"行业方向: {' / '.join(data.get('industry_focus_candidates') or [])}",
        f"机构层级: {' / '.join(data.get('institution_tier_candidates') or [])}",
        "硬门槛: " + " ".join(data.get("hard_requirements") or []),
        "加分项: " + " ".join(data.get("soft_signals") or []),
        f"面试样态: {data.get('interview_style') or ''}",
        f"职业路径: {data.get('career_trajectory') or ''}",
    ]
    quotes = data.get("verbatim_quotes") or []
    if quotes:
        parts.append("XHS 原文要点: " + " | ".join(q.get("quote", "") for q in quotes[:5]))
    return "\n".join(p for p in parts if p)


def _write_md(data: dict, md_path: Path) -> None:
    sc = data.get("sub_cat", "?")
    st = data.get("strategy_type", "?")
    conf = data.get("data_confidence", "?")
    basis = data.get("data_basis", {})
    lines = [
        f"# {sc} — 知识库",
        "",
        f"**策略类型**: {st}",
        f"**数据置信度**: {conf} "
        f"(post={basis.get('post_count', 0)}, "
        f"company_mention={basis.get('company_mention_count', 0)}, "
        f"saif_alumni={basis.get('saif_alumni_count', 0)})",
        f"**行业方向候选**: {' / '.join(data.get('industry_focus_candidates') or []) or '—'}",
        f"**机构层级候选**: {' / '.join(data.get('institution_tier_candidates') or []) or '—'}",
        "",
        "## 典型公司",
        "",
    ]
    for c in data.get("typical_companies") or []:
        must = " ⭐" if c.get("is_must_have") else ""
        saif = " (SAIF 校友流向)" if c.get("is_saif_alumni_dest") else ""
        lines.append(
            f"- **{c.get('name')}** — {c.get('tier')} "
            f"(XHS 提及 {c.get('xhs_mention_count', 0)} 次){saif}{must}"
        )
    lines.extend(["", "## 硬门槛", ""])
    for h in data.get("hard_requirements") or []:
        lines.append(f"- {h}")
    lines.extend(["", "## 加分项", ""])
    for s in data.get("soft_signals") or []:
        lines.append(f"- {s}")
    lines.extend(["", "## 转岗路径", ""])
    for t in data.get("transfer_paths") or []:
        lines.append(
            f"- **{t.get('from')} → {t.get('to')}** "
            f"(难度: {t.get('difficulty')}) — {t.get('notes')}"
        )
    if data.get("pitfalls"):
        lines.extend(["", "## 风险/排雷", ""])
        for p in data["pitfalls"]:
            lines.append(f"- {p}")
    lines.extend([
        "",
        "## 面试样态",
        "",
        data.get("interview_style") or "—",
        "",
        "## 薪酬信号",
        "",
        data.get("compensation_signal") or "—",
        "",
        "## 职业路径",
        "",
        data.get("career_trajectory") or "—",
        "",
        "## 招聘节奏",
        "",
    ])
    hs = data.get("hiring_season") or {}
    if hs:
        lines.append(f"- **春招**: {hs.get('spring') or '—'}")
        lines.append(f"- **秋招**: {hs.get('fall') or '—'}")
        peak = hs.get("peak_month") or []
        if peak:
            lines.append(f"- **高峰月**: {', '.join(str(m) for m in peak)}")
        if hs.get("verbatim"):
            lines.append(f"- **XHS 原话**: {hs['verbatim']}")
    lines.extend(["", "## XHS 原文锚点 (verbatim)", ""])
    for q in data.get("verbatim_quotes") or []:
        lines.append(f"> {q.get('quote')}")
        lines.append(
            f">\n> — [{q.get('context', '')}]({q.get('source_url', '')})"
        )
        lines.append("")
    md_path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    MD_DIR.mkdir(parents=True, exist_ok=True)
    files = sorted(SYNTH_DIR.glob("synth_*.json"))
    print(f"扫到 {len(files)} 个 synth JSON 文件 in {SYNTH_DIR}")

    if not files:
        print("(空) 先跑 T5/T6 subagent 生成 synth_*.json")
        return 1

    db = SessionLocal()
    try:
        existing_by_subcat = {
            r.sub_cat: r for r in db.query(KnowledgeSubcategory).all()
        }
        print(f"DB 已有 {len(existing_by_subcat)} 条 knowledge_subcategories")
        print()

        inserted = 0
        updated = 0
        skipped = 0
        embed_failed = []

        for f in files:
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
            except json.JSONDecodeError as e:
                print(f"  ⚠️  {f.name} JSON parse failed: {e}, skip")
                skipped += 1
                continue

            sc = data.get("sub_cat")
            slug = data.get("sub_cat_slug")
            strategy = data.get("strategy_type")
            if not (sc and slug and strategy):
                print(f"  ⚠️  {f.name} missing sub_cat/slug/strategy, skip")
                skipped += 1
                continue

            embed_text = _build_embed_text(data)
            try:
                vec = embed_one(embed_text)
                blob = to_blob(vec)
            except Exception as e:
                print(f"  ✗ {sc} embed fail: {e}, 入 DB 但 embedding=NULL")
                blob = None
                embed_failed.append(sc)

            basis = data.get("data_basis", {})
            row = existing_by_subcat.get(sc)
            if row:
                row.sub_cat_slug = slug
                row.strategy_type = strategy
                row.payload_json = json.dumps(data, ensure_ascii=False)
                row.data_confidence = data.get("data_confidence", "low")
                row.data_basis_json = json.dumps(basis, ensure_ascii=False)
                row.hiring_season_json = json.dumps(
                    data.get("hiring_season") or {}, ensure_ascii=False
                )
                if blob is not None:
                    row.embedding = blob
                row.updated_at = datetime.utcnow()
                updated += 1
                action = "↻"
            else:
                db.add(KnowledgeSubcategory(
                    sub_cat=sc,
                    sub_cat_slug=slug,
                    strategy_type=strategy,
                    payload_json=json.dumps(data, ensure_ascii=False),
                    data_confidence=data.get("data_confidence", "low"),
                    data_basis_json=json.dumps(basis, ensure_ascii=False),
                    hiring_season_json=json.dumps(
                        data.get("hiring_season") or {}, ensure_ascii=False
                    ),
                    embedding=blob,
                ))
                inserted += 1
                action = "+"

            md_path = MD_DIR / f"{slug}.md"
            _write_md(data, md_path)
            print(
                f"  {action} {sc} | conf={data.get('data_confidence')} | "
                f"posts={basis.get('post_count')} | embed={'ok' if blob else 'fail'}"
            )

        db.commit()
        print()
        print(f"=== T6 入库 summary ===")
        print(f"  新增: {inserted}")
        print(f"  更新: {updated}")
        print(f"  跳过: {skipped}")
        print(f"  embedding 失败: {len(embed_failed)} ({', '.join(embed_failed) or '—'})")
        print(f"  md 输出到: {MD_DIR}")

        # 最终全表统计
        total = db.query(KnowledgeSubcategory).count()
        with_embed = db.query(KnowledgeSubcategory).filter(
            KnowledgeSubcategory.embedding.isnot(None)
        ).count()
        print()
        print(f"DB 全表: {total} sub_cat (其中 {with_embed} 个带 embedding)")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
