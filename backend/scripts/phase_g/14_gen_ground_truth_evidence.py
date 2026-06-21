"""T13 / review 辅助 — 把 ground_truth_companies_v1.json 119 公司每条的"证据来源"
(XHS 原帖) 全部 dump 成 md, 给学院老师审"我们认定这家公司是 must_have 凭啥"。

Source 标签 (saif:YYYY / xhs:sub_cat:N / demo_v1 / taxonomy_doc / common_knowledge:理由)
里 XHS 类的 reverse-lookup taxonomy_xhs_posts 表:
  company_mentions JSON array contains 公司名 (或 brand prefix 剥后缀后) → 取
  (source_url, raw_content[:600], verbatim_signals[:3]) 当证据展示

输出: docs/phase_g_audit/ground_truth_evidence_YYYY-MM-DD.md
"""
from __future__ import annotations

import json
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

import app.config  # noqa: F401

from app.database import SessionLocal
from app.models import TaxonomyXhsPost

BACKEND_ROOT = Path(__file__).resolve().parent.parent.parent
GROUND_TRUTH = BACKEND_ROOT / "data" / "ground_truth_companies_v1.json"
SAIF_REPORT = BACKEND_ROOT / "data" / "saif_employment_reports_extracted.json"
OUTPUT_DIR = BACKEND_ROOT.parent / "docs" / "phase_g_audit"

# 跟 T18 company_fallback._verbatim_for_company 同款 brand prefix 提取规则
_CORP_SUFFIXES = ("基金", "证券", "银行", "信托", "保险", "资管", "投资", "资产管理")


def _brand_prefix(name: str) -> str:
    if not name:
        return ""
    s = name.strip()
    for suf in _CORP_SUFFIXES:
        if s.endswith(suf) and len(s) > len(suf):
            s = s[: -len(suf)]
            break
    return s


def _xhs_evidence_for_company(name: str) -> list[dict]:
    """从 taxonomy_xhs_posts 拉所有 company_mentions 含本公司名的帖。"""
    candidates = {name}
    brand = _brand_prefix(name)
    if brand and brand != name and len(brand) >= 2:
        candidates.add(brand)
    db = SessionLocal()
    try:
        out: list[dict] = []
        seen_urls: set[str] = set()
        # 简化: 加载全表, in-memory JSON contains 判定 (taxonomy_xhs_posts ~800 行, 可接受)
        rows = db.query(TaxonomyXhsPost).all()
        for r in rows:
            if r.source_url in seen_urls:
                continue
            try:
                mentions = json.loads(r.company_mentions or "[]")
            except json.JSONDecodeError:
                continue
            hit = False
            for m in mentions:
                if not isinstance(m, str):
                    continue
                for c in candidates:
                    if c == m or (len(c) >= 2 and c in m):
                        hit = True
                        break
                if hit:
                    break
            if not hit:
                continue
            try:
                verb = json.loads(r.verbatim_signals or "[]")
            except json.JSONDecodeError:
                verb = []
            out.append({
                "sub_cat": r.sub_cat,
                "source_url": r.source_url,
                "raw_content": (r.raw_content or "")[:600],
                "verbatim_signals": verb[:3],
                "company_mentions": mentions[:6],
                "relevance_score": r.relevance_score or 0,
            })
            seen_urls.add(r.source_url)
        out.sort(key=lambda x: (-x["relevance_score"], x["sub_cat"]))
        return out
    finally:
        db.close()


