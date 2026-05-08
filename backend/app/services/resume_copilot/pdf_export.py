"""PDF export for the resume copilot.

Renders the structured resume profile to A4 PDF using Playwright (Chromium).
Chinese glyphs use LXGW WenKai (open-source 楷体 替代); Latin uses Tinos
(open-source Times New Roman 替代). Fonts are fetched once by
``scripts/install_pdf_fonts.sh`` and referenced by ``file://`` URL so
Chromium loads them as actual files (data URLs of ~25MB silently fail).
"""

from __future__ import annotations

import html
import tempfile
from pathlib import Path

from app.schemas_resume_copilot import ResumeProfilePayload


FONTS_DIR = Path(__file__).resolve().parent / 'fonts'
LXGW_FILE = FONTS_DIR / 'LXGWWenKai-Regular.ttf'
TINOS_REGULAR_FILE = FONTS_DIR / 'Tinos-Regular.ttf'
TINOS_BOLD_FILE = FONTS_DIR / 'Tinos-Bold.ttf'


class FontsNotInstalledError(RuntimeError):
    pass


def _font_file_url(path: Path) -> str:
    if not path.is_file():
        raise FontsNotInstalledError(
            f'PDF font missing: {path.name}. '
            'Run scripts/install_pdf_fonts.sh once to download.'
        )
    return path.resolve().as_uri()


def _esc(value: str) -> str:
    return html.escape(value or '')


def _fmt_date_range(start: str, end: str) -> str:
    start = (start or '').strip()
    end = (end or '').strip()
    if start and end:
        return f'{start} – {end}'
    return start or end


def _basic_info_line(basic_info: dict[str, str]) -> str:
    keys = ('email', 'phone', 'location', 'github', 'linkedin', 'website')
    parts = [_esc(basic_info[k]) for k in keys if basic_info.get(k)]
    return ' · '.join(parts)


def _bullets_html(bullets: list[str]) -> str:
    if not bullets:
        return ''
    items = ''.join(f'<li>{_esc(b)}</li>' for b in bullets if b)
    return f'<ul class="bullets">{items}</ul>' if items else ''


def _section(title: str, body: str) -> str:
    if not body.strip():
        return ''
    return f'<section class="section"><h2>{_esc(title)}</h2>{body}</section>'


def _education_block(profile: ResumeProfilePayload) -> str:
    if not profile.education:
        return ''
    rows: list[str] = []
    for item in profile.education:
        head_left_parts = [item.school, item.degree, item.major]
        head_left = ' · '.join(p for p in head_left_parts if p)
        head_right = _fmt_date_range(item.start_date, item.end_date)
        highlights = _bullets_html(item.highlights)
        rows.append(
            f'<div class="entry">'
            f'<div class="entry-head"><span class="left">{_esc(head_left)}</span>'
            f'<span class="right">{_esc(head_right)}</span></div>'
            f'{highlights}'
            f'</div>'
        )
    return _section('教育背景', ''.join(rows))


def _internship_block(profile: ResumeProfilePayload) -> str:
    if not profile.internships:
        return ''
    rows: list[str] = []
    for item in profile.internships:
        head_left_parts = [item.company, item.role]
        head_left = ' · '.join(p for p in head_left_parts if p)
        head_right = _fmt_date_range(item.start_date, item.end_date)
        bullets = _bullets_html(item.bullets)
        rows.append(
            f'<div class="entry">'
            f'<div class="entry-head"><span class="left">{_esc(head_left)}</span>'
            f'<span class="right">{_esc(head_right)}</span></div>'
            f'{bullets}'
            f'</div>'
        )
    return _section('实习经历', ''.join(rows))


def _project_block(profile: ResumeProfilePayload) -> str:
    if not profile.projects:
        return ''
    rows: list[str] = []
    for item in profile.projects:
        head_left_parts = [item.name, item.role]
        head_left = ' · '.join(p for p in head_left_parts if p)
        tech = ' / '.join(item.tech_stack) if item.tech_stack else ''
        bullets = _bullets_html(item.bullets)
        tech_line = (
            f'<div class="entry-tech">技术栈：{_esc(tech)}</div>' if tech else ''
        )
        rows.append(
            f'<div class="entry">'
            f'<div class="entry-head"><span class="left">{_esc(head_left)}</span></div>'
            f'{tech_line}'
            f'{bullets}'
            f'</div>'
        )
    return _section('项目经历', ''.join(rows))


def _skills_block(profile: ResumeProfilePayload) -> str:
    skills = profile.skills
    rows: list[str] = []
    if skills.technical:
        rows.append(f'<div class="skills-row"><span class="label">技术：</span>{_esc(" / ".join(skills.technical))}</div>')
    if skills.tools:
        rows.append(f'<div class="skills-row"><span class="label">工具：</span>{_esc(" / ".join(skills.tools))}</div>')
    languages = skills.languages or profile.languages
    if languages:
        rows.append(f'<div class="skills-row"><span class="label">语言：</span>{_esc(" / ".join(languages))}</div>')
    return _section('专业技能', ''.join(rows))


