"""Task 15: 5 个 persona (P1/P2/P3/P6/P_self) 分类到 3 维 taxonomy。

输入:
- docs/taxonomy-投研-final-v1.md (Phase E Opus 输出)
- backend/data/personas/P{1,2,3,6,_self}.{pdf,json}

输出:
- backend/data/persona_classifications_v1.json
  {
    "P1": {
      "strategy_type": {"canonical": "基本面权益", "sub_category": "公募权益研究员", "confidence": 0.92},
      "industry_focus": ["消费", "医药"],
      "institution_tier": ["一线公募", "头部主观私募"],
      "reasoning": "...",
      "raw_signals_from_resume": [...]
    },
    ...
  }
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
TAXONOMY_MD = REPO_ROOT / "docs" / "taxonomy-投研-final-v1.md"
OUTPUT_JSON = REPO_ROOT / "backend" / "data" / "persona_classifications_v1.json"

PERSONA_IDS = ["P1", "P2", "P3", "P6", "P_self"]


def classify_persona(persona, taxonomy_md: str, client) -> dict:
    """单个 persona LLM 分类。"""
    system = (
        "你是金融求职 + AI 求职双域 taxonomy 分类器。给你一个学生 persona (简历摘要 + hidden_highlights + "
        "target_jd_anchors + persona_voice) 和已锁定的 3 维 taxonomy。请输出该 persona 在 taxonomy 各维度的 "
        "canonical 标签 + sub_category + confidence + 来自简历的 raw_signals (verbatim 截取). 严格 JSON 输出."
    )
    user_msg = f"""
## Taxonomy (锁死, 必须从中选)
{taxonomy_md[:8000]}

## Persona to classify ({persona.id})
target_jd_anchors: {persona.target_jd_anchors}
hidden_highlights: {persona.hidden_highlights}
persona_voice: {persona.persona_voice}

简历正文 (前 4000 字):
{persona.resume_text[:4000]}

## 输出 JSON schema
{{
  "strategy_type": {{
    "canonical": "<7 大类之一>",
    "sub_category": "<细分>",
    "confidence": <0-1>
  }},
  "industry_focus": ["...", "..."],
  "institution_tier": ["...", "..."],
  "reasoning": "<2-3 句话, 为什么分到这>",
  "raw_signals_from_resume": [
    {{"verbatim": "<原文 截取>", "supports": "<哪个 dimension/value>"}}
  ]
}}
"""
    resp = client.chat.completions.create(
        model="deepseek-chat",
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user_msg},
        ],
        response_format={"type": "json_object"},
        temperature=0.1,
    )
    return json.loads(resp.choices[0].message.content or "{}")


def main() -> int:
    if not TAXONOMY_MD.exists():
        print(f"ERROR: {TAXONOMY_MD} 不存在 — 先跑 Phase E (Opus synthesis)", file=sys.stderr)
        return 1

    sys.path.insert(0, str(REPO_ROOT / "backend"))
    from app.services.taxonomy_discovery.persona_loader import load_persona

    api_key = os.environ.get("DEEPSEEK_API_KEY") or os.environ.get("RESUME_COPILOT_API_KEY")
    if not api_key:
        print("ERROR: 缺 DEEPSEEK_API_KEY", file=sys.stderr)
        return 2
    from openai import OpenAI
    client = OpenAI(api_key=api_key, base_url="https://api.deepseek.com")

    taxonomy_md = TAXONOMY_MD.read_text(encoding="utf-8")

    out: dict[str, dict] = {}
    for pid in PERSONA_IDS:
        try:
            p = load_persona(pid)
        except FileNotFoundError:
            print(f"[skip] {pid}: persona file 不存在")
            continue
        print(f"分类 {pid}...")
        out[pid] = classify_persona(p, taxonomy_md, client)
        print(f"  → {out[pid].get('strategy_type', {}).get('canonical')} / "
              f"sub={out[pid].get('strategy_type', {}).get('sub_category')} / "
              f"conf={out[pid].get('strategy_type', {}).get('confidence')}")

    OUTPUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_JSON.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n✓ 写到 {OUTPUT_JSON}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
