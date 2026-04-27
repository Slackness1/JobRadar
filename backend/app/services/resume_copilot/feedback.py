import json
from typing import Any, Protocol
from urllib import request

from app.schemas_resume_copilot import (
    ResumeFeedbackDiagnosticItem,
    ResumeFeedbackRewriteExample,
    ResumePreferencePayload,
    ResumeProfilePayload,
    ResumeRecommendationItem,
)
from app.services.resume_copilot.llm import build_resume_llm_client
from app.services.resume_copilot.redact import redact_profile_for_llm


class ResumeFeedbackProvider(Protocol):
    def generate_feedback(
        self,
        profile: ResumeProfilePayload,
        preferences: ResumePreferencePayload | None,
        recommendations: list[ResumeRecommendationItem],
    ) -> Any: ...


class OpenAICompatibleResumeFeedbackProvider:
    def __init__(self, client=None) -> None:
        self.client = client or build_resume_llm_client()

    def generate_feedback(
        self,
        profile: ResumeProfilePayload,
        preferences: ResumePreferencePayload | None,
        recommendations: list[ResumeRecommendationItem],
    ) -> Any:
        payload = {
            'model': self.client.model,
            'response_format': {'type': 'json_object'},
            'messages': [
                {
                    'role': 'system',
                    'content': (
                        'Review the resume profile and return JSON with keys diagnostics '
                        'and rewrite_examples. diagnostics must be a list of objects with title and description. '
                        'rewrite_examples must be a list of objects with section, original, improved, rationale.'
                    ),
                },
                {
                    'role': 'user',
                    'content': json.dumps(
                        {
                            'profile': redact_profile_for_llm(profile).model_dump(),
                            'preferences': preferences.model_dump() if preferences else None,
                            'recommendations': [item.model_dump() for item in recommendations],
                        },
                        ensure_ascii=False,
                    ),
                },
            ],
        }
        req = request.Request(
            self.client.chat_completions_url,
            data=json.dumps(payload).encode('utf-8'),
            headers={
                'Authorization': f'Bearer {self.client.api_key}',
                'Content-Type': 'application/json',
            },
            method='POST',
        )
        with request.urlopen(req, timeout=self.client.timeout_seconds) as response:
            body = json.loads(response.read().decode('utf-8'))
        content = body['choices'][0]['message']['content']
        return json.loads(content)


def build_resume_feedback_provider() -> ResumeFeedbackProvider:
    client = build_resume_llm_client()
    if not client.api_key:
        raise ValueError('RESUME_COPILOT_LLM_API_KEY is not configured')
    return OpenAICompatibleResumeFeedbackProvider(client=client)


def generate_feedback_for_profile(
    profile: ResumeProfilePayload,
    preferences: ResumePreferencePayload | None,
    recommendations: list[ResumeRecommendationItem],
    provider: ResumeFeedbackProvider | None = None,
) -> tuple[list[ResumeFeedbackDiagnosticItem], list[ResumeFeedbackRewriteExample]]:
    feedback_provider = provider or build_resume_feedback_provider()
    raw_feedback = feedback_provider.generate_feedback(profile, preferences, recommendations)
    if isinstance(raw_feedback, str):
        raw_feedback = json.loads(raw_feedback)
    diagnostics = [
        ResumeFeedbackDiagnosticItem.model_validate(item)
        for item in raw_feedback.get('diagnostics', [])
    ]
    rewrite_examples = [
        ResumeFeedbackRewriteExample.model_validate(item) for item in raw_feedback.get('rewrite_examples', [])
    ]
    return diagnostics, rewrite_examples
