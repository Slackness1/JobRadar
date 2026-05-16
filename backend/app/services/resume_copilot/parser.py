import json
import re
from typing import Any, Protocol
from urllib.error import HTTPError
from urllib.error import URLError
from urllib import request

from app.schemas_resume_copilot import (
    ResumeEducationItem,
    ResumeInternshipItem,
    ResumeProfilePayload,
    ResumeProjectItem,
    ResumeSkillsPayload,
)
from app.services.resume_copilot.llm import build_resume_llm_client
from app.services.taxonomy import canonicalize_track


EMAIL_PATTERN = re.compile(r'[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}')
PHONE_PATTERN = re.compile(
    r'(?<!\d)(?:\+?\d{1,3}[\s-]?)?(?:1[3-9]\d[\s-]?\d{4}[\s-]?\d{4}|\d{3}[-\s]\d{3,4}[-\s]\d{4})(?!\d)'
)
URL_PATTERN = re.compile(
    r'(?:(?:https?://)?(?:www\.)?)'
    r'(?:github\.com/[A-Za-z0-9_.-]+|linkedin\.com/in/[A-Za-z0-9_.-]+|[A-Za-z0-9.-]+\.[A-Za-z]{2,}/[^\s，,；;|]+)'
)
DATE_RANGE_PATTERN = re.compile(r'(?P<start>\d{4}[./-]\d{2})\s*[–—-]\s*(?P<end>至今|\d{4}[./-]\d{2})')
BULLET_PREFIX_PATTERN = re.compile(r'^[•·●▪■*-]\s*')
KNOWN_TECH_SKILLS = [
    'Python', 'Java', 'C++', 'C', 'Go', 'Rust', 'JavaScript', 'TypeScript', 'SQL',
    'React', 'Vue', 'Node', 'FastAPI', 'Django', 'Flask', 'Spring', 'MySQL',
    'PostgreSQL', 'Redis', 'Docker', 'Kubernetes', 'TensorFlow', 'PyTorch',
    '机器学习', '深度学习', '数据分析', '爬虫', '后端', '前端', '算法',
]
ROLE_KEYWORDS = [
    'Backend Engineer', 'Frontend Engineer', 'Full Stack Engineer', 'Data Analyst',
    'Data Engineer', 'Machine Learning Engineer', 'Product Manager', 'Operations',
    '后端开发', '前端开发', '全栈开发', '数据分析', '数据工程', '算法工程师', '产品经理', '运营',
]
TRACK_KEYWORDS = ['Internet', 'AI', 'Finance', '互联网', 'AI', '金融']


def _canonicalize_track_list(values: list[str]) -> list[str]:
    """Phase C (2026-05-16): 把 inferred_tracks 里的 free-text 跑 canonicalize_track
    映到 8 canonical(无 mapping 的保留原值,e.g. '互联网' / 'AI' 不属 8 canonical
    但也别丢)。Dedupe 保序。
    """
    seen: set[str] = set()
    out: list[str] = []
    for v in values:
        if not v:
            continue
        canon = canonicalize_track(v) or v
        if canon and canon not in seen:
            seen.add(canon)
            out.append(canon)
    return out
