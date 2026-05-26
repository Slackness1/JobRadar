"""Opus 4.7 拍板: 从 6 个 bucket 的 XHS 抽取 + SAIF 就业报告, 合成最终 taxonomy。

输入:
- backend/data/xhs/raw/_pilot/{strategy}.jsonl  (6 个, 每行 DualSchemaExtract JSON)
- backend/data/saif_employment_reports_extracted.json  (2024/2025 流向 ground truth)

输出:
- docs/taxonomy-投研-final-v1.md      (最终 taxonomy 表 + 推理过程)
- backend/data/demo_companies_v1.json (10 家 demo 公司 + 推荐理由)

注意: 调 Anthropic API (Opus 4.7 1M context), 不走 OpenAI / DeepSeek。
预估开销 $1-2 一次 (取决于输入大小, 6 bucket × 200 帖 大概 200KB 文本)。
"""
from __future__ import annotations

import json
import os
import sys
from collections import Counter
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
PILOT_DIR = REPO_ROOT / "backend" / "data" / "xhs" / "raw" / "_pilot"
EMPLOYMENT_JSON = REPO_ROOT / "backend" / "data" / "saif_employment_reports_extracted.json"
TAXONOMY_OUT = REPO_ROOT / "docs" / "taxonomy-投研-final-v1.md"
DEMO_COMPANIES_OUT = REPO_ROOT / "backend" / "data" / "demo_companies_v1.json"

STRATEGIES = [
    "基本面权益",
    "卖方研究",
    "量化",
    "多资产_FOF_衍生品",
    "固定收益",
    "相关补充",
    "AI应用_PM_开发",  # 跨域: 给 P_self 用
]

# patch / 二次拉取的 jsonl 也加进来 (e.g. 卖方研究_tmt_patch.jsonl)
EXTRA_JSONL = [
    "卖方研究_tmt_patch",
]


def load_bucket(strategy: str, extra_paths: list[str] | None = None) -> list[dict]:
    """加载一个 bucket 的 jsonl + 可能的 patch 文件, 过滤噪声 (失败抽取 + 完全无关帖)。

    AI bucket 用更宽阈值 — DeepSeek 的 relevance scoring 是 投研-tuned, 把'AI 帖'打到 0.2;
    但 0.2 帖通常仍含 real sub_cat + company metadata (extractor 抽得到), 不该全扔。
    """
    paths = [PILOT_DIR / f"{strategy}.jsonl"]
    for extra in (extra_paths or []):
        if extra.startswith(strategy):  # 仅加同 strategy 的 patch
            paths.append(PILOT_DIR / f"{extra}.jsonl")
    # AI bucket 阈值降低
    rel_threshold = 0.15 if "AI" in strategy else 0.3
    records = []
    for path in paths:
        if not path.exists():
            continue
        with path.open(encoding="utf-8") as f:
            for line in f:
                try:
                    rec = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if rec.get("extraction_confidence", 0) <= 0:
                    continue  # 抽取失败
                # 跨阈值 OR 有 taxonomy / kb 内容 (DeepSeek 觉得低相关但仍抽到了东西)
                rel_ok = rec.get("relevance_score", 0) >= rel_threshold
                has_content = (
                    len((rec.get("taxonomy") or {}).get("discovered_sub_categories") or []) > 0
                    or len((rec.get("taxonomy") or {}).get("company_role_pairs") or []) > 0
                    or len((rec.get("kb") or {}).get("insights") or []) > 0
                )
                if rel_ok or has_content:
                    records.append(rec)
    return records


