"""Task C — 7 条薄赛道知识库补厚 (DeepSeek v4-Pro reasoning=high)。

输入: 7 条 data_confidence in (low, low-medium) 的 sub_cat。
流程: 每条 sub_cat → 知乎 3 query 爬 (面经/校招/日常) → 拼 + 现 payload + 库里该赛道的
       XhsInsight verbatim → 喂 Pro high 重合成 payload_json → 写回
       knowledge_subcategories, confidence 升 medium+。

跑法 (cwd=backend):
    PYTHONPATH=. .venv/bin/python scripts/sub_cat_kb_enrich.py
"""
from __future__ import annotations

import html
import json
import os
import re
import sys
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


TIKHUB_ZHIHU = "https://api.tikhub.io/api/v1/zhihu/web/fetch_article_search_v3"
QUERIES = ["面经", "校招", "日常"]
MAX_POSTS_PER_QUERY = 6
MIN_CONTENT_CHARS = 150


def _strip(s: str) -> str:
    return html.unescape(re.sub(r"<[^>]+>", "", s or "")).strip()


def _zhihu_search(kw: str, key: str, retries: int = 2) -> list[dict]:
    for a in range(retries + 1):
        try:
            r = requests.get(
                TIKHUB_ZHIHU, params={"keyword": kw},
                headers={"Authorization": f"Bearer {key}"}, timeout=45,
            )
            if r.status_code == 200:
                break
            if r.status_code in (400, 429, 500, 502, 503, 504) and a < retries:
                time.sleep(1.5 ** a); continue
            r.raise_for_status(); break
        except requests.RequestException:
            if a < retries: time.sleep(1.5 ** a); continue
            raise
    items = (r.json().get("data") or {}).get("data") or []
    posts = []
    for it in items:
        if it.get("type") != "search_result":
            continue
        o = it.get("object") or {}
        content = _strip(o.get("content") or o.get("excerpt") or "")
        if len(content) < MIN_CONTENT_CHARS:
            continue
        posts.append({
            "title": _strip(o.get("title") or (o.get("question") or {}).get("name") or ""),
            "content": content[:1500],
            "voteup": int(o.get("voteup_count") or o.get("vote_count") or 0),
            "url": str(o.get("url") or ""),
        })
    posts.sort(key=lambda p: -p["voteup"])
    return posts[:MAX_POSTS_PER_QUERY]


SYSTEM_PROMPT = """你是 SAIF 高金的资深求职研究员,正在重写一个金融子赛道的"赛道知识库"。

输入: 一份子赛道 (sub_cat) 名、它现有的 KB payload (低置信、要补厚) + 一批新爬到的知乎面经/校招原帖 + 库里已有的同辈情报 verbatim。

任务: 重新合成这个 sub_cat 的 payload_json,要求结构上严格匹配输入的现 payload schema (同样的 key),内容上:
- **hard_requirements**: 5-8 条,具体可证伪 (e.g. "硕士 985/211" 不是 "学历好"); 每条尽量带上典型公司/数字
- **soft_signals**: 3-5 条
- **pitfalls**: 3-5 条 (常见误区/坑/伪岗位)
- **verbatim_quotes**: 5-8 条,每条 {quote, source_url} (从给的爬料里挑真实原话, source_url 必填,从输入里的 url 字段照搬)
- **hiring_season**: 一句话
- **compensation_signal / interview_style / career_trajectory** 若现 payload 有就保留并据爬料微调
- **typical_companies**: 现有的保留,可补 1-2 家
- 保留原 payload 的 strategy_type / industry_focus_candidates / institution_tier_candidates

输出严格 JSON (整个 payload), 不要前后说明文字。"""


