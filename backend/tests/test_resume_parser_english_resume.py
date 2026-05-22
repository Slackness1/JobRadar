"""#114 Phase 2 (2026-05-22) — 英文简历输入端到端契约。

测 heuristic 路径 (LLM 不在场时):
  - SECTION_ALIASES 能匹配英文 heading (Education / Experience / Projects / Skills)
  - DATE_RANGE_PATTERN 能识别英文日期 (Sep 2024 – Dec 2025 / Present / 09/2024)
  - TRACK_KEYWORDS 能从英文 finance 简历推 IB / Quant / PE 等 canonical track

LLM 路径 (PROMPT 文本) 单独断言双语 directive 已注入。

设计文档: docs/2026-05-22-track-matching-english-resume-design.md (Phase 2)
"""
from __future__ import annotations

from app.services.resume_copilot.parser import (
    DATE_RANGE_PATTERN,
    OpenAICompatibleResumeParserProvider,
    SECTION_ALIASES,
    TRACK_KEYWORDS,
    _extract_sections,
    _normalize_section_heading,
    build_heuristic_resume_profile,
)


# ── _normalize_section_heading ─────────────────────────────────────────────


def test_normalize_section_heading_lowercases() -> None:
    assert _normalize_section_heading('EDUCATION') == 'education'
    assert _normalize_section_heading('Education') == 'education'
    assert _normalize_section_heading('education') == 'education'


def test_normalize_section_heading_strips_trailing_colon() -> None:
    assert _normalize_section_heading('Education:') == 'education'
    assert _normalize_section_heading('Experience: ') == 'experience'
    assert _normalize_section_heading('教育背景:') == '教育背景'
    assert _normalize_section_heading('Skills；') == 'skills'


def test_normalize_section_heading_empty() -> None:
    assert _normalize_section_heading('') == ''
    assert _normalize_section_heading('   ') == ''


# ── SECTION_ALIASES coverage ───────────────────────────────────────────────


def test_section_aliases_include_common_en_headings() -> None:
    """钉死最常见的英文 heading,防回退。"""
    assert 'education' in SECTION_ALIASES['education']
    assert 'experience' in SECTION_ALIASES['internships']
    assert 'work experience' in SECTION_ALIASES['internships']
    assert 'projects' in SECTION_ALIASES['projects']
    assert 'skills' in SECTION_ALIASES['skills']
    assert 'summary' in SECTION_ALIASES['summary']


def test_section_aliases_keep_existing_cn() -> None:
    """加 EN 不能丢 CN。"""
    assert '教育背景' in SECTION_ALIASES['education']
    assert '实习经历' in SECTION_ALIASES['internships']
    assert '项目经历' in SECTION_ALIASES['projects']


# ── _extract_sections on English resume ────────────────────────────────────


def test_extract_sections_handles_uppercase_en_headings() -> None:
    text = """John Smith
EDUCATION
MIT BSc Economics 2024
EXPERIENCE
- Goldman Sachs summer analyst
SKILLS
Python, SQL, Bloomberg
"""
    sections = _extract_sections(text)
    assert 'MIT BSc Economics 2024' in sections['education'][0]
    assert any('Goldman' in line for line in sections['internships'])
    assert any('Python' in line for line in sections['skills'])


def test_extract_sections_handles_titlecase_with_colon() -> None:
    """SAIF MF 学生 LinkedIn-style 英文简历常带 'Education:' / 'Experience:'。"""
    text = """Lin Mei
Education:
NUS Master of Finance 2025
Experience:
- JPMorgan IBD summer
Projects:
- Quant alpha research
"""
    sections = _extract_sections(text)
    assert any('NUS' in line for line in sections['education'])
    assert any('JPMorgan' in line for line in sections['internships'])
    assert any('Quant' in line for line in sections['projects'])


def test_extract_sections_handles_mixed_zh_en() -> None:
    text = """张三
教育背景
清华大学 经济学 2024
Experience
- Goldman Sachs Hong Kong summer analyst
技能
Python, SQL
"""
    sections = _extract_sections(text)
    assert any('清华' in line for line in sections['education'])
    assert any('Goldman' in line for line in sections['internships'])
    assert any('Python' in line for line in sections['skills'])


# ── DATE_RANGE_PATTERN — English date formats ──────────────────────────────


def test_date_pattern_matches_month_name_range() -> None:
    """'Sep 2024 – Dec 2025' / 'September 2024 - Present'。"""
    assert DATE_RANGE_PATTERN.search('Goldman Sachs HK | Sep 2024 – Dec 2025')
    assert DATE_RANGE_PATTERN.search('JPMorgan | September 2024 - Present')
    assert DATE_RANGE_PATTERN.search('NUS | Aug 2023 - May 2025')


def test_date_pattern_matches_slash_format() -> None:
    """'09/2024 – 12/2025' MM/YYYY。"""
    assert DATE_RANGE_PATTERN.search('McKinsey | 09/2024 - 12/2025')
    assert DATE_RANGE_PATTERN.search('Citi HK | 06/2023 – 08/2023')


def test_date_pattern_matches_year_only_range() -> None:
    """'2020 - 2024' (院校 multi-year)。"""
    assert DATE_RANGE_PATTERN.search('MIT BSc Economics 2020 - 2024')
    assert DATE_RANGE_PATTERN.search('SAIF MF | 2024 – 2026')


