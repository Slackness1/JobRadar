"""XHS rerank ablation 输入构建:挑"有本公司小红书证据"的(persona,岗位)对,导出证据块。

对每个 persona 的目标公司,找一个该公司在池里的岗 + 用 fetch_for_job 取证据(I-A 已带 company_match_kind),
只保留本公司(exact/alias)证据。输出 /tmp/xhs_ablation_in.json 给 sonnet subagent 跑 with/without 两臂。
"""
from __future__ import annotations

import json
from pathlib import Path

import sqlite3

from app.database import SessionLocal
from app.models import Job

# (persona 描述, 意图, 该 persona 关注的 sub_cat 关键词, 目标公司列表)
PERSONAS = [
    ("公募行研学生(消费/医药买方投研)", "公募基金 行业研究员 买方", ["研究", "投研"], ["华夏基金", "易方达基金", "招商基金", "中欧基金"]),
    ("卖方研究 TMT 学生", "券商研究所 TMT 行业分析师", ["研究", "分析师"], ["中信证券", "华泰证券", "国泰海通", "国信证券", "兴业证券"]),
    ("量化私募 中频策略学生", "量化研究员 中频 alpha因子", ["量化", "策略", "研究"], ["幻方量化", "九坤投资", "鸣石"]),
    ("投行 IBD 学生", "投行 IPO 承做", ["投行", "承做", "IBD"], ["中金公司", "中信证券", "国金证券"]),
    ("AI 算法学生(大模型)", "大模型 算法工程师", ["算法", "大模型", "AI"], ["腾讯", "字节跳动", "网易", "美团"]),
]


def _company_evidence(cur, comp: str, k: int = 4) -> list[str]:
    """直接按公司名查 xhs_insights 的本公司证据(company_target_json 含该公司),按 confidence 取前 k。"""
    rows = cur.execute(
        "SELECT primary_type, content, confidence FROM xhs_insights "
        "WHERE company_target_json LIKE ? "
        "ORDER BY CASE confidence WHEN 'high' THEN 0 WHEN 'med' THEN 1 ELSE 2 END LIMIT ?",
        (f"%{comp}%", k * 2),
    ).fetchall()
    out = []
    for pt, content, _ in rows[:k]:
        if content:
            out.append(f"- [{pt or ''}] {content[:120]}")
    return out


def main():
    db = SessionLocal()
    cur = sqlite3.connect("data/jobradar.db").cursor()
    pairs = []
    for blurb, query, kw, companies in PERSONAS:
        for comp in companies:
            evidence = _company_evidence(cur, comp, k=4)
            if not evidence:
                continue
            # 挑该公司一个 persona 对口的岗(title/sub_cat 命中关键词);没有就退而求其次取任一 good 岗
            q = (db.query(Job)
                 .filter(Job.company.like(f"%{comp}%"),
                         Job.quality_label.in_(("good", "internship_only")))
                 .filter((Job.job_duty != None) | (Job.job_req != None)))  # noqa: E711
            job = None
            for cand in q.limit(40):
                blob = (cand.job_title or "") + (cand.sub_category or "")
                if any(w in blob for w in kw):
                    job = cand
                    break
            if job is None:
                job = q.first()
            if job is None:
                continue
            pairs.append({
                "persona": blurb, "query": query,
                "company": job.company, "title": job.job_title or "",
                "jd": ((job.job_duty or "") + " " + (job.job_req or "")).strip()[:400],
                "xhs_evidence": "\n".join(evidence), "n_evidence": len(evidence),
            })
    Path("/tmp/xhs_ablation_in.json").write_text(json.dumps(pairs, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"构建 {len(pairs)} 个有本公司XHS证据的(persona,岗位)对 → /tmp/xhs_ablation_in.json")
    for p in pairs:
        print(f"  {p['company'][:14]:14s} | {p['title'][:22]:22s} | 证据 {p['n_evidence']} 条")
    db.close()


if __name__ == "__main__":
    main()