def summarize_bucket(strategy: str, records: list[dict]) -> dict:
    """每 bucket 算高频 sub_cat / company / dimension。"""
    sub_cats = Counter()
    companies = Counter()
    strategies_signal = Counter()
    industries = Counter()
    institutions = Counter()
    distinctions = []
    kb_insights = []

    for r in records:
        tax = r.get("taxonomy", {})
        for s in tax.get("strategy_signals", []):
            strategies_signal[s.get("canonical", "")] += 1
        for ind in tax.get("industry_signals", []):
            industries[ind.get("industry", "")] += 1
        for inst in tax.get("institution_signals", []):
            tier = inst.get("tier_guess", "")
            comp = inst.get("company_name", "")
            if tier:
                institutions[tier] += 1
            if comp:
                companies[comp] += 1
        for sub in tax.get("discovered_sub_categories", []):
            if sub:
                sub_cats[sub] += 1
        for cpair in tax.get("company_role_pairs", []):
            comp = cpair.get("company", "")
            if comp:
                companies[comp] += 1
        for dist in tax.get("dimension_distinctions", []):
            distinctions.append(dist)

        for ki in (r.get("kb") or {}).get("insights", []):
            if ki.get("verbatim_quote"):
                kb_insights.append({
                    "type": ki.get("type"),
                    "text": ki.get("text"),
                    "quote": ki.get("verbatim_quote"),
                    "post_url": r.get("url"),
                })

    return {
        "strategy": strategy,
        "post_count": len(records),
        "top_sub_cats": sub_cats.most_common(30),
        "top_companies": companies.most_common(30),
        "strategy_signals_canonical": strategies_signal.most_common(10),
        "industries": industries.most_common(20),
        "institutions": institutions.most_common(10),
        "dimension_distinctions_sample": distinctions[:30],
        "kb_insight_sample": kb_insights[:50],
    }


def load_employment_reports() -> dict:
    if not EMPLOYMENT_JSON.exists():
        return {}
    return json.loads(EMPLOYMENT_JSON.read_text(encoding="utf-8"))


