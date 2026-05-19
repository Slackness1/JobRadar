"""Pass 3 — extract typed insights from episodes via mimo-v2.5-pro.

Schema per insight:
- id, source_eid
- type: list[str] from {role_insight, resume_tip, interview_qa, company_anecdote, industry_trend}
- role_target, company_target, sector_target: list[str]
- content: structured conclusion
- source_quote: verbatim quote from transcript
- speaker: guest | host | unknown
- confidence: high | med | low

Output: backend/data/podcasts/_processed/insights.jsonl

Usage:
    MIMO_API_KEY=... python scripts/podcast_pass3_extract.py [--sample N] [--eids id1,id2,...]
"""
import argparse
import json
import os
import re
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
SUMMARIES = PROC / "episode_summaries.jsonl"
OUT = PROC / "insights.jsonl"
DEBUG = PROC / "_debug"
DEBUG.mkdir(parents=True, exist_ok=True)

KEY = os.environ.get("MIMO_API_KEY")
MIMO_URL = "https://token-plan-sgp.xiaomimimo.com/v1/chat/completions"
MIMO_MODEL = "mimo-v2.5-pro"

# DeepSeek fallback for content-filter rejections
def _env(k):
    for p in [ROOT/"backend/.env.local", ROOT/"backend/.env"]:
        if p.exists():
            for line in p.read_text().splitlines():
                if line.startswith(f"{k}="):
                    return line.split("=",1)[1].strip().strip('"').strip("'")
    return None
DS_KEY = _env("DEEPSEEK_API_KEY") or _env("RESUME_COPILOT_API_KEY")
DS_URL = (_env("DEEPSEEK_BASE_URL") or _env("RESUME_COPILOT_BASE_URL") or "https://api.deepseek.com/v1") + "/chat/completions"
DS_MODEL = "deepseek-chat"

term_dict = json.loads((PROC / "term_dict.json").read_text())
CANON_COMPANIES = [c["canonical"] for c in term_dict["companies"]]
CANON_ROLES = [r["canonical"] for r in term_dict["roles"]]
CANON_SECTORS = [s["canonical"] for s in term_dict["sectors"]]

VALID_TYPES = {"role_insight", "resume_tip", "interview_qa", "company_anecdote", "industry_trend"}
VALID_SPEAKER = {"guest", "host", "unknown"}
VALID_CONF = {"high", "med", "low"}

SYS = f"""你是金融求职播客知识抽取专家。从一集中文金融播客转录文本中抽取**类型化 insight 记录**，供 RAG 召回喂给岗位推荐 / 简历修改 / 模拟面试三个下游使用。

抽取规则：
- 一集通常产出 8-25 条 insight，宁缺勿滥
- 每条必须有真正可被下游 RAG 检索的价值，避免抽空话/套话
- 每条必须有 source_quote（**逐字**从转录里摘取，可以是句子或短段，10-200字），不能改写

5 种 type（一条可同时属于 1-3 种，用 list）：
- role_insight: 关于具体金融岗位的"日常做什么/进阶路径/薪资段/技能要求"
- resume_tip: 关于"什么样的简历/经历能/不能进金融"，含反例
- interview_qa: 真实面试问题、常见考点、面试套路、避坑提醒
- company_anecdote: 具体公司的 culture / 八卦 / 真实故事
- industry_trend: 赛道冷热、政策影响、近 1-3 年的行业变化

confidence 三档：
- high: 嘉宾亲身经历（"我在 GS IBD 做了 3 年..."）或主持人作为业内人的明确判断
- med: 嘉宾观察但二手（"我朋友在 MS, 听说他们..."）
- low: hearsay / 推测（"听说现在..."）

speaker：
- 转录里 [spk0] / [spk1] 标签是 ASR 的说话人编号
- 根据 system 提供的「主持人」和「嘉宾」名字，推断每段是谁说的
- 单口集 speaker = "host"
- 实在判断不出 speaker = "unknown"

role_target / company_target / sector_target：
- 必填，但允许 list 为空
- 尽量用 canonical 名（见下）
- 一条 insight 涉及多个 role/company 全列出

Canonical 列表：
- companies: {', '.join(CANON_COMPANIES)}
- roles: {', '.join(CANON_ROLES)}
- sectors: {', '.join(CANON_SECTORS)}

输出严格 JSON：{{"insights": [...]}} 数组，每条字段:
{{
  "type": ["role_insight"],            // list of 1-3
  "role_target": ["机构销售"],
  "company_target": ["中信证券"],
  "sector_target": ["卖方研究"],
  "content": "...",                    // ≤120字 结构化结论
  "source_quote": "...",               // 逐字原文 10-200字
  "speaker": "guest",
  "confidence": "high"
}}"""

