"""Task 17: 5 persona × demo job pool 端到端匹配 + fit 度 + 推荐理由。

输入:
- backend/data/persona_classifications_v1.json (Task 15)
- backend/data/enriched_demo_jobs_v1.json   (Task 16)
- backend/data/personas/P{1,2,3,6,_self}.json (原 persona JSON, 拿 hidden_highlights / target_jd_anchors)
- docs/taxonomy-投研-final-v1.md

输出:
- backend/data/demo_match_results_v1.json
  {
    "P1": {
      "top_recommendations": [
        {
          "job_id": ..., "company": ..., "title": ...,
          "fit_score": 0.92,
          "tier_label": "强匹配 | 适配 | 可考虑",
          "narrative": "...为什么 fit, 关键证据 1-2 条...",
          "hidden_highlight_invoked": "deal size 80 亿 / 跨 3 部门"
        },
        ...
      ]
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
CLASSIFICATIONS = REPO_ROOT / "backend" / "data" / "persona_classifications_v1.json"
ENRICHED_JOBS = REPO_ROOT / "backend" / "data" / "enriched_demo_jobs_v1.json"
TAXONOMY_MD = REPO_ROOT / "docs" / "taxonomy-投研-final-v1.md"
OUTPUT_JSON = REPO_ROOT / "backend" / "data" / "demo_match_results_v1.json"


def match_for_persona(persona, persona_class: dict, jobs: list[dict], taxonomy_md: str, client) -> list[dict]:
    system = (
        "你是金融求职 + AI 求职双域匹配引擎。给你 persona 的简历 + taxonomy 分类, 和一池 enriched job. "
        "为每个 job 算 fit_score (0-1) + tier_label (强匹配/适配/可考虑/不匹配) + 1-2 句叙事, "
        "若命中 persona hidden_highlights 显式 invoke. 输出 JSON 列表, 按 fit_score 降序."
    )
    user_msg = f"""
## Persona ({persona.id})
target_jd_anchors: {persona.target_jd_anchors}
hidden_highlights: {persona.hidden_highlights}
classification: {persona_class}
简历正文 (前 3000 字):
{persona.resume_text[:3000]}

## Job Pool ({len(jobs)} 个)
{json.dumps([{k: v for k, v in j.items() if k != 'snippet'} for j in jobs], ensure_ascii=False)[:6000]}

## 输出 JSON
{{
  "results": [
    {{
      "job_id": <job.id>,
      "company": "...",
      "title": "...",
      "fit_score": <0-1>,
      "tier_label": "强匹配 | 适配 | 可考虑 | 不匹配",
      "narrative": "<1-2 句, 解释为什么 fit/不 fit, 引用具体 taxonomy dimension>",
      "hidden_highlight_invoked": "<persona hidden_highlights 里命中的 1 条, 如果没有则 null>",
      "evidence_from_persona": "<persona 简历里支持这个 fit 的 verbatim 截取>"
    }},
    ...
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
        temperature=0.2,
    )
    data = json.loads(resp.choices[0].message.content or "{}")
    return data.get("results", [])


def main() -> int:
    for f in [CLASSIFICATIONS, ENRICHED_JOBS, TAXONOMY_MD]:
        if not f.exists():
            print(f"ERROR: {f} 不存在 — 先跑前置 task", file=sys.stderr)
            return 1

    sys.path.insert(0, str(REPO_ROOT / "backend"))
    from app.services.taxonomy_discovery.persona_loader import load_persona

    api_key = os.environ.get("DEEPSEEK_API_KEY") or os.environ.get("RESUME_COPILOT_API_KEY")
    if not api_key:
        print("ERROR: 缺 DEEPSEEK_API_KEY", file=sys.stderr)
        return 2
    from openai import OpenAI
    client = OpenAI(api_key=api_key, base_url="https://api.deepseek.com")

    classifications = json.loads(CLASSIFICATIONS.read_text(encoding="utf-8"))
    enriched_jobs = json.loads(ENRICHED_JOBS.read_text(encoding="utf-8"))
    taxonomy_md = TAXONOMY_MD.read_text(encoding="utf-8")

    out: dict[str, dict] = {}
    for pid, pclass in classifications.items():
        try:
            p = load_persona(pid)
        except FileNotFoundError:
            continue
        print(f"匹配 {pid} × {len(enriched_jobs)} jobs...")
        results = match_for_persona(p, pclass, enriched_jobs, taxonomy_md, client)
        # 按 fit_score 降序, 取 top 10
        results.sort(key=lambda r: r.get("fit_score", 0), reverse=True)
        out[pid] = {"top_recommendations": results[:10], "all_results": results}
        # 简短 print
        for r in results[:3]:
            print(f"  → {r.get('company')} | {r.get('title')[:30]} | {r.get('fit_score'):.2f} | {r.get('tier_label')}")

    OUTPUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_JSON.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n✓ 写到 {OUTPUT_JSON}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
