import re
from dataclasses import dataclass
from typing import Any, Callable

from sqlalchemy.orm import Session

from app.models import Job, JobIntelSnapshot
from app.schemas_resume_copilot import (
    ResumePreferencePayload,
    ResumeProfilePayload,
    ResumeRecommendationItem,
)
from app.services.resume_copilot.quick_enrichment import search_web as _search_web
from app.services.resume_copilot.recommendation import compute_company_priority


@dataclass
class ToolResult:
    summary: str
    data: Any = None


def build_tools(
    db: Session,
    profile: ResumeProfilePayload,
    preferences: ResumePreferencePayload | None,
    candidates: list[ResumeRecommendationItem],
) -> dict[str, Callable]:
    """Returns a dict of tool_name → callable. Each callable matches its spec args."""

    def search_candidates(query: str, filters: dict | None = None) -> ToolResult:
        query_lower = query.lower()
        tokens = {t for t in re.findall(r'[\u4e00-\u9fff]+|[a-z0-9]+', query_lower) if len(t) > 1}
        results: list[ResumeRecommendationItem] = []
        for item in candidates:
            text = ' '.join([
                item.company, item.job_title, item.location,
                item.company_priority_label or '',
                item.matched_track_label or '',
                item.matched_role_family or '',
            ]).lower()
            if not tokens or any(tok in text for tok in tokens):
                if filters and 'track' in filters:
                    tf = filters['track'].lower()
                    tier = (item.company_priority_tier or '').lower()
                    track_key = (item.matched_track_key or '').lower()
                    if tf not in tier and tf not in track_key:
                        continue
                results.append(item)
        results.sort(key=lambda x: x.base_match_score, reverse=True)
        top = results[:20]
        rows = [
            {
                'job_id': i.job_id,
                'company': i.company,
                'job_title': i.job_title,
                'location': i.location,
                'rule_score': i.base_match_score,
                'company_tier': i.company_priority_label or '',
                'need_enrichment': i.need_enrichment,
            }
            for i in top
        ]
        return ToolResult(
            summary=f'召回 {len(top)} 个匹配岗位（共 {len(results)} 个候选）',
            data=rows,
        )

    def inspect_jobs(job_ids: list[str]) -> ToolResult:
        ids = job_ids[:5]
        rows = db.query(Job).filter(Job.job_id.in_(ids)).all()
        job_map = {str(j.job_id): j for j in rows}
        details = []
        for jid in ids:
            job = job_map.get(jid)
            if not job:
                continue
            details.append({
                'job_id': jid,
                'company': job.company,
                'job_title': job.job_title,
                'department': job.department or '',
                'job_req': (job.job_req or '')[:800],
                'job_duty': (job.job_duty or '')[:800],
            })
        return ToolResult(
            summary=f'读取 {len(details)} 个岗位完整 JD',
            data=details,
        )

    def get_company_intel(company_name: str) -> ToolResult:
        job = db.query(Job).filter(Job.company.like(f'%{company_name}%')).first()
        if not job:
            return ToolResult(summary=f'未找到公司「{company_name}」的记录', data={})
        priority = compute_company_priority(job)
        snapshot = (
            db.query(JobIntelSnapshot)
            .filter(JobIntelSnapshot.job_id == job.id)
            .order_by(JobIntelSnapshot.generated_at.desc())
            .first()
        )
        data = {
            'company': company_name,
            'tier': priority.tier,
            'tier_label': priority.label,
            'category': priority.category_label,
            'high_info_asymmetry': priority.high_info_asymmetry,
            'cached_summary': str(snapshot.summary_text or '') if snapshot else '',
        }
        summary = f'{company_name}：{priority.label or "未收录"}'
        if priority.high_info_asymmetry:
            summary += '（高信息不对称）'
        if snapshot:
            summary += '，有缓存情报'
        return ToolResult(summary=summary, data=data)

    def search_web(query: str) -> ToolResult:
        results = _search_web(query, max_results=4)
        rows = [{'title': r.title, 'url': r.url, 'snippet': r.snippet} for r in results]
        return ToolResult(
            summary=f'搜索到 {len(rows)} 条外部结果',
            data=rows,
        )

    return {
        'search_candidates': search_candidates,
        'inspect_jobs': inspect_jobs,
        'get_company_intel': get_company_intel,
        'search_web': search_web,
    }
