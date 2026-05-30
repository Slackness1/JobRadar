"""增量双源入库 — 给 ground_truth 119 中尚未 zhihu 入过的 ~58 家公司,
同时跑 zhihu (TikHub fetch_article_search_v3) + xhs hybrid (TikHub search_notes + Decodo),
幂等 (insight_id 已存在则跳),完成后调 reload_cache。

跑法 (cwd=backend):
    PYTHONPATH=. .venv/bin/python scripts/intel_incremental_ingest.py
"""
from __future__ import annotations

import hashlib
import html
import json
import os
import re
import sys
import tempfile
import time
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.chdir(str(Path(__file__).resolve().parent.parent))


def _load_env() -> None:
    for line in Path(".env.local").read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if s and not s.startswith("#") and "=" in s:
            k, v = s.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


_load_env()
from app.database import SessionLocal  # noqa: E402
from app.models import XhsInsight, XhsNote  # noqa: E402
from app.services.podcasts.embed import embed_one, to_blob  # noqa: E402
from app.services.taxonomy_discovery.budget_tracker import BudgetTracker  # noqa: E402
from app.services.taxonomy_discovery.crawler_client import CrawlerClient, build_xhs_discovery_url  # noqa: E402
from app.services.xhs.retrieve import reload_cache  # noqa: E402

TIKHUB_ZHIHU = "https://api.tikhub.io/api/v1/zhihu/web/fetch_article_search_v3"
QUERIES = ["面经", "实习"]
MAX_POSTS_PER_QUERY = 5

FINANCE_KW = re.compile(
    r"投行|投研|研究员|分析师|校招|秋招|春招|暑期|实习|面试|面经|笔试|"
    r"IBD|PE|VC|FOF|量化|quant|公募|私募|券商|资管|信用|固收|宏观|"
    r"销售交易|S&T|FICC|衍生品|内推|offer|薪资|待遇",
    re.IGNORECASE,
)
_COMPANY_SUFFIX = re.compile(r"(基金|证券|资管|集团|公司|银行|国际|管理|股份|有限|投资|信托|期货|保险)$")


def _company_stem(name: str) -> str:
    stem = _COMPANY_SUFFIX.sub("", name or "")
    return stem if len(stem) >= 2 else name


def _is_relevant(title: str, content: str, company: str) -> bool:
    text = (title or "") + " " + (content or "")
    stem = _company_stem(company)
    if company and (company not in text) and (stem not in text):
        return False
    return bool(FINANCE_KW.search(text))


def _strip(s: str) -> str:
    return html.unescape(re.sub(r"<[^>]+>", "", s or "")).strip()


def _conf(voteup: int) -> str:
    return "high" if voteup >= 50 else ("med" if voteup >= 10 else "low")


# -------------------- 目标公司 --------------------
def _target_companies() -> list[str]:
    """119 ground_truth - 已 zhihu 入过的公司。"""
    import sqlite3
    gt = json.loads(Path("data/ground_truth_companies_v1.json").read_text(encoding="utf-8"))["ground_truth"]
    all_gt = {(c.get("name") or "").strip() for lst in gt.values() for c in lst if c.get("name")}
    all_gt.discard("")
    c = sqlite3.connect("data/jobradar.db")
    zhi_done: set[str] = set()
    for (cj,) in c.execute("select company_target_json from xhs_insights where source_note_id like 'zh_%'"):
        try:
            for n in json.loads(cj or "[]"):
                if n:
                    zhi_done.add(str(n).strip())
        except Exception:
            pass
    c.close()
    return sorted(all_gt - zhi_done)


# -------------------- 知乎(沿用 zhihu_intel_ingest 逻辑) --------------------
def _zhihu_search(keyword: str, key: str, retries: int = 2) -> list[dict]:
    for attempt in range(retries + 1):
        try:
            r = requests.get(
                TIKHUB_ZHIHU, params={"keyword": keyword},
                headers={"Authorization": f"Bearer {key}"}, timeout=45,
            )
            if r.status_code == 200:
                break
            if r.status_code in (400, 429, 500, 502, 503, 504) and attempt < retries:
                time.sleep(1.5 ** attempt); continue
            r.raise_for_status(); break
        except requests.RequestException:
            if attempt < retries:
                time.sleep(1.5 ** attempt); continue
            raise
    items = (r.json().get("data") or {}).get("data") or []
    posts: list[dict] = []
    for it in items:
        if it.get("type") != "search_result":
            continue
        o = it.get("object") or {}
        content = _strip(o.get("content") or o.get("excerpt") or "")
        if len(content) < 120:
            continue
        posts.append({
            "title": _strip(o.get("title") or (o.get("question") or {}).get("name") or ""),
            "content": content,
            "voteup": int(o.get("voteup_count") or o.get("vote_count") or 0),
            "url": str(o.get("url") or ""),
            "author": str(((o.get("author") or {}).get("name")) or ""),
        })
    posts.sort(key=lambda p: -p["voteup"])
    return posts


