"""Pass 2 — per-episode structured summary via mimo-v2.5-pro.

Output: backend/data/podcasts/_processed/episode_summaries.jsonl (one row per episode)

Resumable: skips eids already in the JSONL.
"""
import json
import os
import sys
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "backend/data/podcasts"
TRANSCRIPTS = DATA / "transcripts"
META = DATA / "_meta"
PROC = DATA / "_processed"
OUT = PROC / "episode_summaries.jsonl"
DEBUG = PROC / "_debug"
DEBUG.mkdir(parents=True, exist_ok=True)

KEY = os.environ["MIMO_API_KEY"]
URL = "https://token-plan-sgp.xiaomimimo.com/v1/chat/completions"
MODEL = "mimo-v2.5-pro"

term_dict = json.loads((PROC / "term_dict.json").read_text())
CANON_COMPANIES = [c["canonical"] for c in term_dict["companies"]]
CANON_ROLES = [r["canonical"] for r in term_dict["roles"]]
CANON_SECTORS = [s["canonical"] for s in term_dict["sectors"]]

SYS = f"""你是金融行业播客分析专家。从一集中文金融职业播客转录文本中提取结构化摘要。

输出严格 JSON，字段：
- topic_one_liner: 一句话定位本集主题（≤25字）
- summary_500: 500字以内摘要，覆盖核心议题、嘉宾观点、有价值的具体信息
- covers_role: 本集涉及的金融岗位（参考下面的 canonical 列表，相同含义请用 canonical 名）
- covers_company: 本集涉及的金融机构（参考 canonical 列表）
- covers_sector: 本集涉及的子赛道（参考 canonical 列表）
- guests: 嘉宾列表 [{{"name": "嘉宾姓名/昵称", "background": "嘉宾背景一句话"}}], 没明确嘉宾就空数组
- hot_takes: 3-5 条金句，每条 ≤80 字，必须能"独立成立"（脱离上下文也能看懂），优先选反共识/具体场景/可量化建议
- audience: 这集对哪类求职者最有价值（≤20字，如"想入投行的应届生"/"卖方研究员转买方"）

Canonical 列表（你的 covers_* 字段尽量使用这些标准名）：
- companies: {', '.join(CANON_COMPANIES)}
- roles: {', '.join(CANON_ROLES)}
- sectors: {', '.join(CANON_SECTORS)}

注意：
- 对话型节目主持人是「大力」/「王大力」，guests 列表里**不要包括主持人**。
- 单口/无嘉宾就 guests=[]，不要瞎编。
- 转录可能有少量 ASR 错误，根据上下文推断真实意思。"""

def get_done():
    if not OUT.exists():
        return set()
    eids = set()
    for line in OUT.read_text().splitlines():
        if line.strip():
            eids.add(json.loads(line)["eid"])
    return eids

def load_episode(eid):
    txt = (TRANSCRIPTS / f"{eid}.txt").read_text()
    meta = json.loads((META / f"{eid}.meta.json").read_text())
    return txt, meta

def call_llm(eid, txt, meta):
    user_msg = f"""节目: {meta.get('show','?')}
单集: {meta.get('title','?')}
时长: {meta.get('duration_sec',0)//60} 分钟

转录文本：
{txt}"""
    body = json.dumps({
        "model": MODEL,
        "messages": [{"role": "system", "content": SYS}, {"role": "user", "content": user_msg}],
        "temperature": 0.0,
        "max_tokens": 4096,
        "response_format": {"type": "json_object"},
    }).encode("utf-8")
    req = urllib.request.Request(
        URL, data=body,
        headers={"Authorization": f"Bearer {KEY}", "Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=180) as r:
        resp = json.load(r)
    content = resp["choices"][0]["message"]["content"]
    try:
        data = json.loads(content)
    except Exception as e:
        (DEBUG / f"{eid}__pass2.raw.txt").write_text(content)
        raise RuntimeError(f"{eid} JSON parse failed: {e}")
    return data, resp.get("usage", {})

def process(eid):
    try:
        txt, meta = load_episode(eid)
        data, usage = call_llm(eid, txt, meta)
        row = {
            "eid": eid,
            "show": meta.get("show"),
            "title": meta.get("title"),
            "duration_min": (meta.get("duration_sec") or 0) // 60,
            **data,
            "_usage": usage,
        }
        return ("ok", eid, row, None)
    except Exception as e:
        return ("err", eid, None, str(e))

def main():
    done = get_done()
    all_eids = sorted(p.stem for p in TRANSCRIPTS.glob("*.txt"))
    todo = [e for e in all_eids if e not in done]
    print(f"Done: {len(done)} / Todo: {len(todo)}")
    if not todo:
        print("Nothing to do.")
        return

    out_handle = OUT.open("a")
    total_in, total_out = 0, 0
    t0 = time.time()
    n_ok, n_err = 0, 0
    with ThreadPoolExecutor(max_workers=4) as ex:
        for fut in as_completed([ex.submit(process, e) for e in todo]):
            status, eid, row, err = fut.result()
            if status == "ok":
                out_handle.write(json.dumps(row, ensure_ascii=False) + "\n")
                out_handle.flush()
                u = row.get("_usage", {})
                total_in += u.get("prompt_tokens", 0)
                total_out += u.get("completion_tokens", 0)
                n_ok += 1
                print(f"  ✓ {eid} {row.get('topic_one_liner','')[:40]}  (in={u.get('prompt_tokens')}/out={u.get('completion_tokens')})")
            else:
                n_err += 1
                print(f"  ✗ {eid} {err[:120]}")
    out_handle.close()
    dt = time.time() - t0
    print(f"\nDone in {dt:.0f}s. ok={n_ok} err={n_err}")
    print(f"Total tokens: in={total_in:,} out={total_out:,}")

if __name__ == "__main__":
    main()
