"""T7 — Audit: 拿 119 家 ground_truth 公司去匹配 32k 真实岗位库, 出 gap 报告。

判定逻辑:
1. 标准化公司名 (去括号 / 去公司后缀 / 去地理前缀)
2. 全字匹配 → alias 表辅助 (字节/抖音, 高盛/Goldman 等) → 双向 substring (≥3 字)
3. 每个 ground_truth 公司算 matched_job_count
4. 按 sub_cat 聚合 + must_have 命中率

输出:
- gap report md 到 docs/phase_g_audit/ground_truth_coverage_2026-05-28.md
- jsonl 详细数据到 data/_phase_g/audit_2026-05-28.jsonl (给 T8 补爬挑 target 用)
"""
from __future__ import annotations

import json
import re
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

import app.config  # noqa: F401

from app.database import SessionLocal
from app.models import Job

BACKEND_ROOT = Path(__file__).resolve().parent.parent.parent
GROUND_TRUTH = BACKEND_ROOT / "data" / "ground_truth_companies_v1.json"
AUDIT_JSONL = BACKEND_ROOT / "data" / "_phase_g" / f"audit_{datetime.now():%Y-%m-%d}.jsonl"
REPORT_MD = BACKEND_ROOT.parent / "docs" / "phase_g_audit" / f"ground_truth_coverage_{datetime.now():%Y-%m-%d}.md"


# 常见 alias / 简称 → 正式公司名候选 (双向, 用于匹配 ground_truth vs jobs.company)
ALIAS_MAP: dict[str, list[str]] = {
    "字节跳动": ["抖音", "字节", "北京抖音"],
    "腾讯": ["腾讯科技", "腾讯计算机"],
    "阿里巴巴": ["阿里", "淘宝", "天猫", "蚂蚁", "阿里云"],
    "美团": ["三快", "美团点评"],
    "百度": ["百度在线", "百度网讯"],
    "京东": ["京东方", "京东集团"],  # 注意京东方是另一家
    "蚂蚁集团": ["蚂蚁科技", "蚂蚁金服", "Ant"],
    "高盛": ["Goldman", "Goldman Sachs"],
    "Goldman Sachs": ["高盛"],
    "摩根士丹利": ["Morgan Stanley", "大摩"],
    "Morgan Stanley": ["摩根士丹利", "大摩"],
    "摩根大通": ["JPMorgan", "JP Morgan", "JPM", "小摩"],
    "JPMorgan": ["摩根大通", "小摩"],
    "瑞银": ["UBS"],
    "UBS": ["瑞银"],
    "汇丰": ["HSBC"],
    "HSBC": ["汇丰"],
    "DeepSeek": ["深度求索"],
    "深度求索": ["DeepSeek"],
    "Anthropic": ["Claude"],
    "Kimi": ["月之暗面", "Moonshot"],
    "月之暗面": ["Kimi", "Moonshot"],
    "智谱": ["智谱AI", "智谱清言", "Zhipu"],
    "MiniMax": ["稀宇科技"],
    "稀宇科技": ["MiniMax"],
    "中信证券": ["中信证券股份"],
    "中金公司": ["中国国际金融", "CICC", "中金"],
    "华泰证券": ["华泰联合"],
    "招商银行": ["招行"],
    "工商银行": ["工行", "ICBC"],
    "建设银行": ["建行", "CCB"],
    "易方达基金": ["易方达"],
    "华夏基金": ["华夏"],
    "南方基金": ["南方"],
    "广发基金": ["广发"],
    "嘉实基金": ["嘉实"],
    "招商基金": ["招商"],
    "汇添富基金": ["汇添富"],
    "工银瑞信基金": ["工银瑞信"],
    "兴证全球基金": ["兴证全球", "兴全"],
    "招商证券": ["招商"],
    "申万宏源": ["申万", "宏源"],
    "国泰海通": ["国泰君安", "海通证券"],
    "九坤投资": ["九坤"],
    "明汯投资": ["明汯"],
    "幻方量化": ["幻方"],
    "鸣石基金": ["鸣石"],
    "灵均投资": ["灵均"],
    "衍复投资": ["衍复"],
    "宽德投资": ["宽德"],
    "Citadel": ["城堡", "Citadel Securities"],
    "Two Sigma": ["TwoSigma"],
    "Jane Street": ["JaneStreet"],
    "Optiver": ["Optiver Asia"],
    "中信保诚基金": ["中信保诚"],
    "信银理财": ["中信银行理财"],
    "招银理财": ["招商银行理财"],
    "中欧基金": ["中欧"],
    "鸣石基金": ["鸣石投资", "鸣石"],
    "鸣石投资": ["鸣石基金", "鸣石"],
    "商汤科技": ["商汤智能", "商汤"],
    "红杉中国": ["红杉资本", "红杉"],
    "高瓴资本": ["高瓴投资", "高瓴"],
    "贝莱德": ["BlackRock", "贝莱德基金"],
    "BlackRock": ["贝莱德"],
    "联合资信": ["联合信用评级", "联合资信评估"],
    "大公国际": ["大公国际资信"],
    "平安资产管理": ["平安资产", "平安资管"],
    "华创证券": ["华创"],  # 注意可能误命中 北方华创 — 但 ground_truth 里没"北方华创"
    "工银瑞信基金": ["工银瑞信"],
    "华泰联合证券": ["华泰联合"],
    "国寿投资": ["国寿", "中国人寿"],
    "中再资产": ["中再"],
}