def get_summary_for_eid(eid):
    for line in SUMMARIES.read_text().splitlines():
        if line.strip():
            r = json.loads(line)
            if r["eid"] == eid:
                return r
    return None

def load_transcript_with_speakers(eid):
    return (TRANSCRIPTS / f"{eid}.txt").read_text()

def get_done_eids():
    if not OUT.exists():
        return set()
    return {json.loads(l)["source_eid"] for l in OUT.read_text().splitlines() if l.strip()}

def call_llm(payload_body, *, use_deepseek=False):
    url, key, model = (DS_URL, DS_KEY, DS_MODEL) if use_deepseek else (MIMO_URL, KEY, MIMO_MODEL)
    payload_body["model"] = model
    body = json.dumps(payload_body).encode("utf-8")
    req = urllib.request.Request(
        url, data=body,
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=240) as r:
        return json.load(r)

def _load_host(eid: str) -> str:
    """Read host from META/{eid}.meta.json (recorded by transcribe_apple.py)."""
    meta_path = META / f"{eid}.meta.json"
    if meta_path.exists():
        try:
            m = json.loads(meta_path.read_text())
            host = (m.get("host") or "").strip()
            if host:
                return host
        except Exception:
            pass
    return "(主持人未知)"


def build_user_msg(eid, summary, transcript):
    show = summary.get("show") or "?"
    title = summary.get("title") or "?"
    topic = summary.get("topic_one_liner") or "?"
    guests = summary.get("guests") or []
    guests_str = "; ".join(f"{g.get('name','?')}({g.get('background','?')[:40]})" for g in guests) or "(无嘉宾，主持人单口)"
    host = _load_host(eid)
    return f"""节目: {show}
单集: {title}
主题: {topic}
主持人: {host}
嘉宾: {guests_str}

转录文本（[spkN] 是 ASR 说话人编号）：
{transcript}"""

def validate_insight(ins):
    """Return cleaned insight dict, or raise ValueError."""
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

PRIMARY_DEEPSEEK = False  # set in main() from CLI flag

