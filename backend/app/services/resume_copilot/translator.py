"""中→英简历翻译 — 纯函数(日期/数字锁/标题映射)+ LLM provider + translate_profile。"""
from __future__ import annotations

import re

from app import config
from app.services.resume_copilot.llm import build_resume_llm_client  # noqa: F401 — used by B3

_MONTHS = ['', 'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
_YM = re.compile(r'^(\d{4})-(\d{1,2})$')
_NUM = re.compile(r'\d+(?:\.\d+)?')

# section id → 固定英文标题(不靠 LLM 现译,保一致)。
EN_SECTION_LABELS = {
    'edu': 'Education',
    'str': 'Summary',
    'intern': 'Work Experience',
    'proj': 'Projects',
    'skills': 'Skills',
    'honor': 'Honors & Awards',
}


def _fmt_ym(token: str) -> str:
    m = _YM.match(token.strip())
    if not m:
        return token.strip()
    y, mo = int(m.group(1)), int(m.group(2))
    if 1 <= mo <= 12:
        return f'{_MONTHS[mo]} {y}'
    return token.strip()


def format_date_en(s: str) -> str:
    """'2024-06' → 'Jun 2024';'2024-06 - 2024-12' → 'Jun 2024 – Dec 2024';无法识别原样返回。"""
    raw = (s or '').strip()
    # Split on " - " (space-hyphen-space) to avoid splitting on the hyphen inside YYYY-MM.
    parts = re.split(r'\s+-\s+', raw)
    if len(parts) == 2 and _YM.match(parts[0].strip()) and _YM.match(parts[1].strip()):
        return f'{_fmt_ym(parts[0])} – {_fmt_ym(parts[1])}'
    if _YM.match(raw):
        return _fmt_ym(raw)
    return raw


def numbers_in(text: str) -> set[str]:
    """抽出文本里的数字 token(用于数字锁)。"""
    return set(_NUM.findall(text or ''))


def en_section_label(section_id: str, source_label: str) -> str:
    """id 命中固定映射则用之,否则回退源标题(自定义段)。"""
    return EN_SECTION_LABELS.get(section_id, source_label)
