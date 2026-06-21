"""B站金融面经转录 → typed XhsInsight（source_platform='bilibili'）。

把 crawler-xhs worktree 的 108 条 B站转录稿,经 DeepSeek(Pro+reasoning)抽成 5 桶
typed insight,向量化后幂等写进**共享 dev DB** 的 xhs_insights + xhs_notes。
因 retrieve._load_cache 读全表不挑 source_platform,写进去即被 XhsContextProvider
自动检索 → 模拟面试出题/评分吃到。零新表、零新 provider。

设计:
- Phase 1（并发,网络密集,不碰 DB）: 每条转录 → DeepSeek 抽取 {relevant, insights}。
  relevant=false（养猫/游戏等噪声,prompt 自带门）直接 drop。
- Phase 2（串行,单线程写库,遵守"绝不跨线程共享 session"铁律）: 批量 embed + 幂等 upsert。
- 幂等: insight_id=bili_<BV>_<md5(content)[:8]>,note_id=bili_<BV>,已存在则 skip → 可断点重跑。

跑法(cwd=backend,主 clone):
    PYTHONPATH=. .venv/bin/python scripts/bilibili_transcripts_to_insights.py            # 全量
    PYTHONPATH=. .venv/bin/python scripts/bilibili_transcripts_to_insights.py --limit 3  # smoke
    PYTHONPATH=. .venv/bin/python scripts/bilibili_transcripts_to_insights.py --workers 6
"""
from __future__ import annotations

import argparse
import hashlib
import html
import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent
# B站转录稿生料(.gitignore，可重生)。默认指向 crawler-xhs worktree；
# 覆写用环境变量 BILI_TRANSCRIPTS_DIR / BILI_MANIFEST。
_DEFAULT_PODCASTS = Path("/home/chuanbo/projects/JobRadar/.worktrees/crawler-xhs/backend/data/podcasts")
TRANSCRIPTS = Path(os.environ.get("BILI_TRANSCRIPTS_DIR", str(_DEFAULT_PODCASTS / "transcripts_staging")))
MANIFEST = Path(os.environ.get("BILI_MANIFEST", str(_DEFAULT_PODCASTS / "_harvest/manifest.jsonl")))
MAX_CHARS = 8000
ALLOWED_TYPES = {"interview_qa", "role_insight", "resume_tip", "company_anecdote", "industry_trend"}

# 自包含抽取 prompt（与 bake-off 验证过的同一份；DeepSeek Pro+reasoning 胜出 Haiku）。
PROMPT_TPL = """你是金融校招知识库的信息抽取器。输入是一段 B 站视频的中文转录稿（金融求职/面经类，但也可能是关键词误匹配的无关内容）。请从中抽取「可复用于模拟面试出题与评分」的结构化情报。

# 第一步：相关性判定
先判断这段转录是否真的与「金融行业求职 / 面试 / 实习 / 投研 / 投行 / 量化 / 资管」相关。
- 如果是宠物、游戏、生活、纯娱乐、医疗等与金融求职无关的内容（即便标题里有 IBD、量化 等词被误匹配），直接返回：{"relevant": false, "reason": "<一句话原因>", "insights": []}
- 相关才继续抽取。

# 第二步：抽取 typed insight（仅 relevant=true 时）
把内容拆成若干条独立 insight。每条必须严格落在以下 5 个类型之一或多个：
- "interview_qa"：真实面试会问的问题 / 考点 / 答题套路（对出题最有价值）
- "role_insight"：岗位真实工作内容、日常、能力要求、职业路径
- "resume_tip"：简历 / 申请 / 背景包装的具体建议
- "company_anecdote"：特定公司/机构的面试流程、文化、真实经历
- "industry_trend"：行业格局、薪资、招聘行情、赛道对比

每条 insight 字段：
- "type": 上述类型的数组（1-2 个）
- "content": 一句凝练、可被语义检索命中的情报（中文，不超过 80 字，自带主语，别用"他说"这种指代）
- "source_quote": 从转录里摘的**逐字原话**（不得改写、润色；模拟面试评分要拿它当参照标准）
- "role_target": 相关岗位数组，如 ["量化研究员","投行分析师"]，没有则 []
- "company_target": 明确提到的公司数组，如 ["中信证券","Jane Street"]，没有则 []
- "sector_target": 赛道数组，如 ["量化私募","投行IBD","公募基金"]，没有则 []
- "confidence": "high"（具体、可验证）/ "med"（一般经验）/ "low"（模糊/主观）
- "speaker": "author"

# 规则
- 宁缺毋滥：模糊的口水话、纯口号、无信息量的句子不要抽。一条好的 interview_qa 比五条废话有用。
- source_quote 必须真实出现在转录里，不许编造数字或公司名。
- 输出严格 JSON：{"relevant": true, "insights": [ {...}, ... ]}

转录稿如下：
---
{TRANSCRIPT}
---
"""