def _awards_block(profile: ResumeProfilePayload) -> str:
    if not profile.awards:
        return ''
    return _section('荣誉奖项', _bullets_html(profile.awards))


def _summary_block(profile: ResumeProfilePayload) -> str:
    summary = (profile.candidate_summary or '').strip()
    if not summary:
        return ''
    return _section('个人简介', f'<p class="summary">{_esc(summary)}</p>')


def build_resume_html(profile: ResumeProfilePayload) -> str:
    lxgw = _font_file_url(LXGW_FILE)
    tinos_r = _font_file_url(TINOS_REGULAR_FILE)
    tinos_b = _font_file_url(TINOS_BOLD_FILE)

    basic = profile.basic_info or {}
    name = _esc(basic.get('name', '') or '简历')
    headline = _esc(basic.get('headline', ''))
    contact_line = _basic_info_line(basic)

    body_html = ''.join([
        _summary_block(profile),
        _education_block(profile),
        _internship_block(profile),
        _project_block(profile),
        _skills_block(profile),
        _awards_block(profile),
    ])

    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8" />
<style>
@font-face {{
  font-family: 'Tinos';
  font-weight: 400;
  font-style: normal;
  src: url('{tinos_r}') format('truetype');
}}
@font-face {{
  font-family: 'Tinos';
  font-weight: 700;
  font-style: normal;
  src: url('{tinos_b}') format('truetype');
}}
@font-face {{
  font-family: 'LXGW WenKai';
  font-weight: 400;
  font-style: normal;
  src: url('{lxgw}') format('truetype');
}}
@page {{
  size: A4;
  margin: 16mm 18mm;
}}
* {{ box-sizing: border-box; }}
html, body {{
  margin: 0;
  padding: 0;
  font-family: 'Tinos', 'LXGW WenKai', serif;
  font-size: 10.5pt;
  line-height: 1.55;
  color: #1f1f1f;
}}
header {{
  text-align: center;
  margin-bottom: 14pt;
  padding-bottom: 10pt;
  border-bottom: 0.6pt solid #1f1f1f;
}}
header h1 {{
  margin: 0 0 4pt 0;
  font-size: 22pt;
  font-weight: 700;
  letter-spacing: 1.5pt;
}}
header .headline {{
  font-size: 11pt;
  margin-bottom: 4pt;
  color: #4a4a4a;
}}
header .contact {{
  font-size: 9.5pt;
  color: #4a4a4a;
}}
section.section {{
  margin-top: 10pt;
  page-break-inside: auto;
}}
section.section h2 {{
  margin: 0 0 6pt 0;
  padding-bottom: 2pt;
  border-bottom: 0.4pt solid #888;
  font-size: 13pt;
  font-weight: 700;
  letter-spacing: 0.5pt;
}}
.entry {{
  margin-bottom: 8pt;
  page-break-inside: avoid;
}}
.entry-head {{
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  font-weight: 700;
  font-size: 11pt;
  margin-bottom: 2pt;
}}
.entry-head .right {{
  font-weight: 400;
  font-size: 10pt;
  color: #555;
  white-space: nowrap;
}}
.entry-tech {{
  font-size: 10pt;
  color: #555;
  margin-bottom: 2pt;
}}
ul.bullets {{
  margin: 2pt 0 0 0;
  padding-left: 16pt;
}}
ul.bullets li {{
  margin-bottom: 1.5pt;
  text-align: justify;
}}
.skills-row {{
  margin-bottom: 3pt;
}}
.skills-row .label {{
  font-weight: 700;
}}
.summary {{
  margin: 0;
  text-align: justify;
}}
</style>
</head>
<body>
<header>
  <h1>{name}</h1>
  {f'<div class="headline">{headline}</div>' if headline else ''}
  {f'<div class="contact">{contact_line}</div>' if contact_line else ''}
</header>
{body_html}
</body>
</html>
"""


def render_resume_pdf(profile: ResumeProfilePayload) -> bytes:
    from playwright.sync_api import sync_playwright

    html_doc = build_resume_html(profile)
    # Write the HTML next to the fonts so file:// URLs in @font-face resolve
    # against this directory. NamedTemporaryFile is fine — Chromium reads it
    # synchronously before we delete it.
    with tempfile.NamedTemporaryFile(
        mode='w',
        suffix='.html',
        encoding='utf-8',
        dir=str(FONTS_DIR.parent),
        delete=False,
    ) as fh:
        fh.write(html_doc)
        html_path = Path(fh.name)
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            try:
                context = browser.new_context()
                page = context.new_page()
                page.goto(html_path.resolve().as_uri(), wait_until='load')
                # Wait for @font-face to actually finish loading — large TTFs
                # take >100ms even from the local disk.
                page.evaluate('async () => { await document.fonts.ready; }')
                pdf_bytes = page.pdf(
                    format='A4',
                    margin={'top': '0', 'right': '0', 'bottom': '0', 'left': '0'},
                    print_background=True,
                    prefer_css_page_size=True,
                )
            finally:
                browser.close()
    finally:
        try:
            html_path.unlink()
        except OSError:
            pass
    return pdf_bytes