def build_synthesis_prompt(bucket_summaries: list[dict], employment: dict, personas: list[dict] | None = None) -> str:
    """组 Opus prompt — 7 bucket 摘要 (6 投研 + 1 AI 应用) + 就业报告 + 5 persona 任务说明。"""
    lines = ["# 任务\n"]
    lines.append(
        "你是金融求职 + AI 求职 双域赛道分析专家。我给你 7 个 strategy 大类下用 DeepSeek 从小红书抽取的结构化数据 (6 个投研 + 1 个跨域 AI 应用/PM/开发) + SAIF MF 学院 2024-2025 真实就业流向 (投研侧 ground truth)。请合成最终 taxonomy 服务 5 个 persona 的端到端 demo:\n\n"
        "- P1 林思远: 清华本经济 + SAIF MF, 公募基本面行研 (消费 + 医药)\n"
        "- P2: 卖方 TMT, 中金/中信建投研究所路径\n"
        "- P3: 跨专业 (理工→金融), 私募基本面 (Quantamental 倾向)\n"
        "- P6: 头部量化私募 (九坤/明汯/灵均级), 数学+CS, sharpe>0.8 alpha factor\n"
        "- **P_self 周传博**: 跨域投研→AI 应用/PM, 帝国理工 DS+剑桥经济+利物浦金融数学, "
        "4 段 0-1 全栈 AI 项目 (JobCopilot 250+⭐+SAIF 合作 / StockRadar 100+⭐ / Lewoo RAG / AgentX), "
        "目标 AI 产品经理 OR AI 应用开发 实习, 想知道这两个方向自己 fit 度孰高 + 应该投哪些 AI 公司\n"
    )
    lines.append("\n## 你要输出的内容 (按 markdown 章节)\n")
    lines.append("""
### 1. 三维 Taxonomy

按 spec §4.1 的 3 dimension 输出, 含跨域 AI 大类:
- `strategy_type` (7 大类): 基本面权益 / 量化 / 固定收益 / 卖方研究 / 多资产_FOF_衍生品 / 相关补充 / AI应用_PM_开发
  - 每个大类下细分 2-6 个 sub_category (从 XHS 数据真出现 + 学生原话验证, 优先选 mention 数高的)
  - AI 大类细分至少要区分: AI PM vs AI 应用开发 (LLM/Agent 工程) vs 算法工程师 (传统 ML)
- `industry_focus`: 行业方向 (消费 / TMT / 医药 / 金融 / 周期 / AI 基础设施 / AI 应用层 / 等), 不锁词表
- `institution_tier`: 平台分层 (一线公募 / 二线公募 / 头部主观私募 / 量化大厂 / 卖方研究所 / 银行理财子 / 保险资管 / 券商资管 / 大厂 AI 部门 / 大模型独角兽 / Agent-应用层创业 / 出海 AI 公司)

每个细分写 1 行: `<canonical> · <sub_category> · <典型公司 3-5 家, 必须 XHS 数据真出现> · <学生原话标志词 / 区分点>`。

### 2. 给学生看的 "细颗粒度地图"

把 1 里的细分按 strategy 大类整理成树形, 给学生看哪条路径符合自己。每个细分挂 1-2 条 XHS 学生 verbatim quote 作为佐证 (必须带 post_url)。

### 3. Demo 选公司

**3a. 投研侧: 选 10 家公司, 覆盖至少 4 个投研 strategy 大类**, 满足:
- 在 XHS 数据 + 就业报告中均有 mention (双重 ground truth)
- 跨越 institution_tier
- 配 1 句话 demo pitch (为什么选它, 它能区分哪类 persona)

**3b. AI 侧 (给 P_self 用): 选 8-12 家公司**, 满足:
- 必须在 XHS AI bucket 数据中真出现 (mention 数排序), 不允许凭印象添加
- 跨越 institution_tier: 大厂 AI 部门 / 大模型独角兽 / Agent-应用层创业 / 出海 AI 公司 等都各覆盖 ≥1 家
- 每家配:
  - 主要招的角色 (AI PM / AI 应用开发 / 算法 / Agent / 等)
  - 1 句话 fit 度 pitch (为什么 P_self 这个背景 fit / 不 fit)
  - 估计入职门槛 (低/中/高)

### 4. P_self 专属决策建议 (2-3 段)

基于 AI bucket 数据 + P_self 简历 (附在下方), 直接回答:
- **AI PM vs AI 应用开发** P_self 哪个成功率更高? 给出 sub_cat 级粒度的判断 + 数据依据
- **平台优先级**: 大厂 AI / 大模型独角兽 / 创业 / 出海 — P_self 应该按什么顺序投? 为什么?
- **必须解决的 1-2 个简历差距**: P_self 没有大厂 AI 实习 tag, 项目都是个人/小团队, 你怎么建议补?

### 5. 区分力 sanity check

简短 1-2 段, 评估你给的 taxonomy 能否在以下 6 维都做出区分:
(a) P1 公募基本面 vs P6 量化私募 — strategy 主轴
(b) P1 公募 vs P3 私募 — institution_tier
(c) P1 买方 vs P2 卖方 — strategy 内部
(d) 跨专业 P3 (理工→金融) 友好度
(e) 隐藏亮点挖掘 (P1 deal size / P2 头部 broker / P6 sharpe ratio / P_self GitHub stars + SAIF 合作)
(f) **跨域 P_self (AI) vs P1-P6 (投研)** — 7 大类是否真把 AI 跟投研区分开?

---
""")

    lines.append("\n## 输入数据\n")

    # 6 bucket 摘要
    for b in bucket_summaries:
        lines.append(f"\n### Bucket: {b['strategy']} (帖数 {b['post_count']})\n")
        lines.append(f"- strategy_signals canonical 分布: {b['strategy_signals_canonical']}\n")
        lines.append(f"- top sub_cats: {b['top_sub_cats'][:20]}\n")
        lines.append(f"- top companies: {b['top_companies'][:20]}\n")
        lines.append(f"- industries: {b['industries']}\n")
        lines.append(f"- institution_tier 分布: {b['institutions']}\n")
        if b["dimension_distinctions_sample"]:
            lines.append(f"- 学生原话 X vs Y 对比 (前 10):\n")
            for d in b["dimension_distinctions_sample"][:10]:
                lines.append(f"  - axis={d.get('axis')!r} | {d.get('x_vs_y')} — {d.get('note')}\n")
        if b["kb_insight_sample"]:
            lines.append(f"- KB insight verbatim quotes 样例 (前 15, 你引用时务必带 post_url):\n")
            for ki in b["kb_insight_sample"][:15]:
                quote = (ki.get("quote") or "")[:200]
                lines.append(f"  - [{ki.get('type')}] {quote!r} ← {ki.get('post_url')}\n")

    # Persona 简历摘要
    if personas:
        lines.append("\n### Persona 简历摘要 (5 个)\n")
        for p in personas:
            lines.append(f"\n#### {p['id']}\n")
            lines.append(f"- target_jd_anchors: {p.get('target_jd_anchors')}\n")
            lines.append(f"- hidden_highlights: {p.get('hidden_highlights')}\n")
            avoid = (p.get('raw_json') or {}).get('avoid_emphasize') or {}
            if avoid:
                lines.append(f"- wants_to_emphasize: {avoid.get('wants_to_emphasize', '')}\n")
                lines.append(f"- wants_to_avoid: {avoid.get('wants_to_avoid', '')}\n")
            lines.append(f"- 简历前 3500 字:\n```\n{p.get('resume_text_excerpt', '')}\n```\n")

    # 就业报告 ground truth
    lines.append("\n### SAIF MF 就业流向 ground truth (2024 + 2025)\n")
    for year, recs in employment.items():
        if not recs:
            continue
        comp_counter = Counter(r.get("company", "") for r in recs)
        ind_counter = Counter(r.get("industry", "") for r in recs)
        role_counter = Counter(r.get("role_type", "") for r in recs)
        lines.append(f"\n**{year}** ({len(recs)} 条记录):\n")
        lines.append(f"- 公司 top: {comp_counter.most_common(15)}\n")
        lines.append(f"- 行业 top: {ind_counter.most_common(10)}\n")
        lines.append(f"- 角色 top: {role_counter.most_common(10)}\n")

    return "".join(lines)