SECTION_ALIASES = {
    'summary': {'个人介绍', '个人简介', '自我介绍', '自我评价', 'Profile', 'Summary'},
    'education': {'教育背景', '教育经历', '教育'},
    'internships': {'实习经历', '工作经历', '职业经历', '实习/工作经历'},
    'projects': {'项目经历', '项目经验', '项目与论文', '项目/论文', '科研项目'},
    'skills': {'技能与资质', '技能', '专业技能', '技能证书'},
}
SECTION_HEADING_ALIASES = {alias for aliases in SECTION_ALIASES.values() for alias in aliases}
BASIC_INFO_KEY_ALIASES = {
    '姓名': 'name',
    'name': 'name',
    'full_name': 'name',
    'full name': 'name',
    '邮箱': 'email',
    '电子邮箱': 'email',
    'email': 'email',
    'email_address': 'email',
    'email address': 'email',
    '电话': 'phone',
    '手机号': 'phone',
    '手机': 'phone',
    'phone': 'phone',
    'mobile': 'phone',
    'tel': 'phone',
    'github': 'github',
    'github_url': 'github',
    'github url': 'github',
    'git hub': 'github',
    '领英': 'linkedin',
    'linkedin': 'linkedin',
    'linkedin_url': 'linkedin',
    'linkedin url': 'linkedin',
    '个人主页': 'website',
    '个人网站': 'website',
    '作品集': 'website',
    'website': 'website',
    'portfolio': 'website',
    '所在地': 'location',
    '地址': 'location',
    'location': 'location',
    'target_role': 'headline',
    'target role': 'headline',
    'headline': 'headline',
    'title': 'headline',
}
SUMMARY_FACT_KEYWORDS = {
    '教育背景',
    '教育经历',
    '实习经历',
    '工作经历',
    '项目经历',
    '项目经验',
    '专业技能',
    '技能与资质',
    '大学',
    '学院',
    '硕士',
    '本科',
    '博士',
    '学士',
    '专业',
    'GPA',
}


class ResumeParserProvider(Protocol):
    def parse_resume_text(self, resume_text: str) -> Any: ...


