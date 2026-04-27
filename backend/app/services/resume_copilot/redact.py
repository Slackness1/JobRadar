"""PII redaction before sending profile to third-party LLMs.

`basic_info` is a free-form `dict[str, str]` populated by the resume parser.
In practice it carries `name / email / phone / github / linkedin / wechat /
qq / address / website` — all directly identifying. None of these are needed
for the LLM tasks (rerank / feedback / chat / quick enrichment), so we strip
them entirely before any outbound call.

We deliberately do NOT redact professional content (companies, schools,
project names) — the LLM needs that signal, and it is publicly inferable
from the candidate's behavior anyway.
"""
from app.schemas_resume_copilot import ResumeProfilePayload


_PII_KEYS = {
    'email', 'mail', 'e-mail',
    'phone', 'tel', 'mobile', 'cell',
    'github', 'gitee',
    'linkedin', 'in',
    'wechat', 'weixin', 'wx',
    'qq',
    'address', '地址',
    'website', 'site', 'homepage', 'blog',
    'name', '姓名',
}


def _redact_basic_info(basic_info: dict[str, str]) -> dict[str, str]:
    """Drop any key whose lowercased name matches a known PII tag."""
    return {
        k: v
        for k, v in basic_info.items()
        if k.strip().lower() not in _PII_KEYS
    }


def redact_profile_for_llm(profile: ResumeProfilePayload) -> ResumeProfilePayload:
    """Return a copy of `profile` with PII fields stripped from `basic_info`."""
    return profile.model_copy(update={'basic_info': _redact_basic_info(profile.basic_info)})
