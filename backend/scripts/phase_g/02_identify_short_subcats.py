"""Identify sub_cats below baseline (30 posts + 10 unique companies) and generate
targeted XHS queries to补足 to baseline.

Output: data/_phase_g/short_subcats_queries_v1.json

Data-shape note: Phase F XHS posts don't have a `content` or `title` field at top level.
Company extraction uses ast.literal_eval on the `taxonomy` field's institution_signals +
company_role_pairs (populated by Phase F classifier), NOT content scanning.

Baseline uses COMBINED (primary + secondary) post count, not primary-only.
"""
from __future__ import annotations
import ast
import json
import sys
from collections import defaultdict
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT / "backend"))

from app.services.phase_g.xhs_classifier import _SUB_CATS_27  # noqa: E402

CLASSIFIED_FILE = REPO_ROOT / "backend/data/_phase_g/xhs_classified_v1.jsonl"
OUTPUT_FILE = REPO_ROOT / "backend/data/_phase_g/short_subcats_queries_v1.json"

BASELINE_POSTS = 30        # combined >= 30 AND companies >= 10 → "OK"
BASELINE_COMPANIES = 10
RED_POSTS_THRESHOLD = 10  # combined < 10 → "RED SHORT" (must补爬)


def extract_mentioned_companies(post: dict) -> set[str]:
    """Extract company names from Phase F's pre-parsed taxonomy field.

    Reads taxonomy.institution_signals[].company_name and
    taxonomy.company_role_pairs[].company. Skips vague/placeholder names.

    taxonomy can be a dict (Phase F stored as dict) or a str repr (legacy).
    """
    raw = post.get("taxonomy")
    if not raw:
        return set()
    # Handle both dict (normal) and str repr (legacy fallback)
    if isinstance(raw, dict):
        tax = raw
    elif isinstance(raw, str):
        try:
            tax = ast.literal_eval(raw)
        except (SyntaxError, ValueError):
            return set()
        if not isinstance(tax, dict):
            return set()
    else:
        return set()

    _VAGUE = {"未指明", "未具名", "未披露", "不明", ""}

    def _is_real(name: str) -> bool:
        if not name:
            return False
        if name in _VAGUE:
            return False
        if "未指明" in name or "未具名" in name:
            return False
        # Skip generic descriptions like "上海市明星大模型初创企业"
        if len(name) > 15:
            return False
        return True

    out: set[str] = set()
    for sig in tax.get("institution_signals", []):
        if isinstance(sig, dict):
            name = (sig.get("company_name") or "").strip()
            if _is_real(name):
                out.add(name)
    for pair in tax.get("company_role_pairs", []):
        if isinstance(pair, dict):
            name = (pair.get("company") or "").strip()
            if _is_real(name):
                out.add(name)
    return out


def classify_distribution() -> dict[str, dict]:
    """Returns {sub_cat: {primary_count, secondary_count, combined_count, company_count, companies}}."""
    by_subcat: dict[str, dict] = defaultdict(
        lambda: {"primary_posts": [], "secondary_posts": [], "companies": set()}
    )
    for line in CLASSIFIED_FILE.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        post = json.loads(line)
        cls = post.get("classification", {})
        primary = cls.get("primary_sub_cat")
        secondary = cls.get("secondary_sub_cat")
        companies = extract_mentioned_companies(post)
        if primary:
            by_subcat[primary]["primary_posts"].append(post)
            by_subcat[primary]["companies"].update(companies)
        if secondary:
            by_subcat[secondary]["secondary_posts"].append(post)
            by_subcat[secondary]["companies"].update(companies)
    result = {}
    for sc, d in by_subcat.items():
        primary_count = len(d["primary_posts"])
        secondary_count = len(d["secondary_posts"])
        result[sc] = {
            "primary_count": primary_count,
            "secondary_count": secondary_count,
            "combined_count": primary_count + secondary_count,
            "company_count": len(d["companies"]),
            "companies": sorted(d["companies"]),
        }
    return result


# Hardcoded per-sub_cat seed query templates (used when XHS data sparse).
# Sub_cat name + 2-3 ground truth companies + 1 verbatim signal word per query.
_QUERY_TEMPLATES = {
    "PE投后VC行研": [
        "高瓴 PE 投后 实习", "弘毅资本 行研", "中投公司 二级市场",
        "淡马锡 上海 投资 实习", "PE 投后管理 学姐分享",
    ],
    "信用研究员": [
        "信用研究 城投 内卷", "光大永明 信用债 实习",
        "中再资产 信用研究员", "信用研究 转债 多资产", "公募固收 信用",
    ],
    "固收交易员": [
        "券商自营 固收交易", "平安 ficc 实习", "中信 ficc 交易员",
        "固收交易 银行间", "国债交易 卖方研究",
    ],
    "投行 IBD": [
        "三中一华 投行 IBD 实习", "中金投行 TMT", "中信投行 消费",
        "IBD 暑期实习", "保荐承做 投行",
    ],
    "结构化产品衍生品": [
        "中金衍生品 实习", "FCN 结构性产品", "期权策略 衍生品",
        "家办 衍生品", "越秀 结构化产品",
    ],
    "利率宏观策略": [
        "公募 利率 宏观策略", "保险资管 利率研究", "货币中介 利率",
        "宏观利率分析 实习", "公募 利率 大类资产",
    ],
    "财富管理FOF": [
        "信银理财 FOF", "平安 财富 FOF", "公募 财富线 FOF",
        "招商 财富 FOF 投后", "财富 FOF 客户服务",
    ],
    "多模态推理优化": [
        "字节 多模态 推理优化", "投机采样 Speculative", "商汤 多模态大模型",
        "华为 推理优化 实习", "腾讯 多模态 算法",
    ],
}