class OpenAICompatibleResumeParserProvider:
    def __init__(self, client=None) -> None:
        self.client = client or build_resume_llm_client()

    def parse_resume_text(self, resume_text: str) -> Any:
        payload = {
            'model': self.client.model,
            'response_format': {'type': 'json_object'},
            'max_tokens': 8000,
            'stream': True,
            'messages': [
                {
                    'role': 'system',
                    'content': (
                        'Extract the resume into JSON with keys: basic_info, education, '
                        'internships, projects, skills, languages, awards, '
                        'candidate_summary, inferred_roles, inferred_tracks.\n'
                        'Put contact facts only in basic_info using normalized keys '
                        'name, email, phone, github, linkedin, website, location, headline.\n'
                        'For every education item output all of: school, degree, major, '
                        'start_date, end_date, highlights (list of bullet strings such as '
                        'core courses / GPA / honours). Do not leave school or dates blank '
                        'when the resume text contains them.\n'
                        'For every internship item output all of: company, role, start_date, '
                        'end_date, bullets (list of strings — copy each bullet from the resume '
                        'verbatim, preserve every one of them, do not summarize, do not merge, '
                        'do not cap the count).\n'
                        'For every project item output all of: name, role, tech_stack (list), '
                        'bullets (list of strings — copy each bullet from the resume verbatim, '
                        'preserve every one of them, do not summarize, do not merge, do not cap '
                        'the count).\n'
                        'Dates should be in the resume original format (e.g. "2024.09 – 2025.12").\n'
                        'Do not put education, contact details, dates, projects, skills, '
                        'or work-history facts into candidate_summary. candidate_summary '
                        'should only contain an explicit personal introduction or self-evaluation; '
                        'leave it empty if the resume does not have one.'
                    ),
                },
                {'role': 'user', 'content': resume_text},
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
        # Streaming mode: accumulate SSE chunks so each recv() arrives quickly,
        # avoiding long silent-wait timeouts on large JSON outputs.
        chunks: list[str] = []
        with request.urlopen(req, timeout=self.client.timeout_seconds) as response:
            for raw_line in response:
                line = raw_line.decode('utf-8').strip()
                if not line.startswith('data:'):
                    continue
                data = line[len('data:'):].strip()
                if data == '[DONE]':
                    break
                try:
                    event = json.loads(data)
                    delta = event['choices'][0].get('delta', {})
                    token = delta.get('content') or ''
                    if token:
                        chunks.append(token)
                except (KeyError, json.JSONDecodeError):
                    continue
        content = ''.join(chunks)
        return json.loads(content)


def is_resume_parser_upstream_http_error(exc: Exception) -> bool:
    if isinstance(exc, HTTPError):
        return True
    if isinstance(exc, URLError):
        reason = getattr(exc, 'reason', None)
        return isinstance(reason, TimeoutError) or 'timed out' in str(reason).lower()
    if isinstance(exc, ValueError) and 'RESUME_COPILOT_LLM_API_KEY is not configured' in str(exc):
        return True
    return isinstance(exc, TimeoutError)


def _clean_line(value: str) -> str:
    return re.sub(r'\s+', ' ', BULLET_PREFIX_PATTERN.sub('', value or '')).strip()


def _normalize_line_preserve_bullet(value: str) -> str:
    return re.sub(r'\s+', ' ', value or '').strip()


def _dedupe_preserve_order(values: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        cleaned = value.strip()
        if not cleaned or cleaned in seen:
            continue
        result.append(cleaned)
        seen.add(cleaned)
    return result


def _split_text_items(value: str) -> list[str]:
    items: list[str] = []
    buffer: list[str] = []
    depth = 0

    for char in value:
        if char in '([{（':
            depth += 1
        elif char in ')]}）' and depth > 0:
            depth -= 1

        if depth == 0 and char in '\n,;；、':
            item = _clean_line(''.join(buffer))
            if item:
                items.append(item)
            buffer = []
            continue

        buffer.append(char)

    tail = _clean_line(''.join(buffer))
    if tail:
        items.append(tail)
    return items


def _normalize_string_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return _dedupe_preserve_order(_split_text_items(value))
    if not isinstance(value, list):
        return []

    result: list[str] = []
    for item in value:
        if isinstance(item, str):
            cleaned = _clean_line(item)
            if cleaned:
                result.append(cleaned)
            continue
        if isinstance(item, dict):
            language = _clean_line(str(item.get('language', '') or item.get('name', '')))
            proficiency = _clean_line(str(item.get('proficiency', '') or item.get('level', '')))
            if language and proficiency:
                result.append(f'{language} ({proficiency})')
            elif language:
                result.append(language)
            else:
                flattened = ' '.join(_clean_line(str(part)) for part in item.values() if _clean_line(str(part)))
                if flattened:
                    result.append(flattened)
    return _dedupe_preserve_order(result)


def _normalize_basic_info(value: Any) -> dict[str, str]:
    if not isinstance(value, dict):
        return {}
    normalized: dict[str, str] = {}
    for key, raw_value in value.items():
        cleaned_key = str(key).strip()
        normalized_key = BASIC_INFO_KEY_ALIASES.get(cleaned_key, BASIC_INFO_KEY_ALIASES.get(cleaned_key.lower(), cleaned_key))
        cleaned_value = _clean_line(str(raw_value))
        if normalized_key and cleaned_value:
            normalized[normalized_key] = cleaned_value
    return normalized


def _normalize_contact_url(value: str) -> str:
    cleaned = _clean_line(value).strip('.,;；，')
    return re.sub(r'^https?://', '', cleaned)


def _extract_contact_info(resume_text: str) -> dict[str, str]:
    contact: dict[str, str] = {}

    email_match = EMAIL_PATTERN.search(resume_text)
    if email_match:
        contact['email'] = email_match.group(0)

    phone_match = PHONE_PATTERN.search(resume_text)
    if phone_match:
        contact['phone'] = _clean_line(phone_match.group(0))

    for match in URL_PATTERN.finditer(resume_text):
        url = _normalize_contact_url(match.group(0))
        lowered = url.lower()
        if 'github.com/' in lowered and 'github' not in contact:
            contact['github'] = url
        elif 'linkedin.com/in/' in lowered and 'linkedin' not in contact:
            contact['linkedin'] = url
        elif 'website' not in contact:
            contact['website'] = url

    return contact


def _is_structured_fact_fragment(value: str) -> bool:
    cleaned = _clean_line(value)
    if not cleaned:
        return True
    if cleaned in SECTION_HEADING_ALIASES:
        return True
    if EMAIL_PATTERN.search(cleaned) or PHONE_PATTERN.search(cleaned) or URL_PATTERN.search(cleaned):
        return True
    if DATE_RANGE_PATTERN.search(cleaned):
        return True
    return any(keyword in cleaned for keyword in SUMMARY_FACT_KEYWORDS)


def _sanitize_candidate_summary(value: str) -> str:
    cleaned = _clean_line(value)
    if not cleaned:
        return ''

    fragments = [_clean_line(part) for part in re.split(r'[\n|]+', value) if _clean_line(part)]
    if not fragments:
        return ''

    kept = [fragment for fragment in fragments if not _is_structured_fact_fragment(fragment)]
    return '；'.join(kept)[:500]


def _candidate_summary_or_empty(value: str, basic_info: dict[str, str]) -> str:
    summary = _sanitize_candidate_summary(value)
    if summary and summary == basic_info.get('name', ''):
        return ''
    return summary


def _extract_sections(resume_text: str) -> dict[str, list[str]]:
    sections = {key: [] for key in SECTION_ALIASES}
    current_section: str | None = None

    for raw_line in resume_text.splitlines():
        line = _clean_line(raw_line)
        if not line:
            continue

        matched_section = None
        for section_name, aliases in SECTION_ALIASES.items():
            if line in aliases:
                matched_section = section_name
                break

        if matched_section is not None:
            current_section = matched_section
            continue

        if current_section is not None:
            sections[current_section].append(_normalize_line_preserve_bullet(raw_line))

    return sections


def _is_bulleted_line(value: str) -> bool:
    return BULLET_PREFIX_PATTERN.match(value.strip()) is not None


def _looks_like_labeled_bullet(value: str) -> bool:
    cleaned = _clean_line(value)
    colon_positions = [index for index in (cleaned.find('：'), cleaned.find(':')) if index >= 0]
    if not colon_positions:
        return False
    first_colon = min(colon_positions)
    return 1 <= first_colon <= 28


def _merge_detail_lines(lines: list[str]) -> list[str]:
    merged: list[tuple[str, bool]] = []

    for line in lines:
        cleaned = _clean_line(line)
        if not cleaned:
            continue

        is_bulleted = _is_bulleted_line(line)
        starts_new_labeled_item = _looks_like_labeled_bullet(cleaned)

        if not merged or is_bulleted or starts_new_labeled_item:
            merged.append((cleaned, is_bulleted or starts_new_labeled_item))
            continue

        previous, previous_is_item = merged[-1]
        if previous_is_item:
            merged[-1] = (f'{previous}{cleaned}', previous_is_item)
            continue

        merged.append((cleaned, False))

    return [text for text, _is_item in merged]


def _split_section_entries(lines: list[str]) -> list[tuple[str, list[str]]]:
    entries: list[tuple[str, list[str]]] = []
    current_header = ''
    current_details: list[str] = []

    for line in lines:
        if DATE_RANGE_PATTERN.search(line):
            if current_header:
                entries.append((current_header, current_details))
            current_header = line
            current_details = []
            continue

        if current_header:
            current_details.append(line)

    if current_header:
        entries.append((current_header, current_details))

    return entries


def _split_header_parts(value: str) -> list[str]:
    cleaned = re.sub(r'\s{2,}', ' | ', value).strip()
    if '|' in cleaned:
        return [part.strip() for part in cleaned.split('|') if part.strip()]
    return [part.strip() for part in cleaned.split() if part.strip()]


def _extract_date_range(value: str) -> tuple[str, str, str]:
    match = DATE_RANGE_PATTERN.search(value)
    if not match:
        return value.strip(), '', ''
    start_date = match.group('start')
    end_date = match.group('end')
    prefix = value[:match.start()].strip()
    return prefix, start_date, end_date


def _parse_education_section(lines: list[str]) -> list[ResumeEducationItem]:
    items: list[ResumeEducationItem] = []
    for line in lines:
        prefix, start_date, end_date = _extract_date_range(line)
        if not prefix:
            continue
        parts = _split_header_parts(prefix)
        if not parts:
            continue

        school = parts[0]
        remainder = ' '.join(parts[1:]).strip()
        degree = ''
        major = ''
        for candidate in ('博士', '硕士', '学士'):
            if candidate in remainder:
                degree = candidate
                major = remainder.replace(candidate, '').strip()
                break
        if not degree and remainder:
            degree = remainder

        items.append(
            ResumeEducationItem(
                school=school,
                degree=degree,
                major=major,
                start_date=start_date,
                end_date=end_date,
                highlights=[],
            )
        )
    return items


def _parse_internship_header(prefix: str) -> tuple[str, str]:
    parts = _split_header_parts(prefix)
    if len(parts) >= 3:
        return parts[0], ' '.join(parts[1:])
    if len(parts) == 2:
        return parts[0], parts[1]
    if len(parts) == 1:
        return parts[0], ''
    return '', ''


def _parse_internship_section(lines: list[str]) -> list[ResumeInternshipItem]:
    items: list[ResumeInternshipItem] = []
    for header, details in _split_section_entries(lines):
        prefix, start_date, end_date = _extract_date_range(header)
        company, role = _parse_internship_header(prefix)
        if not company:
            continue
        items.append(
            ResumeInternshipItem(
                company=company,
                role=role,
                start_date=start_date,
                end_date=end_date,
                bullets=_merge_detail_lines(details),
            )
        )
    return items


def _parse_project_section(lines: list[str]) -> list[ResumeProjectItem]:
    items: list[ResumeProjectItem] = []
    for header, details in _split_section_entries(lines):
        prefix, _start_date, _end_date = _extract_date_range(header)
        parts = _split_header_parts(prefix)
        if not parts:
            continue
        if len(parts) >= 2:
            name = ' '.join(parts[:-1])
            role = parts[-1]
        else:
            name = parts[0]
            role = ''
        items.append(
            ResumeProjectItem(
                name=name,
                role=role,
                tech_stack=[],
                bullets=_merge_detail_lines(details),
            )
        )
    return items


def _parse_skills_section(lines: list[str]) -> tuple[list[str], list[str], list[str]]:
    technical: list[str] = []
    tools: list[str] = []
    languages: list[str] = []

    for line in lines:
        normalized = line.replace('：', ':')
        if ':' not in normalized:
            continue
        label, values = normalized.split(':', 1)
        parsed_values = _normalize_string_list(values)
        if '编程语言' in label:
            technical.extend(parsed_values)
        elif '软件工具' in label or '工具' in label:
            tools.extend(parsed_values)
        elif label.strip() == '语言' or '语言' in label:
            languages.extend(parsed_values)

    return (
        _dedupe_preserve_order(technical),
        _dedupe_preserve_order(tools),
        _dedupe_preserve_order(languages),
    )


def _normalize_education_items(value: Any) -> list[ResumeEducationItem]:
    if not isinstance(value, list):
        return []
    items: list[ResumeEducationItem] = []
    for raw_item in value:
        if isinstance(raw_item, str):
            items.append(ResumeEducationItem(school=_clean_line(raw_item)))
            continue
        if not isinstance(raw_item, dict):
            continue
        items.append(
            ResumeEducationItem(
                school=_clean_line(str(raw_item.get('school', ''))),
                degree=_clean_line(str(raw_item.get('degree', ''))),
                major=_clean_line(str(raw_item.get('major', ''))),
                start_date=_clean_line(str(raw_item.get('start_date', ''))),
                end_date=_clean_line(str(raw_item.get('end_date', ''))),
                highlights=_normalize_string_list(raw_item.get('highlights', [])),
            )
        )
    return [item for item in items if item.school or item.degree or item.major]


def _normalize_internship_items(value: Any) -> list[ResumeInternshipItem]:
    if not isinstance(value, list):
        return []
    items: list[ResumeInternshipItem] = []
    for raw_item in value:
        if isinstance(raw_item, str):
            items.append(ResumeInternshipItem(company=_clean_line(raw_item)))
            continue
        if not isinstance(raw_item, dict):
            continue
        items.append(
            ResumeInternshipItem(
                company=_clean_line(str(raw_item.get('company', ''))),
                role=_clean_line(str(raw_item.get('role', ''))),
                start_date=_clean_line(str(raw_item.get('start_date', ''))),
                end_date=_clean_line(str(raw_item.get('end_date', ''))),
                bullets=_merge_detail_lines(_normalize_string_list(raw_item.get('bullets', []))),
            )
        )
    return [item for item in items if item.company or item.role or item.bullets]


def _normalize_project_items(value: Any) -> list[ResumeProjectItem]:
    if not isinstance(value, list):
        return []
    items: list[ResumeProjectItem] = []
    for raw_item in value:
        if isinstance(raw_item, str):
            items.append(ResumeProjectItem(name=_clean_line(raw_item)))
            continue
        if not isinstance(raw_item, dict):
            continue
        items.append(
            ResumeProjectItem(
                name=_clean_line(str(raw_item.get('name', ''))),
                role=_clean_line(str(raw_item.get('role', ''))),
                tech_stack=_normalize_string_list(raw_item.get('tech_stack', [])),
                bullets=_merge_detail_lines(_normalize_string_list(raw_item.get('bullets', []))),
            )
        )
    return [item for item in items if item.name or item.role or item.bullets]


def _fill_education_from_heuristic(
    llm_items: list[ResumeEducationItem],
    heuristic_items: list[ResumeEducationItem],
) -> list[ResumeEducationItem]:
    if not llm_items:
        return heuristic_items
    filled: list[ResumeEducationItem] = []
    for index, item in enumerate(llm_items):
        fallback = heuristic_items[index] if index < len(heuristic_items) else None
        filled.append(
            ResumeEducationItem(
                school=item.school or (fallback.school if fallback else ''),
                degree=item.degree or (fallback.degree if fallback else ''),
                major=item.major or (fallback.major if fallback else ''),
                start_date=item.start_date or (fallback.start_date if fallback else ''),
                end_date=item.end_date or (fallback.end_date if fallback else ''),
                highlights=item.highlights or (fallback.highlights if fallback else []),
            )
        )
    return filled


def _fill_internships_from_heuristic(
    llm_items: list[ResumeInternshipItem],
    heuristic_items: list[ResumeInternshipItem],
) -> list[ResumeInternshipItem]:
    if not llm_items:
        return heuristic_items
    filled: list[ResumeInternshipItem] = []
    for index, item in enumerate(llm_items):
        fallback = heuristic_items[index] if index < len(heuristic_items) else None
        filled.append(
            ResumeInternshipItem(
                company=item.company or (fallback.company if fallback else ''),
                role=item.role or (fallback.role if fallback else ''),
                start_date=item.start_date or (fallback.start_date if fallback else ''),
                end_date=item.end_date or (fallback.end_date if fallback else ''),
                bullets=item.bullets or (fallback.bullets if fallback else []),
            )
        )
    return filled


def _fill_projects_from_heuristic(
    llm_items: list[ResumeProjectItem],
    heuristic_items: list[ResumeProjectItem],
) -> list[ResumeProjectItem]:
    if not llm_items:
        return heuristic_items
    filled: list[ResumeProjectItem] = []
    for index, item in enumerate(llm_items):
        fallback = heuristic_items[index] if index < len(heuristic_items) else None
        filled.append(
            ResumeProjectItem(
                name=item.name or (fallback.name if fallback else ''),
                role=item.role or (fallback.role if fallback else ''),
                tech_stack=item.tech_stack or (fallback.tech_stack if fallback else []),
                bullets=item.bullets or (fallback.bullets if fallback else []),
            )
        )
    return filled


def _merge_profile_with_heuristics(raw_profile: Any, heuristic_profile: ResumeProfilePayload) -> ResumeProfilePayload:
    raw_dict = raw_profile if isinstance(raw_profile, dict) else {}
    skills_dict = raw_dict.get('skills', {}) if isinstance(raw_dict.get('skills', {}), dict) else {}
    basic_info = {
        **heuristic_profile.basic_info,
        **_normalize_basic_info(raw_dict.get('basic_info', {})),
    }

    technical = _normalize_string_list(skills_dict.get('technical', []))
    tools = _normalize_string_list(skills_dict.get('tools', []))
    skill_languages = _normalize_string_list(skills_dict.get('languages', []))
    languages = _normalize_string_list(raw_dict.get('languages', []))

    profile = ResumeProfilePayload(
        basic_info=basic_info,
        education=_fill_education_from_heuristic(
            _normalize_education_items(raw_dict.get('education', [])),
            heuristic_profile.education,
        ),
        internships=_fill_internships_from_heuristic(
            _normalize_internship_items(raw_dict.get('internships', [])),
            heuristic_profile.internships,
        ),
        projects=_fill_projects_from_heuristic(
            _normalize_project_items(raw_dict.get('projects', [])),
            heuristic_profile.projects,
        ),
        skills=ResumeSkillsPayload(
            technical=technical or heuristic_profile.skills.technical,
            tools=tools or heuristic_profile.skills.tools,
            languages=skill_languages or heuristic_profile.skills.languages,
        ),
        languages=languages or heuristic_profile.languages,
        awards=_normalize_string_list(raw_dict.get('awards', [])) or heuristic_profile.awards,
        candidate_summary=_candidate_summary_or_empty(str(raw_dict.get('candidate_summary', '') or ''), basic_info)
        or heuristic_profile.candidate_summary,
        inferred_roles=_normalize_string_list(raw_dict.get('inferred_roles', [])) or heuristic_profile.inferred_roles,
        inferred_tracks=_canonicalize_track_list(
            _normalize_string_list(raw_dict.get('inferred_tracks', [])) or heuristic_profile.inferred_tracks
        ),
    )
    return profile


def build_heuristic_resume_profile(resume_text: str) -> ResumeProfilePayload:
    lines = [line.strip() for line in resume_text.splitlines() if line.strip()]
    contact_info = _extract_contact_info(resume_text)
    sections = _extract_sections(resume_text)

    name = ''
    for line in lines[:8]:
        cleaned_line = _clean_line(line)
        if (
            EMAIL_PATTERN.search(cleaned_line)
            or PHONE_PATTERN.search(cleaned_line)
            or URL_PATTERN.search(cleaned_line)
            or cleaned_line in SECTION_HEADING_ALIASES
        ):
            continue
        if len(line) <= 40:
            name = line
            break

    lowered_text = resume_text.lower()
    technical_skills = [skill for skill in KNOWN_TECH_SKILLS if skill.lower() in lowered_text]
    inferred_roles = _dedupe_preserve_order([role for role in ROLE_KEYWORDS if role.lower() in lowered_text])[:3]
    inferred_tracks = _canonicalize_track_list(
        _dedupe_preserve_order([track for track in TRACK_KEYWORDS if track.lower() in lowered_text])[:3]
    )

    summary = _sanitize_candidate_summary('\n'.join(sections['summary']))
    technical_from_section, tools_from_section, languages = _parse_skills_section(sections['skills'])

    return ResumeProfilePayload(
        basic_info={
            'name': name,
            **contact_info,
        },
        education=_parse_education_section(sections['education']),
        internships=_parse_internship_section(sections['internships']),
        projects=_parse_project_section(sections['projects']),
        skills=ResumeSkillsPayload(
            technical=_dedupe_preserve_order(technical_skills + technical_from_section),
            tools=tools_from_section,
            languages=languages,
        ),
        languages=languages,
        candidate_summary=summary,
        inferred_roles=inferred_roles,
        inferred_tracks=inferred_tracks,
    )


def build_resume_parser_provider() -> ResumeParserProvider:
    client = build_resume_llm_client()
    if not client.api_key:
        raise ValueError('RESUME_COPILOT_LLM_API_KEY is not configured')
    return OpenAICompatibleResumeParserProvider(client=client)


def parse_resume_text_to_profile(
    resume_text: str,
    provider: ResumeParserProvider | None = None,
) -> ResumeProfilePayload:
    parser_provider = provider or build_resume_parser_provider()
    raw_profile = parser_provider.parse_resume_text(resume_text)
    if isinstance(raw_profile, str):
        raw_profile = json.loads(raw_profile)
    heuristic_profile = build_heuristic_resume_profile(resume_text)
    return _merge_profile_with_heuristics(raw_profile, heuristic_profile)