def _saif_evidence_for_company(name: str) -> list[dict]:
    """从 saif_employment_reports_extracted.json 拉本公司的 SAIF 校友流向证据。"""
    if not SAIF_REPORT.exists():
        return []
    try:
        saif = json.loads(SAIF_REPORT.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []
    brand = _brand_prefix(name)
    candidates = {name, brand} if brand and brand != name else {name}
    out: list[dict] = []
    for year, records in saif.items():
        if not isinstance(records, list):
            continue
        for r in records:
            co = r.get("company") or ""
            for c in candidates:
                if c and (c == co or (len(c) >= 2 and c in co)):
                    out.append({
                        "year": year,
                        "company_in_saif": co,
                        "role_type": r.get("role_type"),
                        "count": r.get("count"),
                        "industry": r.get("industry"),
                    })
                    break
    return out


def main() -> int:
    if not GROUND_TRUTH.exists():
        print("ground_truth_companies_v1.json 不存在")
        return 1
    gt = json.loads(GROUND_TRUTH.read_text(encoding="utf-8"))

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    out_file = OUTPUT_DIR / f"ground_truth_evidence_{datetime.now():%Y-%m-%d}.md"

    # 跨 sub_cat 同公司去重 → 单家公司一节, 列出它跨多 sub_cat 的全部证据
    company_payload: dict[str, dict] = {}
    for sub_cat, lst in gt.get("ground_truth", {}).items():
        for c in lst:
            name = c.get("name") or ""
            if not name:
                continue
            entry = company_payload.setdefault(name, {
                "name": name,
                "tier": c.get("tier"),
                "must_have_in": [],
                "non_must_in": [],
                "source": set(),
                "industry_focus": set(),
                "notes": [],
            })
            sub_cat_marker = sub_cat
            if c.get("must_have"):
                entry["must_have_in"].append(sub_cat_marker)
            else:
                entry["non_must_in"].append(sub_cat_marker)
            for s in c.get("source") or []:
                entry["source"].add(s)
            for ind in c.get("industry_focus") or []:
                entry["industry_focus"].add(ind)
            if c.get("notes"):
                entry["notes"].append(f"[{sub_cat}] {c['notes']}")

    companies = sorted(
        company_payload.values(),
        key=lambda e: (-len(e["must_have_in"]), -len(e["non_must_in"]), e["name"]),
    )

    lines: list[str] = [
        f"# Phase G — Ground Truth 119 公司 × 全部证据 dump",
        "",
        f"**生成日期**: {datetime.now():%Y-%m-%d}",
        f"**总公司数**: {len(companies)} (去重)",
        f"**总 ground_truth 行**: {sum(len(v) for v in gt.get('ground_truth', {}).values())} (公司 × sub_cat 笛卡尔)",
        "",
        "**用途**: 学院老师审 ground truth 来源, 验 must_have 标记是否有真实数据支撑。",
        "",
        "**Source 标签解释**:",
        "- `saif:YYYY` — 来自 SAIF MF 年度就业报告 (YYYY 年, 该公司在校友流向里出现)",
        "- `xhs:sub_cat:N` — 来自 N 个 XHS 经验帖在该 sub_cat 池里提到此公司",
        "- `demo_v1` — 来自 Phase F demo 评测固定下来的 5 persona 推荐池",
        "- `taxonomy_doc` — 来自 27/29 canonical sub_cat 设计文档的「典型机构」列表",
        "- `common_knowledge:理由` — 来自 LLM 行业常识 (e.g. 高瓴是头部 PE 是公知事实, 但无具体 XHS 帖)",
        "",
        "---",
        "",
        "## 速查索引 (按 must_have 数 + sub_cat 数排序)",
        "",
        "| # | 公司 | tier | must_have sub_cat 数 | 总 sub_cat 数 | 证据来源 |",
        "|---|---|---|---|---|---|",
    ]
    for i, e in enumerate(companies, 1):
        n_must = len(e["must_have_in"])
        n_total = n_must + len(e["non_must_in"])
        srcs = "; ".join(sorted(e["source"]))[:80]
        lines.append(
            f"| {i} | {e['name']} | {e['tier'] or '?'} | {n_must} | {n_total} | {srcs} |"
        )

    lines.extend(["", "---", "", "## 每家公司详细证据", ""])

    for i, e in enumerate(companies, 1):
        name = e["name"]
        lines.append(f"### {i}. {name}")
        lines.append("")
        lines.append(f"- **tier**: {e['tier'] or '?'}")
        lines.append(
            f"- **must_have in**: {', '.join(e['must_have_in']) or '—'} ({len(e['must_have_in'])} sub_cat)"
        )
        lines.append(
            f"- **非 must_have (备选) in**: {', '.join(e['non_must_in']) or '—'} ({len(e['non_must_in'])})"
        )
        lines.append(f"- **industry_focus**: {', '.join(sorted(e['industry_focus'])) or '—'}")
        lines.append(f"- **source 标签**: {', '.join(sorted(e['source']))}")
        if e["notes"]:
            lines.append("- **notes**:")
            for n in e["notes"]:
                lines.append(f"  - {n}")
        lines.append("")

        # SAIF 证据
        saif = _saif_evidence_for_company(name)
        if saif:
            lines.append(f"#### SAIF 校友流向证据 ({len(saif)} 条)")
            lines.append("")
            lines.append("| year | SAIF 表内公司名 | role_type | count | industry |")
            lines.append("|---|---|---|---|---|")
            for s in saif[:8]:
                lines.append(
                    f"| {s['year']} | {s['company_in_saif']} | {s.get('role_type') or '?'} "
                    f"| {s.get('count') or '?'} | {s.get('industry') or '?'} |"
                )
            if len(saif) > 8:
                lines.append(f"| ... | (+{len(saif) - 8} 条) | | | |")
            lines.append("")

        # XHS 证据
        xhs_ev = _xhs_evidence_for_company(name)
        if xhs_ev:
            lines.append(f"#### XHS 帖证据 ({len(xhs_ev)} 条)")
            lines.append("")
            for ev in xhs_ev[:6]:  # 限 6 条避免单公司过长
                lines.append(
                    f"**[{ev['sub_cat']}]** (relevance={ev['relevance_score']:.2f}) "
                    f"— [{ev['source_url'][:60]}]({ev['source_url']})"
                )
                lines.append("")
                lines.append(
                    f"> 帖内提到的公司: {', '.join(ev['company_mentions'])}"
                )
                lines.append("")
                lines.append("> **内容快照**:")
                lines.append("> ")
                content = ev["raw_content"] or "(无)"
                for ln in content.split("\n"):
                    lines.append(f"> {ln}")
                lines.append("")
                if ev["verbatim_signals"]:
                    lines.append("> **verbatim 锚点 (T1/T3 抽取)**:")
                    for v in ev["verbatim_signals"]:
                        lines.append(f"> - {v}")
                    lines.append("")
            if len(xhs_ev) > 6:
                lines.append(f"_(+{len(xhs_ev) - 6} 条更多帖未展示, 同 sub_cat)_")
                lines.append("")
        else:
            lines.append("#### XHS 帖证据")
            lines.append("")
            lines.append("(taxonomy_xhs_posts 表内未找到提及此公司的帖 — source 应该来自 saif / demo_v1 / taxonomy_doc / common_knowledge)")
            lines.append("")

        lines.append("---")
        lines.append("")

    out_file.write_text("\n".join(lines), encoding="utf-8")
    print(f"已写 {len(companies)} 家公司证据 dump 到 {out_file}")
    print(f"  文件大小: {out_file.stat().st_size / 1024:.1f} KB")
    return 0


if __name__ == "__main__":
    sys.exit(main())
