"""Pure-regex semantic tag extractor for resume snippets + helper to
attach parsed-resume evidence to plan items.

Builds ``EvidenceTag`` instances from raw text. Intentionally LLM-free
so it runs cheaply on every parse + every clarification turn; the LLM
layer can refine these tags later if we add that pass.

Tag types extracted (matches plan.py's ``EvidenceTagType``):
- metric    — numbers (with 万/亿/千/百/%/人 suffix variants)
- tech      — known tech keywords (capital english + curated CN list)
- scope     — "N 人" / "N-人" / "整个团队"
- duration  — "N 年/月/周/天/小时"
- outcome   — keyword presence: 上线/获奖/提升/下降/节省/...
- verb_subject — "我" → self, "团队/组里/我们组" → team
- role      — words after "我是/担任/作为"
- tool      — known tool keywords (Git/Jira/Figma/...)
"""
from __future__ import annotations

import re

from app.services.resume_copilot.plan import Evidence, EvidenceTag, PlanState


_METRIC_RE = re.compile(r'\d+(?:\.\d+)?\s*[万亿千百%]?')
_SCOPE_RE = re.compile(r'(\d+)\s*[-—]?\s*人')
_DURATION_RE = re.compile(r'\d+\s*(?:年|个月|月|周|天|小时|h)')
_ENGLISH_TECH_RE = re.compile(r'\b[A-Z][a-zA-Z0-9+#.]{1,}\b')
_ROLE_AFTER_RE = re.compile(r'(?:我是|担任|作为)\s*([一-龥A-Za-z]+)')

# curated tech vocab — Chinese & lowercase forms we can't capture from caps
_CN_TECH_VOCAB: set[str] = {
    '机器学习', '深度学习', '数据分析', '数据挖掘', 'A/B 测试', 'A/B测试',
    'AB 测试', 'AB测试', '埋点', '指标体系', '数据看板', '可视化',
    '前端', '后端', '全栈', '微服务', '推荐系统', '搜索', '风控',
}

_TOOL_VOCAB: set[str] = {
    'Git', 'GitHub', 'GitLab', 'Jira', 'Confluence', 'Figma', 'Sketch',
    'Tableau', 'Power BI', 'PowerBI', 'Excel', 'Notion', 'Slack',
}

_OUTCOME_TOKENS = (
    '上线', '获奖', '获评', '提升', '下降', '减少', '节省', '增加',
    '通过', '达到', '完成', '交付', '落地', '推动', '促成', '推广', '产出',
)


def _dedupe_tags(tags: list[EvidenceTag]) -> list[EvidenceTag]:
    seen: set[tuple[str, str]] = set()
    out: list[EvidenceTag] = []
    for t in tags:
        key = (t.type, t.value)
        if key in seen:
            continue
        seen.add(key)
        out.append(t)
    return out


def extract_tags(text: str) -> list[EvidenceTag]:
    """Extract semantic tags from a raw resume snippet.

    Returns deduped tags in stable order. Never raises — empty input
    yields empty list. Same tag type/value pair appears at most once.
    """
    if not text:
        return []
    tags: list[EvidenceTag] = []

    for m in _METRIC_RE.finditer(text):
        raw = m.group()
        value = raw.strip()
        if value in ('1', '0'):
            continue
        tags.append(EvidenceTag(type='metric', value=value, raw=raw))

    for m in _SCOPE_RE.finditer(text):
        n = m.group(1)
        tags.append(EvidenceTag(type='scope', value=f'{n}人', raw=m.group()))

    for m in _DURATION_RE.finditer(text):
        tags.append(EvidenceTag(type='duration', value=m.group().strip(), raw=m.group()))

    for tech in _ENGLISH_TECH_RE.findall(text):
        if tech in {'I', 'A', 'An', 'The'}:
            continue
        tags.append(EvidenceTag(type='tech', value=tech, raw=tech))

    for cn in _CN_TECH_VOCAB:
        if cn in text:
            tags.append(EvidenceTag(type='tech', value=cn, raw=cn))

    for tool in _TOOL_VOCAB:
        if tool in text:
            tags.append(EvidenceTag(type='tool', value=tool, raw=tool))

    if '我' in text:
        tags.append(EvidenceTag(type='verb_subject', value='self', raw='我'))
    if any(t in text for t in ('团队', '组里', '我们组', '小组')):
        tags.append(EvidenceTag(type='verb_subject', value='team', raw='团队/组里'))

    for m in _ROLE_AFTER_RE.finditer(text):
        role = m.group(1).strip()
        if role:
            tags.append(EvidenceTag(type='role', value=role, raw=m.group()))

    for token in _OUTCOME_TOKENS:
        if token in text:
            tags.append(EvidenceTag(type='outcome', value=token, raw=token))
            break  # one outcome tag is enough

    return _dedupe_tags(tags)


# ─── Profile-level helpers ──────────────────────────────────────────────────

def extract_evidence_text_for_internship(intern: dict) -> str:
    """Flatten an internship dict into a single text blob for tag extraction."""
    parts: list[str] = []
    if intern.get('company'):
        parts.append(str(intern['company']))
    if intern.get('role'):
        parts.append(str(intern['role']))
    if intern.get('start_date') or intern.get('end_date'):
        parts.append(f"{intern.get('start_date', '')}-{intern.get('end_date', '')}")
    for b in intern.get('bullets') or []:
        if b:
            parts.append(str(b))
    return '\n'.join(parts)


def extract_evidence_text_for_project(proj: dict) -> str:
    parts: list[str] = []
    if proj.get('name'):
        parts.append(str(proj['name']))
    if proj.get('role'):
        parts.append(str(proj['role']))
    for t in proj.get('tech_stack') or []:
        if t:
            parts.append(str(t))
    for b in proj.get('bullets') or []:
        if b:
            parts.append(str(b))
    return '\n'.join(parts)


def attach_parsed_evidence(plan: PlanState, parsed_profile: dict) -> PlanState:
    """For each parent plan item, attach an ``Evidence`` derived from the
    matching parsed-profile entry. Child bullet items inherit a copy so the
    audit gate has something to check against from turn 0.

    Internships and projects map by index (parent #N → entries[N]); items
    without a matching entry get no parsed evidence — they remain pure
    template placeholders that will be populated through clarification.
    """
    new_plan = plan.model_copy(deep=True)

    parents_by_kind: dict[str, list] = {}
    for it in new_plan.items:
        if it.parent_id is None:
            parents_by_kind.setdefault(it.kind.value, []).append(it)

    sources: dict[str, tuple[list, callable]] = {
        'internship': (parsed_profile.get('internships') or [], extract_evidence_text_for_internship),
        'project':    (parsed_profile.get('projects') or [], extract_evidence_text_for_project),
    }

    children_by_parent: dict[str, list] = {}
    for it in new_plan.items:
        if it.parent_id is not None:
            children_by_parent.setdefault(it.parent_id, []).append(it)

    for kind_str, parents in parents_by_kind.items():
        if kind_str not in sources:
            continue
        entries, text_fn = sources[kind_str]
        for parent, entry in zip(parents, entries):
            text = text_fn(entry)
            if not text.strip():
                continue
            tags = extract_tags(text)
            parent.evidence.append(Evidence(source='parsed_resume', text=text, tags=tags))
            for child in children_by_parent.get(parent.id, []):
                child.evidence.append(Evidence(source='parsed_resume', text=text, tags=tags))

    return new_plan