def _zhihu_ingest_company(company: str, key: str, db) -> int:
    n = 0
    for q in QUERIES:
        kw = f"{company} {q}"
        try:
            posts = _zhihu_search(kw, key)
        except Exception as e:
            print(f"    [zh {q}] err: {e}"); continue
        kept = posts[:MAX_POSTS_PER_QUERY]
        kept = [p for p in kept if p["voteup"] >= 5] or kept[:2]
        kept = [p for p in kept if _is_relevant(p["title"], p["content"], company)]
        for p in kept:
            note_id = "zh_" + hashlib.md5((p["url"] or p["title"]).encode()).hexdigest()[:16]
            insight_id = note_id + "_i0"
            if db.query(XhsInsight).filter_by(insight_id=insight_id).first():
                continue
            content = (p["title"] + "\n" + p["content"])[:1800]
            try:
                vec = embed_one(content); blob = to_blob(vec)
            except Exception as e:
                print(f"    [zh embed] {e}"); continue
            if not db.query(XhsNote).filter_by(note_id=note_id).first():
                db.add(XhsNote(
                    note_id=note_id, title=p["title"], desc=p["content"][:4000],
                    author_name=p["author"], liked_count=p["voteup"],
                    signal_score=float(p["voteup"]),
                    matched_keywords_json=json.dumps([company, q], ensure_ascii=False),
                    source_url=p["url"], embedding=blob,
                    tags_json=json.dumps(["zhihu"], ensure_ascii=False),
                ))
            db.add(XhsInsight(
                insight_id=insight_id, source_note_id=note_id,
                type_json=json.dumps(["interview"] if q == "面经" else ["company", "role"], ensure_ascii=False),
                primary_type="interview" if q == "面经" else "company",
                role_target_json="[]",
                company_target_json=json.dumps([company], ensure_ascii=False),
                sector_target_json="[]",
                content=content, source_quote=p["content"][:200],
                speaker="author", confidence=_conf(p["voteup"]),
                corroboration_json="[]", embedding=blob,
            ))
            n += 1
        db.commit()
        time.sleep(0.1)
    return n


# -------------------- XHS hybrid --------------------
_CHROME_RE = re.compile(
    r"^\s*(\*|\-|创作中心|业务合作|发现|直播|发布|通知|沪ICP|协议规则|商务合作|"
    r"侵权投诉|©|关注|首页|登录|个人主页|消息|放映厅|商城|MORE|登录后|App|"
    r"扫一扫|二维码|关注作者|更多创作灵感)"
)


def _extract_xhs_body(md: str) -> str:
    """从 Decodo 抓的 XHS 帖 markdown 里抠正文,去 chrome 导航/图标/二维码。"""
    md = re.sub(r"!\[.*?\]\([^)]*\)", " ", md or "")          # 图片
    md = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", md)          # 链接 -> text
    md = re.sub(r"```.*?```", " ", md, flags=re.DOTALL)
    md = re.sub(r"data:image[^\s)]+", " ", md)
    lines: list[str] = []
    for ln in md.split("\n"):
        s = ln.strip()
        if not s or len(s) < 4: continue
        if _CHROME_RE.match(s): continue
        # 跳过纯标点 / 纯英文 url 链接残留
        if re.fullmatch(r"[\W_]+", s): continue
        lines.append(s)
    text = "\n".join(lines).strip()
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text[:3500]