def test_date_pattern_still_matches_cn_format() -> None:
    """CN 日期不能因为加 EN 支持而失效。"""
    assert DATE_RANGE_PATTERN.search('中信证券 | 2024.09 - 2025.12')
    assert DATE_RANGE_PATTERN.search('高瓴资本 | 2024.06 – 至今')


def test_date_pattern_matches_present_aliases() -> None:
    """'Present' / 'now' / 'current' / '至今' — 都算 end token。"""
    assert DATE_RANGE_PATTERN.search('BCG | Sep 2024 - Present')
    assert DATE_RANGE_PATTERN.search('McKinsey | Aug 2024 - now')
    assert DATE_RANGE_PATTERN.search('Tencent | 2024.06 - 至今')


def test_date_pattern_does_not_match_unrelated_numbers() -> None:
    """防 false positive: salary range / 项目规模数字。"""
    assert not DATE_RANGE_PATTERN.search('Annual budget 1000 - 2000')
    assert not DATE_RANGE_PATTERN.search('Tracked 5 - 10 names per week')


# ── TRACK_KEYWORDS — EN finance ────────────────────────────────────────────


def test_track_keywords_include_en_finance() -> None:
    assert 'Investment Banking' in TRACK_KEYWORDS
    assert 'Equity Research' in TRACK_KEYWORDS
    assert 'Private Equity' in TRACK_KEYWORDS
    assert 'Hedge Fund' in TRACK_KEYWORDS
    assert 'Management Consulting' in TRACK_KEYWORDS


def test_track_keywords_keep_cn_and_short_acronyms() -> None:
    assert '金融' in TRACK_KEYWORDS
    assert 'IBD' in TRACK_KEYWORDS
    assert 'PE' in TRACK_KEYWORDS
    assert 'VC' in TRACK_KEYWORDS


# ── build_heuristic_resume_profile end-to-end (English resume) ─────────────


def test_heuristic_profile_extracts_en_education_section() -> None:
    resume = """John Smith
john@example.com | +1 617 555 1234

EDUCATION
MIT BSc Economics | Sep 2020 - May 2024
- GPA 3.8 / 4.0
- Dean's List 2022

EXPERIENCE
Goldman Sachs Hong Kong | Sep 2024 - Dec 2024
- Built valuation model for TMT IPO pipeline

SKILLS
Python, SQL, Bloomberg
"""
    profile = build_heuristic_resume_profile(resume)
    # education was extracted (date range matched + section detected)
    assert len(profile.education) >= 1
    assert any('MIT' in (e.school or '') for e in profile.education)


def test_heuristic_profile_extracts_en_internship_section() -> None:
    resume = """Lin Mei
EDUCATION
NUS Master of Finance | Aug 2024 - May 2026

EXPERIENCE
JPMorgan Singapore | Jun 2023 - Aug 2023
- Quantitative research summer analyst
- Built factor models in Python

SKILLS
Python, R, Bloomberg
"""
    profile = build_heuristic_resume_profile(resume)
    assert len(profile.internships) >= 1
    assert any('JPMorgan' in (it.company or '') for it in profile.internships)


def test_heuristic_profile_infers_canonical_track_from_en_resume() -> None:
    """英文 finance 简历 → inferred_tracks 至少要落到 canonical 之一。"""
    resume = """Chen
EDUCATION
HKUST BBA Finance 2024
EXPERIENCE
Goldman Sachs Hong Kong | Investment Banking summer 2023
Equity Research intern at Citi HK 2024
"""
    profile = build_heuristic_resume_profile(resume)
    # 至少一个 canonical 应该被推出来 — Investment Banking → 一级市场,
    # Equity Research → 卖方研究·S&T。
    assert profile.inferred_tracks, (
        f'Expected non-empty inferred_tracks for IB+ER resume, got: {profile.inferred_tracks}'
    )
    assert any(
        t in ('一级市场', '卖方研究·S&T')
        for t in profile.inferred_tracks
    ), f'Expected canonical IB/ER track, got: {profile.inferred_tracks}'


def test_heuristic_profile_extracts_en_skills_section() -> None:
    resume = """Wang
EDUCATION
SAIF MF 2024
SKILLS
Python, SQL, Bloomberg, FactSet, Wind
"""
    profile = build_heuristic_resume_profile(resume)
    # skills.technical OR skills.tools 至少有一个非空
    has_skills = bool(profile.skills.technical) or bool(profile.skills.tools)
    assert has_skills


# ── LLM prompt acknowledges EN/CN duality ──────────────────────────────────


def test_llm_prompt_mentions_bilingual_extraction() -> None:
    """LLM extractor prompt 必须明确告诉 LLM 简历可能是英文或中文。"""
    provider = OpenAICompatibleResumeParserProvider.__new__(
        OpenAICompatibleResumeParserProvider
    )
    # We don't construct the actual client (skip __init__) — only inspect the
    # baked prompt by reading the literal in parse_resume_text via source.
    import inspect
    source = inspect.getsource(OpenAICompatibleResumeParserProvider.parse_resume_text)
    assert 'Chinese, English' in source or 'English, or' in source, (
        'LLM extractor prompt must explicitly mention EN/CN bilingual support'
    )
    assert 'verbatim' in source.lower()