def _load_env() -> None:
    p = BACKEND / ".env.local"
    if not p.exists():
        print(f"WARN no .env.local at {p}", file=sys.stderr)
        return
    for line in p.read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if s and not s.startswith("#") and "=" in s:
            k, v = s.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def _load_manifest() -> dict[str, dict]:
    out: dict[str, dict] = {}
    if not MANIFEST.exists():
        return out
    for line in MANIFEST.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            r = json.loads(line)
            if r.get("bv"):
                out[r["bv"]] = r
        except json.JSONDecodeError:
            continue
    return out


def _extract_one(bv: str, prompt_tpl: str) -> dict:
    """Phase 1 worker: DeepSeek extraction. No DB. Returns {bv, relevant, insights, secs, err}."""
    from app.services.llm_json import deepseek_json_fn

    tf = TRANSCRIPTS / f"{bv}.txt"
    transcript = tf.read_text(encoding="utf-8")[:MAX_CHARS]
    prompt = prompt_tpl.replace("{TRANSCRIPT}", transcript)
    t0 = time.time()
    try:
        out = deepseek_json_fn(prompt, reasoning_effort="medium")
    except Exception as e:  # deepseek_json_fn already swallows, but belt-and-suspenders
        return {"bv": bv, "relevant": None, "insights": [], "secs": time.time() - t0, "err": str(e)}
    rel = bool(out.get("relevant")) if isinstance(out, dict) else False
    insights = out.get("insights", []) if isinstance(out, dict) else []
    return {"bv": bv, "relevant": rel, "insights": insights, "secs": time.time() - t0, "err": ""}