def _xhs_ingest_company(company: str, client: CrawlerClient, db) -> int:
    n = 0
    for q in QUERIES:
        kw = f"{company} {q}"
        try:
            notes = client.search_notes(kw)
        except Exception as e:
            print(f"    [xhs search {q}] {e}"); continue
        kept = notes[:MAX_POSTS_PER_QUERY]
        for nt in kept:
            xhs_nid = str(nt.get('note_id') or nt.get('id') or '').strip()
            if not xhs_nid:
                continue
            note_id = f"xhs_{xhs_nid}"
            insight_id = f"{note_id}_{hashlib.md5(company.encode()).hexdigest()[:8]}"
            if db.query(XhsInsight).filter_by(insight_id=insight_id).first():
                continue
            xs = nt.get('xsec_token') or nt.get('xsecToken') or ''
            url = build_xhs_discovery_url(xhs_nid, xs)
            try:
                md = client.decode_fetch_url(url)
            except Exception as e:
                print(f"    [xhs fetch] {e}"); continue
            body = _extract_xhs_body(md)
            title = (nt.get('title') or nt.get('display_title') or '')[:120]
            if len(body) < 100: continue
            if not _is_relevant(title, body, company): continue
            try:
                vec = embed_one(body[:1800]); blob = to_blob(vec)
            except Exception as e:
                print(f"    [xhs embed] {e}"); continue
            liked = int(nt.get('liked_count') or nt.get('likes') or 0)
            if not db.query(XhsNote).filter_by(note_id=note_id).first():
                db.add(XhsNote(
                    note_id=note_id, title=title,
                    desc=body[:2000],
                    author_name=str((nt.get('user') or {}).get('nickname') or '')[:80],
                    liked_count=liked,
                    matched_keywords_json=json.dumps([company, q], ensure_ascii=False),
                    source_url=url, signal_score=float(liked),
                    embedding=blob,
                    tags_json=json.dumps(["xhs", "company-targeted"], ensure_ascii=False),
                ))
            db.add(XhsInsight(
                insight_id=insight_id, source_note_id=note_id,
                type_json=json.dumps(["company"], ensure_ascii=False),
                primary_type="company",
                role_target_json="[]",
                company_target_json=json.dumps([company], ensure_ascii=False),
                sector_target_json="[]",
                content=body[:1800], source_quote=body[:200],
                speaker="author", confidence=_conf(liked),
                corroboration_json="[]", embedding=blob,
            ))
            n += 1
        db.commit()
        time.sleep(0.2)
    return n


def main() -> int:
    tikhub = os.environ.get("TIKHUB_API_KEY", "")
    decodo = os.environ.get("WEB_SCRAPING_API_KEY", "")
    if not tikhub:
        print("ERR: TIKHUB_API_KEY 缺"); return 1

    targets = _target_companies()
    print(f"[init] 待入库 {len(targets)} 家 (ground_truth 119 - 已 zhi_done)")

    bf = Path(tempfile.gettempdir()) / "intel_inc_budget.json"
    if bf.exists(): bf.unlink()
    client = CrawlerClient(
        tikhub_key=tikhub, decode_key=decodo,
        budget_tracker=BudgetTracker(state_file=bf, limit_usd=20.0),
    )
    db = SessionLocal()
    n_zhi_total = n_xhs_total = 0
    try:
        for i, company in enumerate(targets, 1):
            print(f"\n[{i}/{len(targets)}] {company}")
            try:
                nz = _zhihu_ingest_company(company, tikhub, db)
                n_zhi_total += nz
                print(f"  zhihu +{nz}")
            except Exception as e:
                print(f"  zhihu err: {type(e).__name__} {e}")
            try:
                nx = _xhs_ingest_company(company, client, db)
                n_xhs_total += nx
                print(f"  xhs +{nx} | 累计 ${client.budget_tracker.spent():.2f}")
            except Exception as e:
                print(f"  xhs err: {type(e).__name__} {e}")
        try:
            n = reload_cache(db)
            print(f"\n[cache] retrieve 缓存重载: {n} insights (服务端需重启)")
        except Exception:
            pass
    finally:
        db.close()
    print(f"\n=== 增量入库完成 ===")
    print(f"  zhihu 新增 insights: {n_zhi_total}")
    print(f"  xhs   新增 insights: {n_xhs_total}")
    print(f"  CrawlerClient 累计花费: ${client.budget_tracker.spent():.2f}")
    print(f"\n下一步: 跑 scripts/intel_score_and_cluster.py 重打分 + 重启后端")
    return 0


if __name__ == "__main__":
    sys.exit(main())