def process(eid):
    summary = get_summary_for_eid(eid)
    if not summary:
        return ("skip-no-summary", eid, [], None)
    transcript = load_transcript_with_speakers(eid)
    user_msg = build_user_msg(eid, summary, transcript)
    payload = {
        "messages": [{"role": "system", "content": SYS}, {"role": "user", "content": user_msg}],
        "temperature": 0.0,
        "max_tokens": 8192,
        "response_format": {"type": "json_object"},
    }
    primary_is_ds = PRIMARY_DEEPSEEK
    used_provider = "deepseek" if primary_is_ds else "mimo"
    try:
        resp = call_llm(payload, use_deepseek=primary_is_ds)
    except urllib.error.HTTPError as e:
        # Cross-provider fallback for content filter / quota issues
        other_key_present = KEY if primary_is_ds else DS_KEY
        if e.code in (400, 429) and other_key_present:
            try:
                resp = call_llm(payload, use_deepseek=not primary_is_ds)
                used_provider = ("mimo-fallback" if primary_is_ds else "deepseek-fallback")
            except Exception as e2:
                return ("err", eid, [], f"both providers failed: primary={e}; other={e2}")
        else:
            return ("err", eid, [], f"http {e.code}: {str(e.read())[:200] if hasattr(e,'read') else e}")
    except Exception as e:
        return ("err", eid, [], str(e))
    content = resp["choices"][0]["message"]["content"]
    # MiMo content filter sometimes returns 200 with rejection text — try the other provider
    other_key_present = KEY if primary_is_ds else DS_KEY
    if used_provider in ("mimo", "deepseek") and other_key_present and ("high risk" in content or len(content.strip()) < 30):
        try:
            resp = call_llm(payload, use_deepseek=not primary_is_ds)
            content = resp["choices"][0]["message"]["content"]
            used_provider = ("mimo-fallback" if primary_is_ds else "deepseek-fallback")
        except Exception as e:
            (DEBUG / f"{eid}__pass3.raw.txt").write_text(content)
            return ("err", eid, [], f"primary rejected, fallback failed: {e}")
    try:
        data = json.loads(content)
    except Exception as e:
        (DEBUG / f"{eid}__pass3.raw.txt").write_text(content)
        return ("err", eid, [], f"JSON parse: {e}")
    raw_list = data.get("insights") if isinstance(data, dict) else data
    if not isinstance(raw_list, list):
        (DEBUG / f"{eid}__pass3.raw.txt").write_text(content)
        return ("err", eid, [], "no insights array")
    valid = []
    bad = []
    for i, ins in enumerate(raw_list):
        try:
            cleaned = validate_insight(ins)
            cleaned["id"] = f"ins_{eid[:8]}_{i:03d}"
            cleaned["source_eid"] = eid
            cleaned["_provider"] = used_provider
            valid.append(cleaned)
        except ValueError as e:
            bad.append({"idx": i, "err": str(e), "raw": ins})
    if bad:
        (DEBUG / f"{eid}__pass3.bad.json").write_text(json.dumps(bad, ensure_ascii=False, indent=2))
    usage = resp.get("usage", {})
    return ("ok", eid, valid, {"usage": usage, "bad": len(bad), "provider": used_provider})

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sample", type=int, default=0, help="run on N sample eids only")
    ap.add_argument("--eids", type=str, default="", help="comma-separated eids to run")
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--use-deepseek", action="store_true", help="DeepSeek primary, mimo fallback (default: mimo primary)")
    args = ap.parse_args()

    global PRIMARY_DEEPSEEK
    PRIMARY_DEEPSEEK = args.use_deepseek
    if PRIMARY_DEEPSEEK:
        if not DS_KEY:
            print("DEEPSEEK_API_KEY not set (or RESUME_COPILOT_API_KEY)", file=sys.stderr); sys.exit(1)
    else:
        if not KEY:
            print("MIMO_API_KEY not set", file=sys.stderr); sys.exit(1)

    done = get_done_eids()
    all_eids = sorted({json.loads(l)["eid"] for l in SUMMARIES.read_text().splitlines() if l.strip()})

    if args.eids:
        todo = [e for e in args.eids.split(",") if e.strip() and e.strip() not in done]
    elif args.sample:
        # Pick a diverse sample by hand
        sample_eids = [
            "6584142e3d1caa927aeb2dcb",  # vol.27 机构销售 (long guest)
            "66af341233ddcbb53c2b821f",  # vol.42 投行少爷 (news + reaction)
            "6850dc1a2a38b4d979082ad2",  # vol.62 卖方研究的肉与骨 (history)
            "67e51c076ea600223521fb27",  # vol.55 退休投行MD (memoir)
            "688b48b8edf3fa32d5737db4",  # vol.66 裁员潮 (multi-guest)
        ]
        todo = [e for e in sample_eids[:args.sample] if e not in done]
    else:
        todo = [e for e in all_eids if e not in done]

    print(f"Done: {len(done)} / Todo: {len(todo)}")
    if not todo:
        return

    out_handle = OUT.open("a")
    n_ok = n_err = total_in = total_out = total_bad = 0
    by_provider = {"mimo": 0, "deepseek": 0, "mimo-fallback": 0, "deepseek-fallback": 0}
    t0 = time.time()
    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        for fut in as_completed([ex.submit(process, e) for e in todo]):
            status, eid, insights, info = fut.result()
            if status == "ok":
                for ins in insights:
                    out_handle.write(json.dumps(ins, ensure_ascii=False) + "\n")
                out_handle.flush()
                u = info["usage"]
                total_in += u.get("prompt_tokens", 0)
                total_out += u.get("completion_tokens", 0)
                total_bad += info["bad"]
                by_provider[info["provider"]] = by_provider.get(info["provider"], 0) + 1
                n_ok += 1
                tag_map = {"deepseek": " (DS)", "mimo": " (MM)", "deepseek-fallback": " (DS-fb)", "mimo-fallback": " (MM-fb)"}
                tag = tag_map.get(info["provider"], "")
                print(f"  ✓ {eid} {len(insights):>3} insights{tag}  bad={info['bad']:>2}  in={u.get('prompt_tokens')}/out={u.get('completion_tokens')}")
            else:
                n_err += 1
                print(f"  ✗ {eid} {status}: {info[:140] if info else ''}")
    out_handle.close()
    dt = time.time() - t0
    print(f"\nDone in {dt:.0f}s. ok={n_ok} err={n_err}")
    print(f"Total tokens: in={total_in:,} out={total_out:,}")
    print(f"Total bad insights (validation rejected): {total_bad}")
    print(f"By provider: {by_provider}")

if __name__ == "__main__":
    main()
