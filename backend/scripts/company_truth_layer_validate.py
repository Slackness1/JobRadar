#!/usr/bin/env python3
"""
Company Truth Layer 校验脚本

对比 CSV 真值层与 DB 实际爬取结果，输出覆盖率报告。
用法: python backend/scripts/company_truth_layer_validate.py
"""

import csv
import sqlite3
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

# ── 路径配置 ──────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DB_PATH = PROJECT_ROOT / "backend" / "data" / "jobradar.db"
CSV_PATH = Path(
    "/home/ubuntu/.openclaw/workspace-projecta/data/exports/all_xiaozhao_export.csv"
)
REPORT_DIR = PROJECT_ROOT / "backend" / "data" / "validation_reports"


# ── 数据加载 ──────────────────────────────────────────────
def load_csv(path: Path) -> list[dict]:
    """加载 CSV 真值层"""
    with open(path, encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def load_db_companies(db_path: Path) -> dict[str, dict]:
    """从 DB 加载公司 → {job_count, sources}"""
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute(
        """
        SELECT company, COUNT(*) as cnt, GROUP_CONCAT(DISTINCT source) as sources
        FROM jobs
        GROUP BY company
        """
    )
    result = {}
    for row in cur.fetchall():
        result[row[0]] = {"job_count": row[1], "sources": row[2] or ""}
    conn.close()
    return result


# ── 匹配逻辑 ──────────────────────────────────────────────
def match_companies(
    csv_companies: set[str], db_companies: set[str]
) -> tuple[dict, list, list, list]:
    """
    宽松匹配：精确优先，然后双向包含。
    返回 (matched_pairs, csv_unmatched, db_unmatched, fuzzy_pairs)
    """
    matched = {}  # csv_name -> db_name
    fuzzy_pairs = []  # [(csv_name, db_name)]
    remaining_csv = set(csv_companies)
    remaining_db = set(db_companies)

    # 第一轮：精确匹配
    exact_matches = remaining_csv & remaining_db
    for c in exact_matches:
        matched[c] = c
    remaining_csv -= exact_matches
    remaining_db -= exact_matches

    # 第二轮：宽松匹配（双向包含）
    # 先按名字长度降序排列，避免短名字误匹配
    sorted_remaining_csv = sorted(remaining_csv, key=len, reverse=True)
    for csv_c in sorted_remaining_csv:
        if csv_c not in remaining_csv:
            continue
        # 找 DB 中包含该名字的，或该名字包含 DB 名字的
        candidates = []
        for db_c in list(remaining_db):
            if csv_c in db_c or db_c in csv_c:
                # 避免单字误匹配：要求较短名字至少2个字符
                shorter = min(csv_c, db_c, key=len)
                if len(shorter) >= 2:
                    candidates.append(db_c)

        if candidates:
            # 选择最相似的（长度差最小）
            best = min(candidates, key=lambda x: abs(len(x) - len(csv_c)))
            matched[csv_c] = best
            fuzzy_pairs.append((csv_c, best))
            remaining_csv.discard(csv_c)
            remaining_db.discard(best)

    return matched, sorted(remaining_csv), sorted(remaining_db), fuzzy_pairs


# ── 链接平台检测 ──────────────────────────────────────────
def detect_link_platform(url: str) -> str:
    """检测投递链接所属平台"""
    if not url:
        return "无链接"
    url_lower = url.lower()
    if "mokahr.com" in url_lower or "moka.com" in url_lower:
        return "Moka"
    if "workday" in url_lower or "wd5." in url_lower:
        return "Workday"
    if "zhiye.com" in url_lower:
        return "智业"
    if "51job" in url_lower:
        return "51job"
    if "zhaopin" in url_lower:
        return "智联"
    if "zhipin" in url_lower or "boss" in url_lower:
        return "BOSS直聘"
    if "hotjob" in url_lower:
        return "HotJob"
    if "mp.weixin.qq.com" in url_lower:
        return "微信公众号"
    if "liepin" in url_lower:
        return "猎聘"
    if "linkedin" in url_lower:
        return "LinkedIn"
    return "其他"


# ── 报告生成 ──────────────────────────────────────────────
def generate_report(
    csv_rows: list[dict],
    db_companies: dict[str, dict],
    matched: dict,
    csv_unmatched: list,
    db_unmatched: list,
    fuzzy_pairs: list,
):
    """生成并打印校验报告"""
    lines: list[str] = []

    def p(s=""):
        lines.append(s)

    # ── 1. 总览 ──
    csv_company_set = set(r["公司"].strip() for r in csv_rows)
    p("=" * 70)
    p("  Company Truth Layer 校验报告")
    p(f"  生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    p("=" * 70)
    p()
    p("【总览】")
    p(f"  CSV 真值层:  {len(csv_company_set):>5} 家公司, {len(csv_rows):>5} 条记录")
    p(f"  DB 爬取结果: {len(db_companies):>5} 家公司")
    p(f"  ─────────────────────────────")
    p(f"  精确匹配:    {len(matched) - len(fuzzy_pairs):>5} 家")
    p(f"  模糊匹配:    {len(fuzzy_pairs):>5} 家")
    p(f"  匹配总计:    {len(matched):>5} 家")
    p(f"  CSV 未覆盖:  {len(csv_unmatched):>5} 家 (真值层有，DB 没有)")
    p(f"  DB 多余:     {len(db_unmatched):>5} 家 (DB 有，真值层没有)")
    p(
        f"  覆盖率:      {len(matched)/len(csv_company_set)*100:.1f}%"
    )
    p()

    # ── 2. 行业覆盖率 ──
    # 构建公司→行业映射
    company_industry = {}
    for r in csv_rows:
        c = r["公司"].strip()
        ind = r["公司行业"].strip()
        if c not in company_industry:
            company_industry[c] = ind

    industry_stats = defaultdict(lambda: {"total": 0, "covered": 0, "companies_not_in_db": []})
    for c in csv_company_set:
        ind = company_industry.get(c, "未知")
        industry_stats[ind]["total"] += 1
        if c in matched:
            industry_stats[ind]["covered"] += 1
        else:
            industry_stats[ind]["companies_not_in_db"].append(c)

    p("【行业覆盖率】")
    p(f"  {'行业':<20} {'总数':>5} {'已覆盖':>6} {'覆盖率':>7}")
    p(f"  {'─'*20} {'─'*5} {'─'*6} {'─'*7}")
    for ind, stats in sorted(
        industry_stats.items(), key=lambda x: x[1]["total"], reverse=True
    ):
        rate = stats["covered"] / stats["total"] * 100 if stats["total"] else 0
        p(f"  {ind:<20} {stats['total']:>5} {stats['covered']:>6} {rate:>6.1f}%")
    p()

    # ── 3. 未覆盖公司清单（按行业分组，附链接平台） ──
    p("【未覆盖公司清单 — CSV 有但 DB 没有】")
    p(f"  共 {len(csv_unmatched)} 家，按行业分组:")
    p()

    # 构建公司→链接信息
    company_links = {}
    company_positions = {}
    for r in csv_rows:
        c = r["公司"].strip()
        if c not in company_links:
            company_links[c] = r.get("投递链接", "").strip()
            company_positions[c] = r.get("岗位", "").strip()[:60]

    for ind in sorted(industry_stats.keys()):
        not_covered = industry_stats[ind]["companies_not_in_db"]
        if not not_covered:
            continue
        p(f"  ── {ind} ({len(not_covered)} 家) ──")
        for c in sorted(not_covered):
            link = company_links.get(c, "")
            platform = detect_link_platform(link)
            p(f"    {c:<30} [{platform}]")
        p()

    # ── 4. 未覆盖公司的链接平台分析 ──
    p("【未覆盖公司 — 链接平台分布】")
    platform_counts = defaultdict(int)
    platform_companies = defaultdict(list)
    for c in csv_unmatched:
        link = company_links.get(c, "")
        platform = detect_link_platform(link)
        platform_counts[platform] += 1
        platform_companies[platform].append(c)

    for plat in sorted(platform_counts.keys(), key=lambda x: platform_counts[x], reverse=True):
        cnt = platform_counts[plat]
        p(f"  {plat:<15} {cnt:>4} 家")
        # 可爬取建议
        if plat in ("Moka", "Workday", "智业", "HotJob"):
            p(f"    ↳ 建议: 已有 adapter，可直接爬取")
        elif plat in ("51job", "BOSS直聘", "智联", "猎聘"):
            p(f"    ↳ 建议: 公开招聘平台，可通过 API/页面抓取")
        elif plat == "微信公众号":
            p(f"    ↳ 建议: 需要微信环境或手动投递，不适合自动爬取")
        elif plat == "其他":
            p(f"    ↳ 建议: 自建招聘站，需逐站分析")
        else:
            p(f"    ↳ 建议: 无链接，需人工确认")
    p()

    # ── 5. 可爬取候选（非微信链接的未覆盖公司） ──
    p("【可爬取候选 — 非微信链接的未覆盖公司】")
    crawlable = []
    for c in csv_unmatched:
        link = company_links.get(c, "")
        platform = detect_link_platform(link)
        if platform != "微信公众号" and platform != "无链接":
            crawlable.append((c, platform, link))
    p(f"  共 {len(crawlable)} 家公司有直接招聘站链接，适合作为爬虫种子:")
    p()
    for c, plat, link in sorted(crawlable, key=lambda x: x[1]):
        p(f"  [{plat:<10}] {c:<30} {link[:80]}")
    p()

    # ── 6. 模糊匹配复核 ──
    if fuzzy_pairs:
        p("【模糊匹配复核 — 请人工确认以下匹配是否正确】")
        for csv_c, db_c in fuzzy_pairs:
            p(f"  CSV: '{csv_c}' <-> DB: '{db_c}'")
        p()

    # ── 7. DB 多余公司（DB 有但 CSV 没有） ──
    p(f"【DB 多余公司 — DB 有但 CSV 没有 ({len(db_unmatched)} 家)】")
    p("  (这些公司可能是非26届秋招来源，正常现象)")
    p()
    for c in sorted(db_unmatched)[:50]:
        info = db_companies[c]
        p(f"    {c:<30} ({info['job_count']} 岗位, 来源: {info['sources']})")
    if len(db_unmatched) > 50:
        p(f"    ... 还有 {len(db_unmatched) - 50} 家未显示")
    p()

    # ── 打印并保存 ──
    report_text = "\n".join(lines)
    print(report_text)

    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    report_file = REPORT_DIR / f"validation_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
    report_file.write_text(report_text, encoding="utf-8")
    print(f"\n报告已保存到: {report_file}")


# ── 主流程 ────────────────────────────────────────────────
def main():
    if not CSV_PATH.exists():
        print(f"错误: CSV 文件不存在: {CSV_PATH}", file=sys.stderr)
        sys.exit(1)
    if not DB_PATH.exists():
        print(f"错误: DB 文件不存在: {DB_PATH}", file=sys.stderr)
        sys.exit(1)

    print("加载数据...")
    csv_rows = load_csv(CSV_PATH)
    db_companies = load_db_companies(DB_PATH)

    csv_company_set = set(r["公司"].strip() for r in csv_rows)
    db_company_set = set(db_companies.keys())

    print(f"  CSV: {len(csv_company_set)} 家公司")
    print(f"  DB:  {len(db_company_set)} 家公司")
    print("执行匹配...")
    matched, csv_unmatched, db_unmatched, fuzzy_pairs = match_companies(
        csv_company_set, db_company_set
    )
    print(f"  匹配: {len(matched)}, CSV未覆盖: {len(csv_unmatched)}, DB多余: {len(db_unmatched)}")
    print()

    generate_report(
        csv_rows, db_companies, matched, csv_unmatched, db_unmatched, fuzzy_pairs
    )


if __name__ == "__main__":
    main()