_NORMALIZE_RE = re.compile(r"[\s　（）()\[\]【】《》<>\-_·,，.。&\|/\\\\]+")
# 只剥纯公司形态后缀, 保留行业词 (证券/基金/银行/科技 等), 避免 招商基金/招商证券/招商银行 互相吃
_CORP_SUFFIX_RE = re.compile(
    r"(?:股份有限公司|有限责任公司|有限公司|股份公司|股份|集团|控股|公司|"
    r"子公司|分公司|总行|总公司|分行|分部|事业部)+$"
)
# 地理前缀 (放在公司名最前) — 仅在 normalize 时去掉
_GEO_PREFIX_RE = re.compile(
    r"^(?:北京市|上海市|深圳市|广州市|杭州市|海南省|北京|上海|深圳|广州|杭州|"
    r"天津|重庆|成都|南京|苏州|武汉|西安|海南|河北|河南|山东|福建|浙江)+"
)


def _normalize(name: str) -> str:
    """剥公司形态后缀 + 地理前缀, 保留行业词 (证券/基金/银行)。"""
    if not name:
        return ""
    s = name.strip().lower()
    s = _NORMALIZE_RE.sub("", s)
    # 反复剥后缀 (多个嵌套)
    for _ in range(3):
        new = _CORP_SUFFIX_RE.sub("", s)
        if new == s:
            break
        s = new
    s = _GEO_PREFIX_RE.sub("", s)
    return s


def _build_match_index(jobs_companies: dict[str, int]) -> dict[str, list[str]]:
    """job company name → list of normalized forms (for alias lookup)."""
    out: dict[str, list[str]] = {}
    for jc in jobs_companies:
        n = _normalize(jc)
        if n:
            out.setdefault(n, []).append(jc)
    return out


def _aliases_for(name: str) -> list[str]:
    """Return name + all alias variants (with self), normalized."""
    aliases = {name}
    aliases.update(ALIAS_MAP.get(name, []))
    return [_normalize(a) for a in aliases if a]


def _match_jobs(gt_name: str, normalized_index: dict[str, list[str]],
                jobs_companies: dict[str, int]) -> tuple[list[str], int]:
    """Return (matched_company_names, total_job_count)."""
    matches: set[str] = set()
    aliases = _aliases_for(gt_name)

    for alias in aliases:
        if not alias:
            continue
        # 1. 全字匹配
        if alias in normalized_index:
            for raw_co in normalized_index[alias]:
                matches.add(raw_co)
        # 2. 双向 substring (≥ 2 字 for Chinese — 红杉/高瓴/九坤/明汯 等 2 字品牌)
        if len(alias) >= 2:
            for norm_jc, raw_list in normalized_index.items():
                if alias in norm_jc or (len(norm_jc) >= 3 and norm_jc in alias):
                    for raw_co in raw_list:
                        matches.add(raw_co)

    total = sum(jobs_companies[c] for c in matches)
    return sorted(matches), total


