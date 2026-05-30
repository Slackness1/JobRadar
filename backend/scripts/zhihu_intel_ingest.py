"""知乎同辈情报 MVP 入库 — TikHub fetch_article_search_v3 → XhsNote/XhsInsight。

让工作台"同辈情报"抽屉(IntelDrawer, 读 XhsInsight by company_target + 向量检索)
重新有真数据。小红书情报库 2026-05-26 被删空, 这是 API 重新入库的第一条管道。

MVP 策略 (不跑 LLM 抽取, 先把真帖入库):
  每家目标公司 × 2 query (面经 / 实习) → TikHub 知乎搜 → 取 search_result 真帖
  → 去 HTML → 整篇(裁 1800 字)作一条 insight, company_target=[公司], 向量化入库。
  幂等: note_id / insight_id 命中即跳过。预算: --max-searches 上限 + 单价 $0.01/搜。

跑法 (cwd=backend):
    PYTHONPATH=. .venv/bin/python scripts/zhihu_intel_ingest.py --max-searches 60
    # 只看会搜哪些不入库: 加 --dry-run
"""
from __future__ import annotations

import argparse
import hashlib
import html
import json
import os
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.chdir(str(Path(__file__).resolve().parent.parent))

import requests  # noqa: E402

GT_PATH = Path("data/ground_truth_companies_v1.json")
TIKHUB_ZHIHU = "https://api.tikhub.io/api/v1/zhihu/web/fetch_article_search_v3"
TIKHUB_COST = 0.01
QUERIES = ["面经", "实习"]      # 每家 2 query
MAX_POSTS_PER_QUERY = 5
MIN_VOTEUP = 5
MIN_CONTENT_CHARS = 120

# A1 相关性启发: 帖正文(或标题)必须出现 ≥1 个金融招聘 keyword, 否则丢弃。
# 防止 "易方达前端开发" / "金融鄙视链" 这类擦边帖被打到公司情报上。
FINANCE_KW = re.compile(
    r"投行|投研|研究员|分析师|校招|秋招|春招|暑期|实习|面试|面经|笔试|"
    r"IBD|PE|VC|FOF|量化|quant|公募|私募|券商|资管|信用|固收|宏观|"
    r"销售交易|S&T|FICC|衍生品|内推|offer|薪资|待遇",
    re.IGNORECASE,
)


def _load_env() -> None:
    p = Path(".env.local")
    if not p.exists():
        return
    for line in p.read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if s and not s.startswith("#") and "=" in s:
            k, v = s.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def _strip_html(s: str) -> str:
    return html.unescape(re.sub(r"<[^>]+>", "", s or "")).strip()


def _target_companies() -> list[str]:
    """全 ground_truth 的 must_have 头部公司, 跨所有 sub_cat 去重。"""
    gt = json.loads(GT_PATH.read_text(encoding="utf-8"))["ground_truth"]
    out: list[str] = []
    seen: set[str] = set()
    for sc, companies in gt.items():
        for c in companies:
            name = (c.get("name") or "").strip()
            if c.get("must_have") and name and name not in seen:
                seen.add(name)
                out.append(name)
    return out


_COMPANY_SUFFIX = re.compile(
    r"(基金|证券|资管|集团|公司|银行|国际|管理|股份|有限|投资|信托|期货|保险)$"
)


def _company_stem(name: str) -> str:
    """去公司常见后缀, 让 '华夏基金' 也接受 '华夏的实习面经'。"""
    stem = _COMPANY_SUFFIX.sub("", name or "")
    return stem if len(stem) >= 2 else name


def _is_finance_relevant(title: str, content: str, company: str) -> bool:
    """启发式相关性: (a) 帖里出现公司名或其 stem  (b) 帖里出现金融招聘 keyword。
    防 '易方达前端开发' / '金融鄙视链' / 'XX 公司股票分析' 这类擦边帖被打到情报库。
    """
    text = (title or "") + " " + (content or "")
    stem = _company_stem(company)
    if company and (company not in text) and (stem not in text):
        return False
    return bool(FINANCE_KW.search(text))


def _zhihu_search(keyword: str, key: str, retries: int = 2) -> list[dict]:
    """TikHub 知乎搜索, 对 400(请求失败请重试)/429/5xx 自动重试。"""
    last_err: Exception | None = None
    for attempt in range(retries + 1):
        try:
            r = requests.get(
                TIKHUB_ZHIHU, params={"keyword": keyword},
                headers={"Authorization": f"Bearer {key}"}, timeout=45,
            )
            if r.status_code == 200:
                break
            if r.status_code in (400, 429, 500, 502, 503, 504) and attempt < retries:
                time.sleep(1.5 ** attempt)
                continue
            r.raise_for_status()
            break
        except requests.RequestException as e:
            last_err = e
            if attempt < retries:
                time.sleep(1.5 ** attempt)
                continue
            raise
    items = (r.json().get("data") or {}).get("data") or []
    posts = []
    for it in items:
        if it.get("type") != "search_result":
            continue
        o = it.get("object") or {}
        content = _strip_html(o.get("content") or o.get("excerpt") or "")
        title = _strip_html(o.get("title") or (o.get("question") or {}).get("name") or "")
        if len(content) < MIN_CONTENT_CHARS:
            continue
        posts.append({
            "kind": o.get("type") or "",
            "title": title,
            "content": content,
            "voteup": int(o.get("voteup_count") or o.get("vote_count") or 0),
            "comment": int(o.get("comment_count") or 0),
            "url": str(o.get("url") or ""),
            "author": str(((o.get("author") or {}).get("name")) or ""),
        })
    posts.sort(key=lambda p: -p["voteup"])
    return posts