def _clean_types(types) -> list[str]:
    if not isinstance(types, list):
        return ["role_insight"]
    keep = [t for t in types if t in ALLOWED_TYPES]
    return keep or ["role_insight"]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0, help="only first N transcripts (smoke)")
    ap.add_argument("--workers", type=int, default=6, help="concurrent DeepSeek calls")
    args = ap.parse_args()

    _load_env()
    prompt_tpl = PROMPT_TPL

    from app.database import SessionLocal
    from app.models import XhsInsight, XhsNote
    from app.services.podcasts.embed import embed_many, to_blob
    from app.services.xhs.retrieve import reload_cache

    manifest = _load_manifest()
    bvs = sorted(p.stem for p in TRANSCRIPTS.glob("BV*.txt"))
    if args.limit:
        bvs = bvs[: args.limit]
    print(f"[init] {len(bvs)} 条转录待处理 (workers={args.workers})")

    # ---- Phase 1: 并发抽取（网络密集，不碰 DB）----
    results: list[dict] = []
    t_start = time.time()
    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        futs = {ex.submit(_extract_one, bv, prompt_tpl): bv for bv in bvs}
        done = 0
        for fut in as_completed(futs):
            r = fut.result()
            results.append(r)
            done += 1
            tag = "DROP噪声" if r["relevant"] is False else (f"{len(r['insights'])}条" if r["relevant"] else "ERR")
            print(f"  [{done}/{len(bvs)}] {r['bv']} {tag} {r['secs']:.0f}s {r.get('err','')}")
    print(f"[phase1] 抽取完成 {time.time()-t_start:.0f}s")

    relevant = [r for r in results if r["relevant"] and r["insights"]]
    dropped = [r for r in results if r["relevant"] is False]
    errs = [r for r in results if r["relevant"] is None]
    print(f"[phase1] relevant={len(relevant)} dropped(噪声)={len(dropped)} err={len(errs)}")

    # ---- Phase 2: 串行写库（embed + 幂等 upsert）----
    db = SessionLocal()
    n_notes = n_ins = n_skip = 0
    try:
        for r in relevant:
            bv = r["bv"]
            note_id = f"bili_{bv}"
            mf = manifest.get(bv, {})
            title = html.unescape(mf.get("title", "") or "")[:200]
            url = f"https://www.bilibili.com/video/{bv}"
            keyword = mf.get("keyword", "")

            # 该 BV 所有 insight 的 content 批量 embed
            valid = []
            for x in r["insights"]:
                content = (x.get("content") or "").strip()
                if not content:
                    continue
                valid.append(x)
            if not valid:
                continue
            texts = [
                "\n".join([
                    x.get("content") or "",
                    x.get("source_quote") or "",
                    " ".join(x.get("role_target") or []),
                    " ".join(x.get("company_target") or []),
                ])[:1200]
                for x in valid
            ]
            try:
                vecs = embed_many(texts)
            except Exception as e:
                print(f"  embed fail {bv}: {e}")
                continue

            # XhsNote（一条 BV 一行，note 的 embedding 用首条 insight 向量兜个底）
            if not db.query(XhsNote).filter_by(note_id=note_id).first():
                db.add(XhsNote(
                    note_id=note_id,
                    title=title or f"B站 {bv}",
                    desc=(r["insights"][0].get("content") or "")[:2000],
                    author_name="",
                    tags_json=json.dumps(["bilibili", keyword], ensure_ascii=False),
                    matched_keywords_json=json.dumps([keyword] if keyword else [], ensure_ascii=False),
                    source_url=url,
                    signal_score=0.0,
                    embedding=to_blob(vecs[0]),
                ))
                n_notes += 1

            for x, vec in zip(valid, vecs):
                content = (x.get("content") or "").strip()
                insight_id = f"{note_id}_{hashlib.md5(content.encode()).hexdigest()[:8]}"
                if db.query(XhsInsight).filter_by(insight_id=insight_id).first():
                    n_skip += 1
                    continue
                types = _clean_types(x.get("type"))
                conf = x.get("confidence") if x.get("confidence") in ("high", "med", "low") else "med"
                db.add(XhsInsight(
                    insight_id=insight_id,
                    source_note_id=note_id,
                    type_json=json.dumps(types, ensure_ascii=False),
                    primary_type=types[0],
                    role_target_json=json.dumps(x.get("role_target") or [], ensure_ascii=False),
                    company_target_json=json.dumps(x.get("company_target") or [], ensure_ascii=False),
                    sector_target_json=json.dumps(x.get("sector_target") or [], ensure_ascii=False),
                    content=content,
                    source_quote=(x.get("source_quote") or "")[:500],
                    speaker="author",
                    confidence=conf,
                    corroboration_json="[]",
                    embedding=to_blob(vec),
                    source_platform="bilibili",
                ))
                n_ins += 1
            db.commit()

        try:
            n = reload_cache(db)
            print(f"[cache] retrieve 缓存重载 {n} insights（服务端需重启才生效）")
        except Exception as e:
            print(f"[cache] reload skip: {e}")
    finally:
        db.close()

    print(f"\n入库: notes +{n_notes}, insights +{n_ins}, skip 已存 {n_skip}")
    print(f"噪声 drop {len(dropped)} 条: {[r['bv'] for r in dropped]}")
    if errs:
        print(f"⚠️ 抽取失败 {len(errs)} 条: {[r['bv'] for r in errs]}（可重跑补）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