def main() -> int:
    AUDIT_JSONL.parent.mkdir(parents=True, exist_ok=True)
    REPORT_MD.parent.mkdir(parents=True, exist_ok=True)

    gt = json.loads(GROUND_TRUTH.read_text(encoding="utf-8"))
    db = SessionLocal()
    try:
        from sqlalchemy import func
        # alive 或 link_status NULL → 进推荐池
        jobs_companies: dict[str, int] = dict(
            db.query(Job.company, func.count())
            .filter((Job.link_status == "alive") | (Job.link_status.is_(None)))
            .group_by(Job.company)
            .all()
        )
        jobs_companies.pop("", None)
        # 全表 (含 dead) → 区分"全新爬"vs"刷活旧 source"
        jobs_companies_all: dict[str, int] = dict(
            db.query(Job.company, func.count()).group_by(Job.company).all()
        )
        jobs_companies_all.pop("", None)
        total_jobs = sum(jobs_companies.values())
        normalized_index = _build_match_index(jobs_companies)
        normalized_index_all = _build_match_index(jobs_companies_all)
        print(f"jobs alive 总: {total_jobs} 帖, 来自 {len(jobs_companies)} 家不同公司名")
        print(f"全表 (含 dead): {sum(jobs_companies_all.values())} 帖, {len(jobs_companies_all)} 公司名")
        print()

        per_sub_cat_summary: list[dict] = []
        gap_lines: list[str] = []
        all_audits: list[dict] = []

        for sub_cat, companies in gt["ground_truth"].items():
            covered = 0
            must_total = 0
            must_covered = 0
            sc_jobs = 0
            company_audits = []
            for co in companies:
                name = co["name"]
                matched, count = _match_jobs(name, normalized_index, jobs_companies)
                matched_all, count_all = _match_jobs(name, normalized_index_all, jobs_companies_all)
                # dead-only: 库内有但全死, T8 可考虑刷活旧 source
                dead_only = count == 0 and count_all > 0
                is_must = bool(co.get("must_have"))
                if is_must:
                    must_total += 1
                if count > 0:
                    covered += 1
                    if is_must:
                        must_covered += 1
                    sc_jobs += count
                company_audits.append({
                    "name": name,
                    "tier": co.get("tier"),
                    "must_have": is_must,
                    "source": co.get("source") or [],
                    "matched_companies": matched,
                    "job_count": count,
                    "job_count_including_dead": count_all,
                    "dead_only": dead_only,
                })
                all_audits.append({
                    "sub_cat": sub_cat,
                    "name": name,
                    "tier": co.get("tier"),
                    "must_have": is_must,
                    "matched_companies": matched,
                    "job_count": count,
                    "job_count_including_dead": count_all,
                    "dead_only": dead_only,
                })
            per_sub_cat_summary.append({
                "sub_cat": sub_cat,
                "company_total": len(companies),
                "company_covered": covered,
                "must_have_total": must_total,
                "must_have_covered": must_covered,
                "sc_job_count": sc_jobs,
                "companies": company_audits,
            })

        # write jsonl (per company line, easy diff)
        with AUDIT_JSONL.open("w", encoding="utf-8") as f:
            for row in all_audits:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
        print(f"已写 {len(all_audits)} 行 audit 到 {AUDIT_JSONL}")

        # build md report
        per_sub_cat_summary.sort(
            key=lambda x: (x["must_have_total"] - x["must_have_covered"]),
            reverse=True,
        )

        md_lines: list[str] = [
            f"# Ground Truth × 岗位库 覆盖率 Audit (T7) — {datetime.now():%Y-%m-%d}",
            "",
            "**生成方式**: `scripts/phase_g/08_audit_ground_truth_vs_jobs.py`",
            "",
            "**输入**:",
            f"- ground_truth_companies_v1.json — {sum(len(v) for v in gt['ground_truth'].values())} 条 (29 sub_cat × 119 公司, 含别名展开)",
            f"- jobs 表 alive 帖 — {total_jobs} 帖来自 {len(jobs_companies)} 家公司",
            "",
            "**匹配逻辑**: 公司名归一 (去括号/后缀/标点) + alias 表 (字节↔抖音, 高盛↔Goldman 等) + 双向 substring (≥3 字)。",
            "",
            "## 整体盘子",
            "",
        ]
        total_co_rows = sum(s["company_total"] for s in per_sub_cat_summary)
        total_co_cov = sum(s["company_covered"] for s in per_sub_cat_summary)
        total_must = sum(s["must_have_total"] for s in per_sub_cat_summary)
        total_must_cov = sum(s["must_have_covered"] for s in per_sub_cat_summary)
        md_lines.extend([
            f"- 全部 ground_truth 公司行: {total_co_rows}, 命中 ≥1 岗位的: **{total_co_cov} ({total_co_cov / total_co_rows:.0%})**",
            f"- must_have 行: {total_must}, 命中 ≥1 岗位的: **{total_must_cov} ({total_must_cov / total_must:.0%})**",
            f"- 缺口 (must_have 未命中): **{total_must - total_must_cov} 行** — T8 补爬目标",
            "",
            "## per sub_cat (按缺口数倒序, 缺口大的在前)",
            "",
            "| sub_cat | 公司命中率 | must_have 命中率 | 缺口数 | 命中岗位帖数 |",
            "|---|---|---|---|---|",
        ])
        for s in per_sub_cat_summary:
            cov_pct = f"{s['company_covered']}/{s['company_total']} ({s['company_covered'] / s['company_total']:.0%})" if s['company_total'] else "—"
            must_pct = f"{s['must_have_covered']}/{s['must_have_total']} ({s['must_have_covered'] / s['must_have_total']:.0%})" if s['must_have_total'] else "—"
            gap = s['must_have_total'] - s['must_have_covered']
            md_lines.append(
                f"| {s['sub_cat']} | {cov_pct} | {must_pct} | **{gap}** | {s['sc_job_count']:,} |"
            )

        md_lines.extend(["", "## 缺口明细 — T8 补爬候选 (must_have=true 且 job_count=0)", ""])
        md_lines.append("> 🩺 = 库内有岗位但全 link_status=dead, T8 可考虑刷活旧 source 而非全新爬。")
        md_lines.append("")
        gap_companies_per_sc: dict[str, list[tuple[str, bool, int]]] = defaultdict(list)
        for s in per_sub_cat_summary:
            for ca in s["companies"]:
                if ca["must_have"] and ca["job_count"] == 0:
                    gap_companies_per_sc[s["sub_cat"]].append(
                        (ca["name"], ca["dead_only"], ca["job_count_including_dead"])
                    )
        for sc, entries in gap_companies_per_sc.items():
            md_lines.append(f"### {sc} ({len(entries)} 缺)")
            md_lines.append("")
            for name, dead_only, all_count in entries:
                if dead_only:
                    md_lines.append(f"- 🩺 {name} (库内 {all_count} 帖全 dead)")
                else:
                    md_lines.append(f"- {name}")
            md_lines.append("")

        md_lines.extend(["", "## per sub_cat 详细 (每家公司命中情况)", ""])
        for s in per_sub_cat_summary:
            md_lines.append(f"### {s['sub_cat']}")
            md_lines.append("")
            md_lines.append("| 公司 | tier | must_have | 命中库内名 | 帖数 |")
            md_lines.append("|---|---|---|---|---|")
            for ca in sorted(s["companies"], key=lambda c: (-c["job_count"], not c["must_have"], c["name"])):
                must_mark = "⭐" if ca["must_have"] else ""
                matched = ", ".join(ca["matched_companies"][:3])
                if len(ca["matched_companies"]) > 3:
                    matched += f", +{len(ca['matched_companies']) - 3}"
                if not matched:
                    matched = "(无命中)"
                md_lines.append(
                    f"| {ca['name']} | {ca.get('tier') or '—'} | {must_mark} | {matched} | {ca['job_count']:,} |"
                )
            md_lines.append("")

        REPORT_MD.write_text("\n".join(md_lines), encoding="utf-8")
        print(f"已写 md 报告到 {REPORT_MD}")
        print()
        print(f"=== T7 audit summary ===")
        print(f"  ground_truth 公司行: {total_co_rows}")
        print(f"  命中 ≥1 岗位行: {total_co_cov} ({total_co_cov / total_co_rows:.0%})")
        print(f"  must_have 命中: {total_must_cov}/{total_must} ({total_must_cov / total_must:.0%})")
        print(f"  缺口 (must_have 未命中): {total_must - total_must_cov} 行")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