def _conf(voteup: int) -> str:
    return "high" if voteup >= 50 else ("med" if voteup >= 10 else "low")


def _query_type(q: str) -> list[str]:
    return ["interview"] if q == "面经" else ["company", "role"]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-searches", type=int, default=60)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    _load_env()
    tikhub_key = os.environ.get("TIKHUB_API_KEY", "")
    if not tikhub_key:
        print("ERR: TIKHUB_API_KEY 缺失"); return 1

    from app.database import SessionLocal
    from app.models import XhsInsight, XhsNote
    from app.services.podcasts.embed import embed_one, to_blob
    from app.services.xhs.retrieve import reload_cache

    companies = _target_companies()
    print(f"[init] 目标公司 {len(companies)} 家 × {len(QUERIES)} query, 上限 {args.max_searches} 搜")

    db = SessionLocal()
    n_search = n_notes = n_insights = n_skip = 0
    cost = 0.0
    stop = False
    try:
        for company in companies:
            if stop:
                break
            for q in QUERIES:
                if n_search >= args.max_searches:
                    print(f"[stop] 到搜索上限 {args.max_searches}")
                    stop = True
                    break
                kw = f"{company} {q}"
                try:
                    posts = _zhihu_search(kw, tikhub_key)
                except Exception as e:
                    print(f"  [{kw}] 搜索失败: {type(e).__name__}: {e}")
                    continue
                n_search += 1
                cost += TIKHUB_COST
                kept = posts[:MAX_POSTS_PER_QUERY]
                kept = [p for p in kept if p["voteup"] >= MIN_VOTEUP] or kept[:2]
                # A1 相关性过滤: 帖里必须出现公司名 + 金融招聘 keyword (启发式)
                raw_n = len(kept)
                kept = [p for p in kept if _is_finance_relevant(p["title"], p["content"], company)]
                print(f"  [{kw}] 返 {len(posts)} 帖 → 取 {raw_n} → 相关 {len(kept)}")
                for p in kept:
                    note_id = "zh_" + hashlib.md5((p["url"] or p["title"]).encode()).hexdigest()[:16]
                    insight_id = note_id + "_i0"
                    if db.query(XhsInsight).filter_by(insight_id=insight_id).first():
                        n_skip += 1
                        continue
                    if args.dry_run:
                        n_insights += 1
                        continue
                    content = (p["title"] + "\n" + p["content"])[:1800]
                    try:
                        vec = embed_one(content)
                        blob = to_blob(vec)
                    except Exception as e:
                        print(f"     embed 失败跳过: {e}")
                        continue
                    if not db.query(XhsNote).filter_by(note_id=note_id).first():
                        db.add(XhsNote(
                            note_id=note_id, title=p["title"], desc=p["content"][:4000],
                            author_name=p["author"], liked_count=p["voteup"],
                            comment_count=p["comment"], signal_score=float(p["voteup"]),
                            matched_keywords_json=json.dumps([company, q], ensure_ascii=False),
                            source_url=p["url"], embedding=blob,
                            tags_json=json.dumps(["zhihu"], ensure_ascii=False),
                        ))
                        n_notes += 1
                    db.add(XhsInsight(
                        insight_id=insight_id, source_note_id=note_id,
                        type_json=json.dumps(_query_type(q), ensure_ascii=False),
                        primary_type=_query_type(q)[0],
                        role_target_json="[]",
                        company_target_json=json.dumps([company], ensure_ascii=False),
                        sector_target_json="[]",
                        content=content, source_quote=p["content"][:200],
                        speaker="author", confidence=_conf(p["voteup"]),
                        corroboration_json="[]", embedding=blob,
                    ))
                    n_insights += 1
                    db.commit()
                time.sleep(0.15)  # rate-limit 友好
    finally:
        _done(db, n_notes, n_insights, cost, args.dry_run, reload_cache)
        db.close()
    return 0


def _done(db, n_notes, n_insights, cost, dry, reload_cache) -> None:
    if not dry:
        try:
            n = reload_cache(db)
            print(f"[cache] 本进程 retrieve 缓存重载: {n} insights (服务端需重启才生效)")
        except Exception:
            pass
    tag = "DRY-RUN " if dry else ""
    print(f"\n{tag}入库: notes +{n_notes}, insights +{n_insights}, 估算成本 ${cost:.2f}")


if __name__ == "__main__":
    sys.exit(main())
