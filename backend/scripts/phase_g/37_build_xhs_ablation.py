"""XHS rerank 消融输入构建(扩展版)。

每个(persona,岗位)对捕获三种证据变体,用于拆解"到底是哪种证据在帮/在害":
  - ev_prod    : 生产实际注入 = fetch_for_job(company,title,k=3),语义取证(多为泛化,偶尔本公司)
  - ev_company : 本公司证据 = company_target_json 含该公司(XHS 最佳情形)
  - ev_generic : 泛化证据 = 命中 persona 角色关键词、但 company_target 不含该公司(别家/通用)

输出 /tmp/xhs_ablation_in.json,给判官按 4 臂(none / +prod / +company / +generic)打分。
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from app.database import SessionLocal
from app.models import Job
from app.services.xhs import context as xhs_ctx

PERSONAS = [
    ("公募行研学生(消费/医药买方投研)", "公募基金 行业研究员 买方", ["研究", "投研"],
     ["华夏基金", "易方达基金", "招商基金", "中欧基金", "广发基金", "南方基金", "汇添富"]),
    ("卖方研究 TMT 学生", "券商研究所 TMT 行业分析师", ["研究", "分析师"],
     ["中信证券", "华泰证券", "国泰海通", "国信证券", "兴业证券", "招商证券", "中信建投"]),
    ("量化私募 中频策略学生", "量化研究员 中频 alpha因子", ["量化", "策略", "研究"],
     ["幻方量化", "九坤投资", "鸣石", "衍复", "灵均", "宽德"]),
    ("投行 IBD 学生", "投行 IPO 承做", ["投行", "承做", "IBD"],
     ["中金公司", "中信证券", "国金证券", "中信建投", "海通证券"]),
    ("AI 算法学生(大模型)", "大模型 算法工程师", ["算法", "大模型", "AI"],
     ["腾讯", "字节跳动", "网易", "美团", "快手", "百度", "阿里"]),
    ("互联网后端研发学生", "后端开发 分布式 工程师", ["研发", "开发", "后端"],
     ["腾讯", "字节跳动", "美团", "阿里", "网易"]),
]
_ROLE_KW = {  # persona → 泛化证据匹配的角色词(content LIKE)
    "研究": ["研究", "投研", "分析师"], "量化": ["量化", "策略"],
    "投行": ["投行", "承做", "IPO"], "算法": ["算法", "大模型", "AI"], "研发": ["开发", "后端", "工程师"],
}


def _company_ev(cur, comp, k=3):
    rows = cur.execute(
        "SELECT primary_type, content FROM xhs_insights WHERE company_target_json LIKE ? "
        "ORDER BY CASE confidence WHEN 'high' THEN 0 WHEN 'med' THEN 1 ELSE 2 END LIMIT ?",
        (f"%{comp}%", k)).fetchall()
    return [f"- [{pt or ''}] {c[:120]}" for pt, c in rows if c]


def _generic_ev(cur, kw, comp, k=3):
    words = []
    for w in kw:
        words += _ROLE_KW.get(w, [w])
    seen, out = set(), []
    for w in set(words):
        for pt, c, ct in cur.execute(
            "SELECT primary_type, content, company_target_json FROM xhs_insights "
            "WHERE content LIKE ? AND (company_target_json IS NULL OR company_target_json NOT LIKE ?) "
            "ORDER BY CASE confidence WHEN 'high' THEN 0 WHEN 'med' THEN 1 ELSE 2 END LIMIT ?",
            (f"%{w}%", f"%{comp}%", k)).fetchall():
            if c and c not in seen:
                seen.add(c); out.append(f"- [{pt or ''}] {c[:120]}")
            if len(out) >= k:
                break
        if len(out) >= k:
            break
    return out


def main():
    db = SessionLocal()
    cur = sqlite3.connect("data/jobradar.db").cursor()
    pairs = []
    for blurb, query, kw, companies in PERSONAS:
        for comp in companies:
            ev_company = _company_ev(cur, comp, 3)
            if not ev_company:
                continue
            q = (db.query(Job).filter(Job.company.like(f"%{comp}%"),
                                      Job.quality_label.in_(("good", "internship_only")))
                 .filter((Job.job_duty != None) | (Job.job_req != None)))  # noqa: E711
            job = None
            for cand in q.limit(50):
                if any(w in ((cand.job_title or "") + (cand.sub_category or "")) for w in kw):
                    job = cand; break
            job = job or q.first()
            if job is None:
                continue
            prod = xhs_ctx.fetch_for_job(db, company=job.company or comp, job_title=job.job_title or "", k=3)
            ev_prod = [f"- [{i.get('primary_type','')}] {(i.get('content') or '')[:120]}" for i in prod]
            pairs.append({
                "persona": blurb, "query": query, "company": job.company,
                "title": job.job_title or "",
                "jd": ((job.job_duty or "") + " " + (job.job_req or "")).strip()[:400],
                "ev_prod": "\n".join(ev_prod),
                "ev_company": "\n".join(ev_company),
                "ev_generic": "\n".join(_generic_ev(cur, kw, comp, 3)),
            })
    Path("/tmp/xhs_ablation_in.json").write_text(json.dumps(pairs, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"构建 {len(pairs)} 对 → /tmp/xhs_ablation_in.json")
    for p in pairs:
        print(f"  {p['company'][:12]:12s} | {p['title'][:20]:20s} | prod{len(p['ev_prod'].splitlines())} comp{len(p['ev_company'].splitlines())} gen{len(p['ev_generic'].splitlines())}")
    db.close()


if __name__ == "__main__":
    main()
