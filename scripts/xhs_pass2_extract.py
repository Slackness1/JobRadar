"""XHS Pass 2 — LLM-extract typed insights per note via DeepSeek.

Mirrors podcast_pass3_extract structure but per-note (not per-episode), and
adds "evidence_strength" weighting (XHS noise is much higher than podcasts).

Output: backend/data/xhs/_processed/insights.jsonl
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PROC = ROOT / "backend/data/xhs/_processed"
NOTES = PROC / "notes_clean.jsonl"
OUT = PROC / "insights.jsonl"
DEBUG = PROC / "_debug"
DEBUG.mkdir(parents=True, exist_ok=True)


def _env(k: str) -> str | None:
    for p in [ROOT / "backend/.env.local", ROOT / "backend/.env"]:
        if p.exists():
            for line in p.read_text().splitlines():
                if line.startswith(f"{k}="):
                    return line.split("=", 1)[1].strip().strip('"').strip("'")
    return None


DS_KEY = os.environ.get("DEEPSEEK_API_KEY") or _env("DEEPSEEK_API_KEY") or _env("RESUME_COPILOT_API_KEY")
DS_URL = (os.environ.get("DEEPSEEK_BASE_URL") or _env("DEEPSEEK_BASE_URL") or _env("RESUME_COPILOT_BASE_URL") or "https://api.deepseek.com/v1") + "/chat/completions"
DS_MODEL = os.environ.get("XHS_PASS2_MODEL") or "deepseek-v4-flash"

# Re-use podcast term_dict for canonical names
TERM_DICT_PATH = ROOT / "backend/data/podcasts/_processed/term_dict.json"
term_dict = json.loads(TERM_DICT_PATH.read_text())
CANON_COMPANIES = [c["canonical"] for c in term_dict["companies"]]
CANON_ROLES = [r["canonical"] for r in term_dict["roles"]]
CANON_SECTORS = [s["canonical"] for s in term_dict["sectors"]]

VALID_TYPES = {"role_insight", "resume_tip", "interview_qa", "company_anecdote", "industry_trend"}
VALID_SPEAKER = {"author", "commenter", "unknown"}
VALID_CONF = {"high", "med", "low"}

SYS = f"""你是金融求职社媒情报抽取专家。从一条**小红书帖子 + 高赞评论**里抽取类型化 insight 记录，喂给 RAG 召回供岗位推荐 / 简历建议 / 模拟面试三个下游使用。

**抽取规则**：
- 一条帖子产出 0-8 条 insight，**宁缺勿滥**：明显软广 / 鸡汤 / 自夸 / 纯吐槽 → 不抽
- 每条必须有真正可被下游 RAG 用到的实操价值
- 每条必须有 source_quote（**逐字**从帖子或评论里摘取，10-200字），不能改写
- 高赞评论(like ≥ 50)往往比帖子本身信息密度更高 — **优先**从评论里抽
- **小红书噪声很高**：如果整篇都是"分享我的求职心路 ✨" 这种空话，老老实实返 {{"insights": []}}

**5 种 type**（一条可同时属于 1-3 种，用 list）：
- role_insight: 具体金融岗位的"日常做什么 / 进阶路径 / 薪资段 / 技能要求"
- resume_tip: "什么样的简历 / 经历能 / 不能进金融"，含反例
- interview_qa: 真实面试问题、常见考点、面试套路、避坑
- company_anecdote: 具体公司的 culture / 八卦 / 真实故事 / 面试体感
- industry_trend: 赛道冷热、政策影响、近 1-3 年行业变化

**confidence 三档**：
- high: 帖主明确说"我是 XX 公司的 / 我刚拿到 XX offer / 我面了 XX"，或评论里同样级别的亲历
- med: 帖主转述听说 / "我朋友在 X" / 评论说"我也遇到了" 的弱亲历
- low: 推测 / 模糊感受 / "听说" / 鸡汤

**speaker**：
- author: 来自帖子正文（标题 + desc）
- commenter: 来自评论区
- unknown: 抽不准

**role_target / company_target / sector_target**：必填，list 允许为空；尽量用 canonical 名。

Canonical 列表：
- companies: {', '.join(CANON_COMPANIES)}
- roles: {', '.join(CANON_ROLES)}
- sectors: {', '.join(CANON_SECTORS)}

**输出严格 JSON**：{{"insights": [...]}}
每条字段:
{{
  "type": ["interview_qa"],
  "role_target": ["行业研究员"],
  "company_target": ["华夏基金"],
  "sector_target": ["公募基金"],
  "content": "...",                  // ≤120字 结构化结论
  "source_quote": "...",             // 帖子/评论逐字 10-200字
  "speaker": "author",
  "confidence": "high"
}}"""


def build_user_msg(note: dict) -> str:
    kws = "、".join(note.get("matched_keywords") or [])
    tags = "、".join(note.get("tags") or [])
    top_c = note.get("top_comments") or []
    comments_block = "\n".join(
        f"  [{i+1}] (👍{c['like']} · {c['ip']}) {c['content'][:300]}"
        for i, c in enumerate(top_c[:12]) if c["content"]
    ) or "(无高赞评论)"
    return f"""【帖子元信息】
匹配搜索词: {kws}
作者: {note.get('author_name') or '?'} (ip: {top_c[0]['ip'] if top_c else '?'})
点赞 {note.get('liked_count', 0)} · 收藏 {note.get('collected_count', 0)} · 评论 {note.get('comment_count', 0)}
标签: {tags or '(无)'}
发布时间: {note.get('time_iso', '?')}

