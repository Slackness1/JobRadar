"""Task 16: 给 Opus 选的 demo 公司挑岗位 + 用 taxonomy 标签 enrich。

输入:
- backend/data/demo_companies_v1.json (Phase E Opus 输出, 10 投研 + 8-12 AI 公司清单)
- backend/data/jobradar.db (本仓库岗位库, 32k 金融 + 互联网)
- docs/taxonomy-投研-final-v1.md (作 LLM 系统 prompt 上下文)

输出:
- backend/data/enriched_demo_jobs_v1.json
  [
    {
      "job_id": ...,
      "company": ...,
      "title": ...,
      "source": "jobradar_db" | "xhs_proxy_quote" | "manual_placeholder",
      "taxonomy_labels": {
        "strategy_type": {...},
        "industry_focus": [...],
        "institution_tier": ...,
        "sub_category": ...
      },
      "fit_signals_for_demo": "..."  # 给 demo 用的 1 句话标签
    },
    ...
  ]
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DEMO_COMPANIES_JSON = REPO_ROOT / "backend" / "data" / "demo_companies_v1.json"
TAXONOMY_MD = REPO_ROOT / "docs" / "taxonomy-投研-final-v1.md"
OUTPUT_JSON = REPO_ROOT / "backend" / "data" / "enriched_demo_jobs_v1.json"
DB_PATH = REPO_ROOT / "backend" / "data" / "jobradar.db"


def fetch_jobs_for_company(company_name: str, limit: int = 5) -> list[dict]:
    """从 jobradar.db 捞这家公司的岗位 (fuzzy match).

    jobs 表 schema: id, job_id, source, company, department, job_title, location,
    major_req, job_req, job_duty, job_stage, publish_date, detail_url, canonical_track 等.
    返回字典里把 job_title -> title, job_duty + job_req -> snippet, detail_url -> jd_url
    以便后续 enrich/match 统一字段名。
    """
    import sqlite3
    if not DB_PATH.exists():
        return []
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    # 模糊匹配 (公司全名可能 DB 里只存简称, e.g. '华夏基金管理有限公司' vs '华夏基金')
    short_name = company_name.replace("有限公司", "").replace("管理", "").replace("基金", "基金").strip()
    cur = conn.execute(
        """
        SELECT id, job_id, company, job_title, department, location, source,
               job_req, job_duty, job_stage, detail_url, canonical_track, publish_date
        FROM jobs
        WHERE (company LIKE ? OR company LIKE ?)
        ORDER BY publish_date DESC NULLS LAST
        LIMIT ?
        """,
        (f"%{short_name[:6]}%", f"%{company_name[:6]}%", limit),
    )
    rows = []
    for r in cur.fetchall():
        d = dict(r)
        d["title"] = d.get("job_title", "")
        snippet_parts = []
        if d.get("job_duty"):
            snippet_parts.append(f"职责: {d['job_duty'][:600]}")
        if d.get("job_req"):
            snippet_parts.append(f"要求: {d['job_req'][:600]}")
        d["snippet"] = " | ".join(snippet_parts)
        d["jd_url"] = d.get("detail_url", "")
        rows.append(d)
    conn.close()
    return rows


def enrich_job(job: dict, taxonomy_md: str, client) -> dict:
    """LLM 给单 job 加 taxonomy 标签。"""
    system = (
        "你是金融求职 + AI 求职双域 job tagger。给你一个 job (title + snippet + company) 和已锁定的 3 维 "
        "taxonomy。请输出该 job 在 taxonomy 各维度的 canonical 标签 + sub_category + 1 句话 fit_signals (demo 用)."
        " 严格 JSON 输出."
    )
    user_msg = f"""
## Taxonomy (锁死, 必须从中选)
{taxonomy_md[:8000]}

## Job
company: {job.get('company')}
title: {job.get('title')}
snippet: {(job.get('snippet') or '')[:1500]}

## 输出 JSON
{{
  "strategy_type": {{"canonical": "<7 大类之一>", "sub_category": "<细分>"}},
  "industry_focus": ["..."],
  "institution_tier": "<...>",
  "fit_signals_for_demo": "<1 句话标签, 给 demo 用>"
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
    if not DEMO_COMPANIES_JSON.exists():
        print(f"ERROR: {DEMO_COMPANIES_JSON} 不存在 — 先跑 Phase E (Opus synthesis) 落地 demo 公司清单",
              file=sys.stderr)
        return 1
    if not TAXONOMY_MD.exists():
        print(f"ERROR: {TAXONOMY_MD} 不存在", file=sys.stderr)
        return 1

    api_key = os.environ.get("DEEPSEEK_API_KEY") or os.environ.get("RESUME_COPILOT_API_KEY")
    if not api_key:
        print("ERROR: 缺 DEEPSEEK_API_KEY", file=sys.stderr)
        return 2
    from openai import OpenAI
    client = OpenAI(api_key=api_key, base_url="https://api.deepseek.com")

    companies_data = json.loads(DEMO_COMPANIES_JSON.read_text(encoding="utf-8"))
    taxonomy_md = TAXONOMY_MD.read_text(encoding="utf-8")

    enriched_jobs: list[dict] = []
    for company in companies_data:
        cname = company.get("name") or company.get("company")
        print(f"[{cname}] 捞岗位...")
        jobs = fetch_jobs_for_company(cname, limit=5)
        if not jobs:
            # 没找到 — 用 placeholder (XHS 帖里学生提到的 role)
            placeholder = {
                "id": f"placeholder_{cname}",
                "company": cname,
                "title": company.get("xhs_typical_role", "实习生"),
                "snippet": company.get("demo_pitch", ""),
                "source": "xhs_proxy_quote",
            }
            jobs = [placeholder]
            print(f"  ⚠ DB 无此公司岗位, 用 placeholder")
        else:
            print(f"  → DB 找到 {len(jobs)} 个岗位")
        for j in jobs:
            tags = enrich_job(j, taxonomy_md, client)
            enriched_jobs.append({
                **j,
                "taxonomy_labels": tags,
                "_demo_company_pitch": company.get("demo_pitch", ""),
            })

    OUTPUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_JSON.write_text(json.dumps(enriched_jobs, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n✓ 写到 {OUTPUT_JSON}, 共 {len(enriched_jobs)} 个 enriched job")
    return 0


if __name__ == "__main__":
    sys.exit(main())