def generate_queries_for_short_subcats(dist: dict[str, dict]) -> dict[str, list[str]]:
    """For sub_cats that need补爬, generate targeted XHS queries.

    补爬 trigger (either condition):
      1. combined < RED_POSTS_THRESHOLD (10) → "red SHORT" — truly sparse, must补爬
      2. combined < BASELINE_POSTS (30) AND company_count < BASELINE_COMPANIES (10)
         → 黄 sub_cat with insufficient company coverage

    Sub_cats with combined >= 10 AND company_count >= 10 (even if combined < 30)
    are "yellow" — enough for T4 synthesis; not补爬 in this pass.
    """
    out: dict[str, list[str]] = {}
    for sc in _SUB_CATS_27:
        info = dist.get(sc, {"combined_count": 0, "company_count": 0})
        combined = info.get("combined_count", 0)
        companies = info.get("company_count", 0)
        is_red = combined < RED_POSTS_THRESHOLD
        is_yellow_low_company = (combined < BASELINE_POSTS) and (companies < BASELINE_COMPANIES)
        if is_red or is_yellow_low_company:
            queries = _QUERY_TEMPLATES.get(sc, [])
            if not queries:
                # Fallback: 5 generic queries based on sub_cat name
                queries = [
                    f"{sc} 实习",
                    f"{sc} 招聘",
                    f"{sc} 学姐分享",
                    f"{sc} 应届生",
                    f"{sc} 求职",
                ]
            out[sc] = queries
    return out


def main():
    if not CLASSIFIED_FILE.exists():
        print(f"ERROR: classified file not found: {CLASSIFIED_FILE}")
        sys.exit(1)

    dist = classify_distribution()
    print(
        f"Distribution across {len(_SUB_CATS_27)} sub_cats "
        f"(OK: combined>={BASELINE_POSTS} + companies>={BASELINE_COMPANIES}; "
        f"RED SHORT: combined<{RED_POSTS_THRESHOLD}):"
    )
    ok_count = 0
    red_count = 0
    yellow_count = 0
    for sc in _SUB_CATS_27:
        info = dist.get(sc, {"primary_count": 0, "secondary_count": 0, "combined_count": 0, "company_count": 0})
        combined = info.get("combined_count", 0)
        companies = info.get("company_count", 0)
        primary = info.get("primary_count", 0)
        secondary = info.get("secondary_count", 0)
        is_ok = combined >= BASELINE_POSTS and companies >= BASELINE_COMPANIES
        is_red = combined < RED_POSTS_THRESHOLD
        if is_ok:
            status = "OK   "
            ok_count += 1
        elif is_red:
            status = "RED  "
            red_count += 1
        else:
            status = "黄   "
            yellow_count += 1
        print(
            f"  [{status}] {sc:<22} primary={primary:3d} secondary={secondary:2d} "
            f"combined={combined:3d} companies={companies:3d}"
        )

    print(f"\nSummary: {ok_count} OK, {yellow_count} 黄, {red_count} RED SHORT")

    short = generate_queries_for_short_subcats(dist)
    print(f"\n{len(short)} sub_cats will补爬:")
    for sc, queries in short.items():
        print(f"  {sc}: {len(queries)} queries")

    # Build output with combined field in distribution for clarity
    distribution_out = {}
    for sc in _SUB_CATS_27:
        info = dist.get(sc, {"primary_count": 0, "secondary_count": 0, "combined_count": 0, "company_count": 0, "companies": []})
        distribution_out[sc] = {
            "primary_count": info.get("primary_count", 0),
            "secondary_count": info.get("secondary_count", 0),
            "combined_count": info.get("combined_count", 0),
            "company_count": info.get("company_count", 0),
        }

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_FILE.write_text(
        json.dumps(
            {
                "baseline": {"posts": BASELINE_POSTS, "companies": BASELINE_COMPANIES},
                "distribution": distribution_out,
                "queries_to_run": short,
            },
            indent=2,
            ensure_ascii=False,
        )
    )
    print(f"\nOutput: {OUTPUT_FILE}")

    # Sanity check
    if ok_count != 4:
        print(f"\nWARNING: expected 4 OK sub_cats, got {ok_count} — verify distribution!")
    queries_count = len(short)
    if queries_count < 9 or queries_count > 12:
        print(
            f"\nWARNING: expected 9-10 sub_cats in queries_to_run (9 red + maybe 1-2 yellow with low companies), "
            f"got {queries_count} — verify!"
        )


if __name__ == "__main__":
    main()
