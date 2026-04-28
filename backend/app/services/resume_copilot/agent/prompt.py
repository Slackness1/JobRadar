import json

from app.schemas_resume_copilot import (
    DirectionTierResult,
    ResumePreferencePayload,
    ResumeProfilePayload,
    ResumeRecommendationItem,
)
from app.services.resume_copilot.agent.budget import AgentBudget
from app.services.resume_copilot.redact import redact_profile_for_llm


def _summarize_profile(profile: ResumeProfilePayload) -> str:
    profile = redact_profile_for_llm(profile)
    parts: list[str] = []
    if profile.basic_info:
        parts.append(f"基本信息：{json.dumps(profile.basic_info, ensure_ascii=False)}")
    if profile.education:
        edu = profile.education[0]
        parts.append(f"学历：{edu.school} {edu.degree} {edu.major}")
    if profile.internships:
        names = [f"{i.company}（{i.role}）" for i in profile.internships[:3]]
        parts.append(f"实习经历：{', '.join(names)}")
    if profile.inferred_roles:
        parts.append(f"推断职能方向：{', '.join(profile.inferred_roles[:5])}")
    if profile.inferred_tracks:
        parts.append(f"推断赛道：{', '.join(profile.inferred_tracks[:3])}")
    if profile.candidate_summary:
        parts.append(f"综合评估：{profile.candidate_summary}")
    return '\n'.join(parts) or '（简历信息不足）'


def _summarize_preferences(preferences: ResumePreferencePayload | None) -> str:
    if not preferences or preferences.all_skipped:
        return '未指定偏好'
    parts: list[str] = []
    if preferences.preferred_locations:
        parts.append(f"期望城市：{', '.join(preferences.preferred_locations)}")
    if preferences.preferred_tracks:
        parts.append(f"目标赛道：{', '.join(preferences.preferred_tracks)}")
    if preferences.preferred_roles:
        parts.append(f"目标职能：{', '.join(preferences.preferred_roles)}")
    if preferences.preferred_company_types:
        parts.append(f"目标公司类型：{', '.join(preferences.preferred_company_types)}")
    return '\n'.join(parts) or '未指定偏好'


def _summarize_candidates(candidates: list[ResumeRecommendationItem]) -> str:
    rows = [
        {
            'rank': i + 1,
            'job_id': item.job_id,
            'company': item.company,
            'job_title': item.job_title,
            'location': item.location,
            'base_match_score': item.base_match_score,
            'company_tier': item.company_priority_label or '',
            'need_enrichment': item.need_enrichment,
        }
        for i, item in enumerate(candidates[:100])
    ]
    return json.dumps(rows, ensure_ascii=False)


def _format_direction_tiers(direction_results: list[DirectionTierResult]) -> str:
    lines = []
    for r in direction_results:
        tier_emoji = '🟢' if r.tier == 1 else '🟡' if r.tier == 2 else '🔴'
        hint = ''
        if r.tier == 1:
            hint = '— 优先在 finalize 中推荐此方向岗位'
        elif r.tier == 2:
            hint = '— 包含部分此方向岗位；在 why_recommended 中注明可迁移性'
        else:
            hint = '— 只包含入门级/容忍度高的岗位；在 finalize 的 target_direction 中标注'
        lines.append(f"{tier_emoji} {r.direction}: 第{r.tier}层 ({r.tier_label}) {hint}")
    return '\n'.join(lines)


def build_system_prompt(
    profile: ResumeProfilePayload,
    preferences: ResumePreferencePayload | None,
    candidates: list[ResumeRecommendationItem],
    budget: AgentBudget,
    direction_results: list[DirectionTierResult] | None = None,
) -> str:
    r = budget.remaining()
    direction_section = ''
    if direction_results:
        direction_section = f"""
## 方向层级分析
{_format_direction_tiers(direction_results)}
在 finalize 的每个推荐岗位中，请根据上述层级设置 target_direction 字段（例如 "投研"）。

"""
    return f"""你是一个专业的校招求职顾问，正在帮助一名中国大学生匹配最适合的岗位。

## 候选人画像
{_summarize_profile(profile)}

## 求职偏好
{_summarize_preferences(preferences)}
{direction_section}
## 候选岗位池（规则引擎预筛 top-100，按规则分降序）
{_summarize_candidates(candidates)}

## 你的任务
从候选池中挑选 8-15 个最匹配的岗位，给出排序和每个岗位的推荐理由。

## 工具预算（每轮动态更新）
- search_candidates: 剩余 {r.get('search_candidates', 0)} 次
- inspect_jobs: 剩余 {r.get('inspect_jobs', 0)} 次
- get_company_intel: 剩余 {r.get('get_company_intel', 0)} 次
- search_web: 剩余 {r.get('search_web', 0)} 次
- finalize: 剩余 {r.get('finalize', 0)} 次（必须调用，结束分析）

## 工具参数规格（严格使用以下参数名，不得自定义或增减）
- search_candidates: {{"query": "搜索词字符串", "filters": {{"track": "赛道"}} 或 null}}
- inspect_jobs:      {{"job_ids": ["id1", "id2"]}}  ← 最多5个，job_id 来自候选池
- get_company_intel: {{"company_name": "单个公司名字符串"}}  ← 每次只查一家
- search_web:        {{"query": "搜索词字符串"}}
- finalize:          {{"recommendations": [{{"job_id": "...", "final_score": 85, "why_recommended": [...], "strengths": [...], "risks": [...], "target_direction": "目标方向名"}}]}}

## 输出格式（每轮严格返回 JSON）
{{"thought": "...", "action": "工具名", "args": {{...}}, "reasoning_display": "..."}}

## 行为规则
1. reasoning_display 用中文、用"你"称呼候选人，一句话，面向候选人展示
2. 有足够依据时尽早 finalize，不要为了用完预算而无意义搜索
3. 对高信息不对称赛道（券商/银行/国央企）优先调 get_company_intel，每次只传一个 company_name
4. search_web 只用于真正模糊的岗位，不对每个岗位都搜
5. 预算耗尽时立即 finalize，不要报错"""