def _synth_one(sub_cat: str, cur_payload: dict, posts: list[dict], inhouse_verbatims: list[str]) -> dict:
    from openai import OpenAI
    client = OpenAI(
        base_url=os.environ.get("RESUME_COPILOT_LLM_BASE_URL", "https://api.deepseek.com/v1"),
        api_key=os.environ.get("DEEPSEEK_API_KEY") or os.environ.get("RESUME_COPILOT_LLM_API_KEY", ""),
        timeout=180,
        max_retries=1,
    )
    user_msg = json.dumps({
        "sub_cat": sub_cat,
        "current_payload": cur_payload,
        "new_zhihu_posts": posts[:18],     # 限制 token
        "inhouse_xhs_verbatims": inhouse_verbatims[:25],
    }, ensure_ascii=False)
    resp = client.chat.completions.create(
        model=os.environ.get("CRAWLER_LLM_PRO_MODEL", "deepseek-v4-pro"),
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_msg},
        ],
        extra_body={"reasoning_effort": "high"},
        response_format={"type": "json_object"},
        temperature=0.3,
    )
    return json.loads(resp.choices[0].message.content)


def main() -> int:
    _load_env()
    tikhub = os.environ.get("TIKHUB_API_KEY", "")
    if not tikhub:
        print("ERR: TIKHUB_API_KEY 缺"); return 1

    from app.database import SessionLocal
    from app.models import KnowledgeSubcategory, XhsInsight
    from app.services.podcasts.embed import embed_one, to_blob

    db = SessionLocal()
    THIN = list(db.query(KnowledgeSubcategory).filter(
        KnowledgeSubcategory.data_confidence.in_(["low", "low-medium"])
    ).all())
    print(f"[init] 待补厚 {len(THIN)} 条薄赛道: {[k.sub_cat for k in THIN]}")

    n_done = 0
    cost_search = 0.0
    for kb in THIN:
        sc = kb.sub_cat
        print(f"\n=== {sc} (现 conf={kb.data_confidence}) ===")
        # 1) 爬 知乎
        all_posts: list[dict] = []
        for q in QUERIES:
            try:
                posts = _zhihu_search(f"{sc} {q}", tikhub)
                cost_search += 0.01
                print(f"  [{q}] +{len(posts)} 帖")
                all_posts.extend(posts)
            except Exception as e:
                print(f"  [{q}] 搜失败: {e}")
        # dedup by url
        seen = set(); dedup = []
        for p in all_posts:
            if p["url"] not in seen:
                seen.add(p["url"]); dedup.append(p)
        # 2) 现 payload
        try:
            cur = json.loads(kb.payload_json or "{}")
        except Exception:
            cur = {}
        # 3) 库内该赛道 verbatim (从 XhsInsight 找 sub_cat 命中的)
        inhouse: list[str] = []
        for r in db.query(XhsInsight).filter(XhsInsight.sector_target_json.like(f'%"{sc}"%')).limit(30).all():
            if r.source_quote:
                inhouse.append(r.source_quote[:240])
        # 4) Pro 合成
        if not dedup:
            print("  ⚠️ 无爬到帖,跳过"); continue
        try:
            t0 = time.time()
            new_payload = _synth_one(sc, cur, dedup, inhouse)
            print(f"  ✓ Pro 合成 {time.time()-t0:.0f}s | new keys: {list(new_payload.keys())[:8]}")
        except Exception as e:
            print(f"  ✗ Pro 合成失败: {e}"); continue
        # 5) 写回 + 升 confidence + 重算 embedding
        new_payload["_data_confidence"] = "medium"
        try:
            text_blob = (sc + " " + " ".join(
                (q.get("quote","") if isinstance(q,dict) else str(q))
                for q in (new_payload.get("verbatim_quotes") or [])[:5]
            ))[:1800]
            emb = embed_one(text_blob); blob = to_blob(emb)
            kb.payload_json = json.dumps(new_payload, ensure_ascii=False)
            kb.data_confidence = "medium"
            kb.embedding = blob
            db.commit()
            n_done += 1
            print(f"  ✅ 入库 confidence升 medium, payload bytes={len(kb.payload_json)}")
        except Exception as e:
            print(f"  ✗ 入库失败: {e}"); db.rollback()
        time.sleep(0.3)
    db.close()
    print(f"\n=== 完成 ===\n  补厚 {n_done}/{len(THIN)} 条 | 知乎搜索成本 ${cost_search:.2f} | (+ DeepSeek Pro 合成)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