【标题】
{note.get('title', '')}

【正文】
{note.get('desc', '')}

【高赞评论 (TOP)】
{comments_block}"""


def call_llm(payload_body: dict) -> dict:
    payload_body["model"] = DS_MODEL
    body = json.dumps(payload_body).encode("utf-8")
    req = urllib.request.Request(
        DS_URL,
        data=body,
        headers={"Authorization": f"Bearer {DS_KEY}", "Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=240) as r:
        return json.load(r)


def validate_insight(ins):
    if not isinstance(ins, dict):
        raise ValueError("not a dict")
    types = ins.get("type") or []
    if isinstance(types, str):
        types = [types]
    types = [t for t in types if t in VALID_TYPES]
    if not types:
        raise ValueError(f"no valid type in {ins.get('type')}")
    content = (ins.get("content") or "").strip()
    quote = (ins.get("source_quote") or "").strip()
    if len(content) < 10 or len(quote) < 10:
        raise ValueError("content/quote too short")
    speaker = ins.get("speaker") or "unknown"
    if speaker not in VALID_SPEAKER:
        speaker = "unknown"
    conf = ins.get("confidence") or "med"
    if conf not in VALID_CONF:
        conf = "med"
    return {
        "type": types,
        "role_target": ins.get("role_target") or [],
        "company_target": ins.get("company_target") or [],
        "sector_target": ins.get("sector_target") or [],
        "content": content,
        "source_quote": quote,
        "speaker": speaker,
        "confidence": conf,
    }


def get_done_ids() -> set[str]:
    if not OUT.exists():
        return set()
    return {json.loads(l)["source_note_id"] for l in OUT.read_text().splitlines() if l.strip()}


def process(note: dict) -> tuple:
    nid = note["note_id"]
    user_msg = build_user_msg(note)
    payload = {
        "messages": [
            {"role": "system", "content": SYS},
            {"role": "user", "content": user_msg},
        ],
        "temperature": 0.0,
        "max_tokens": 4096,
        "response_format": {"type": "json_object"},
    }
    try:
        resp = call_llm(payload)
    except urllib.error.HTTPError as e:
        body = ""
        try:
            body = e.read().decode("utf-8", errors="replace")
        except Exception:
            pass
        return ("err", nid, [], f"http {e.code}: {body[:200]}")
    except Exception as e:
        return ("err", nid, [], str(e)[:200])
    content = resp["choices"][0]["message"]["content"]
    try:
        data = json.loads(content)
    except Exception as e:
        (DEBUG / f"{nid[:12]}__pass2.raw.txt").write_text(content)
        return ("err", nid, [], f"JSON parse: {e}")
    raw_list = data.get("insights") if isinstance(data, dict) else data
    if not isinstance(raw_list, list):
        return ("err", nid, [], "no insights array")
    valid = []
    bad = []
    for i, ins in enumerate(raw_list):
        try:
            cleaned = validate_insight(ins)
            cleaned["id"] = f"xhs_{nid[:10]}_{i:02d}"
            cleaned["source_note_id"] = nid
            valid.append(cleaned)
        except ValueError as e:
            bad.append({"idx": i, "err": str(e), "raw": ins})
    if bad:
        (DEBUG / f"{nid[:12]}__pass2.bad.json").write_text(json.dumps(bad, ensure_ascii=False, indent=2))
    return ("ok", nid, valid, {"usage": resp.get("usage", {}), "bad": len(bad)})


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sample", type=int, default=0)
    ap.add_argument("--workers", type=int, default=8)
    args = ap.parse_args()
    if not DS_KEY:
        print("DEEPSEEK_API_KEY (or RESUME_COPILOT_API_KEY) not set", file=sys.stderr)
        sys.exit(1)

    all_notes = [json.loads(l) for l in NOTES.read_text().splitlines() if l.strip()]
    done = get_done_ids()
    todo = [n for n in all_notes if n["note_id"] not in done]
    if args.sample:
        todo = todo[: args.sample]
    print(f"Done: {len(done)} / Todo: {len(todo)} / Total notes: {len(all_notes)}")
    if not todo:
        return

    out_h = OUT.open("a")
    n_ok = n_err = total_in = total_out = total_bad = n_empty = 0
    t0 = time.time()
    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        futs = [ex.submit(process, n) for n in todo]
        for fut in as_completed(futs):
            status, nid, insights, info = fut.result()
            if status == "ok":
                for ins in insights:
                    out_h.write(json.dumps(ins, ensure_ascii=False) + "\n")
                out_h.flush()
                u = info["usage"]
                total_in += u.get("prompt_tokens", 0)
                total_out += u.get("completion_tokens", 0)
                total_bad += info["bad"]
                if not insights:
                    n_empty += 1
                n_ok += 1
                print(f"  ✓ {nid[:12]:<12} {len(insights):>2} insights  bad={info['bad']:>2}  in={u.get('prompt_tokens')}/out={u.get('completion_tokens')}")
            else:
                n_err += 1
                print(f"  ✗ {nid[:12]}  {info[:140] if info else ''}")
    out_h.close()
    dt = time.time() - t0
    print(f"\nDone in {dt:.0f}s. ok={n_ok} err={n_err} empty={n_empty}")
    print(f"Total tokens: in={total_in:,} out={total_out:,}")
    print(f"Total bad insights (validation rejected): {total_bad}")


if __name__ == "__main__":
    main()