def call_opus(prompt: str, max_tokens: int = 16000) -> str:
    """调 Anthropic Opus 4.7 (1M context)。需要 ANTHROPIC_API_KEY。"""
    import anthropic  # type: ignore
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("ERROR: 缺 ANTHROPIC_API_KEY", file=sys.stderr)
        sys.exit(2)
    client = anthropic.Anthropic(api_key=api_key)
    resp = client.messages.create(
        model="claude-opus-4-7",
        max_tokens=max_tokens,
        messages=[{"role": "user", "content": prompt}],
    )
    return resp.content[0].text


def main() -> int:
    bucket_summaries = []
    total_posts = 0
    for s in STRATEGIES:
        recs = load_bucket(s, extra_paths=EXTRA_JSONL)
        summary = summarize_bucket(s, recs)
        bucket_summaries.append(summary)
        total_posts += summary["post_count"]
        print(f"[{s}] 加载 {summary['post_count']} 帖, sub_cats={len(summary['top_sub_cats'])}, "
              f"companies={len(summary['top_companies'])}")

    if total_posts == 0:
        print("\n⚠ 没找到任何 bucket 数据。先跑 _pilot_single_bucket.py 抽取。", file=sys.stderr)
        return 1

    employment = load_employment_reports()
    print(f"\n就业报告: {sum(len(v) for v in employment.values())} 条记录")

    # 加载 5 个 persona, 给 Opus 看简历
    from app.services.taxonomy_discovery.persona_loader import load_persona, DEMO_IDS
    persona_ids = DEMO_IDS + ["P_self"]
    persona_blobs: list[dict] = []
    for pid in persona_ids:
        try:
            p = load_persona(pid)
            persona_blobs.append({
                "id": p.id,
                "resume_text_excerpt": p.resume_text[:3500],
                "hidden_highlights": p.hidden_highlights,
                "target_jd_anchors": p.target_jd_anchors,
                "persona_voice": p.persona_voice,
                "raw_json": p.raw_json,
            })
            print(f"[persona] {pid} loaded ({len(p.resume_text)} chars resume)")
        except FileNotFoundError as e:
            print(f"[persona] ⚠ {pid} missing: {e}")

    prompt = build_synthesis_prompt(bucket_summaries, employment, persona_blobs)
    print(f"\nOpus prompt 长度: {len(prompt)} 字 / {len(prompt) / 4:.0f} tokens 估算")
    print(f"准备调 Opus 4.7 (max_tokens=16000)...")

    if "--dry-run" in sys.argv:
        # 只输出 prompt 到文件预览, 不真调 API
        preview = REPO_ROOT / "docs" / "_opus_synth_prompt_preview.md"
        preview.write_text(prompt, encoding="utf-8")
        print(f"✓ Dry-run, prompt 保存到 {preview}")
        return 0

    output = call_opus(prompt)
    TAXONOMY_OUT.parent.mkdir(parents=True, exist_ok=True)
    TAXONOMY_OUT.write_text(output, encoding="utf-8")
    print(f"\n✓ Taxonomy 写到 {TAXONOMY_OUT}")
    print(f"  字数: {len(output)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
