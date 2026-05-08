import json
from typing import Any, Protocol

from urllib import request as urllib_request

from app.schemas_resume_copilot import DirectionTierResult, ResumePreferencePayload, ResumeProfilePayload
from app.services.resume_copilot.llm import build_resume_llm_client

_SYSTEM_PROMPT = """\
你是一个专业的校招求职顾问。对于候选人的每个目标方向，评估其背景与该方向的匹配程度，分为三层：
- 第1层（强匹配）：有直接相关经历
- 第2层（可迁移）：有相邻经历，经过改写可以靠近
- 第3层（有差距）：几乎没有相关背景

返回 JSON，格式为：
{"directions": [{"direction": "...", "tier": 1, "tier_label": "强匹配", "strengths": [...], "gaps": [...], "transferable_from": [...]}]}

tier_label 的取值只能是 "强匹配" / "可迁移" / "有差距"。
"""


class DirectionAnalysisProvider(Protocol):
    def analyze_directions(
        self,
        profile: ResumeProfilePayload,
        preferences: ResumePreferencePayload | None,
        directions: list[str],
    ) -> list[dict[str, Any]]: ...


class OpenAICompatibleDirectionAnalysisProvider:
    def __init__(self, client=None) -> None:
        self.client = client or build_resume_llm_client()

    def analyze_directions(
        self,
        profile: ResumeProfilePayload,
        preferences: ResumePreferencePayload | None,
        directions: list[str],
    ) -> list[dict[str, Any]]:
        payload = {
            'model': self.client.model,
            'response_format': {'type': 'json_object'},
            'messages': [
                {'role': 'system', 'content': _SYSTEM_PROMPT},
                {
                    'role': 'user',
                    'content': json.dumps(
                        {
                            'candidate_summary': profile.candidate_summary,
                            'inferred_roles': profile.inferred_roles,
                            'inferred_tracks': profile.inferred_tracks,
                            'internships': [
                                {'company': i.company, 'role': i.role, 'bullets': i.bullets}
                                for i in profile.internships
                            ],
                            'projects': [
                                {'name': p.name, 'bullets': p.bullets}
                                for p in profile.projects
                            ],
                            'target_directions': directions,
                        },
                        ensure_ascii=False,
                    ),
                },
            ],
        }
        req = urllib_request.Request(
            self.client.chat_completions_url,
            data=json.dumps(payload).encode('utf-8'),
            headers={
                'Authorization': f'Bearer {self.client.api_key}',
                'Content-Type': 'application/json',
            },
            method='POST',
        )
        with urllib_request.urlopen(req, timeout=self.client.timeout_seconds) as response:
            body = json.loads(response.read().decode('utf-8'))
        content = body['choices'][0]['message']['content']
        return json.loads(content).get('directions', [])


# Picker roles map to their broader track concept so direction analysis does
# not emit two near-identical entries (e.g. '投研实习生' vs '投研'). The track
# label wins because that's the concept users reason about in the UI.
_DIRECTION_CANONICAL: dict[str, str] = {
    '投研实习生': '投研',
    '咨询顾问': '咨询',
    '数据分析师': '数据分析',
    '后端工程师': '后端开发',
    '产品经理': '产品运营',
}


def _canonical_direction(value: str) -> str:
    cleaned = (value or '').strip()
    return _DIRECTION_CANONICAL.get(cleaned, cleaned)


def _collect_directions(
    profile: ResumeProfilePayload,
    preferences: ResumePreferencePayload | None,
) -> list[str]:
    raw: list[str] = []
    if preferences and not preferences.all_skipped:
        raw.extend(preferences.preferred_tracks + preferences.preferred_roles)
    if not raw:
        raw.extend(profile.inferred_tracks[:4] + profile.inferred_roles[:4])
    seen: dict[str, None] = {}
    for d in raw:
        canonical = _canonical_direction(d)
        if canonical and canonical not in seen:
            seen[canonical] = None
    return list(seen.keys())[:8]


def generate_direction_analysis(
    profile: ResumeProfilePayload,
    preferences: ResumePreferencePayload | None,
    provider: DirectionAnalysisProvider | None = None,
) -> list[DirectionTierResult]:
    directions = _collect_directions(profile, preferences)
    if not directions:
        return []

    _provider = provider or OpenAICompatibleDirectionAnalysisProvider()
    try:
        raw_list = _provider.analyze_directions(profile, preferences, directions)
        results = []
        for item in (raw_list or []):
            tier_raw = int(item.get('tier', 1))
            tier = tier_raw if tier_raw in (1, 2, 3) else 1
            results.append(DirectionTierResult(
                direction=str(item.get('direction', '')),
                tier=tier,
                tier_label=str(item.get('tier_label', '强匹配')),
                strengths=[str(s) for s in item.get('strengths', [])],
                gaps=[str(g) for g in item.get('gaps', [])],
                transferable_from=[str(t) for t in item.get('transferable_from', [])],
            ))
        return results
    except Exception:
        return [
            DirectionTierResult(
                direction=d,
                tier=1,
                tier_label='强匹配',
                strengths=[],
                gaps=[],
                transferable_from=[],
            )
            for d in directions
        ]
