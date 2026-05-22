"""一次性 eval: CN vs EN persona parser 一致性。

跑法:
    cd /home/chuanbo/projects/JobRadar/backend
    PYTHONPATH=. .venv/bin/python scripts/_tmp_cn_en_eval.py

输出:
    - stdout: 8 个 persona 的 CN vs EN parser 摘要 + 命中判断
    - 落盘 JSON: backend/scripts/_out/cn_en_eval_2026_05_22.json
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

# 让 import app.* 能找到
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.chdir(str(Path(__file__).resolve().parent.parent))

from app.services.resume_copilot.parser import (  # noqa: E402
    _extract_sections,
    build_heuristic_resume_profile,
)
from app.services.taxonomy.canonical import canonicalize_track  # noqa: E402


CN_DIR = Path('tests/eval/personas/workspace_2026_05_20')
EN_DIR = Path('tests/eval/personas/workspace_en_2026_05_22')
OUT_DIR = Path('scripts/_out')
OUT_DIR.mkdir(parents=True, exist_ok=True)


def _persona_to_resume_text_cn(persona: dict) -> str:
    """把 CN persona JSON 拍平成 SAIF 常见的中文简历文本。

    section heading 用 _extract_sections / SECTION_ALIASES 能识别的标准中文词:
      教育背景 / 实习经历 / 项目经历 / 技能。
    """
    r = persona['resume']
    bi = r.get('basic_info', {}) or {}
    lines: list[str] = []

    # header
    if bi.get('name'):
        lines.append(bi['name'])
    contact_bits = []
    if bi.get('email'):
        contact_bits.append(bi['email'])
    if bi.get('phone'):
        contact_bits.append(bi['phone'])
    if bi.get('location'):
        contact_bits.append(bi['location'])
    if contact_bits:
        lines.append(' | '.join(contact_bits))
    if bi.get('headline'):
        lines.append(bi['headline'])
    lines.append('')

    # education
    lines.append('教育背景')
    for e in r.get('education', []) or []:
        head_bits = [str(e.get('school', ''))]
        deg_major = ' '.join(b for b in [str(e.get('degree', '')), str(e.get('major', ''))] if b).strip()
        if deg_major:
            head_bits.append(deg_major)
        date_bit = ''
        if e.get('start_date') or e.get('end_date'):
            date_bit = f"{e.get('start_date', '')} – {e.get('end_date', '')}"
        if date_bit:
            head_bits.append(date_bit)
        lines.append(' | '.join(b for b in head_bits if b))
        for h in e.get('highlights', []) or []:
            lines.append(f'- {h}')
        lines.append('')

    # internships
    lines.append('实习经历')
    for it in r.get('internships', []) or []:
        head_bits = [str(it.get('company', ''))]
        if it.get('role'):
            head_bits.append(str(it['role']))
        if it.get('start_date') or it.get('end_date'):
            head_bits.append(f"{it.get('start_date', '')} – {it.get('end_date', '')}")
        lines.append(' | '.join(b for b in head_bits if b))
        for b in it.get('bullets', []) or []:
            lines.append(f'- {b}')
        lines.append('')

    # projects
    lines.append('项目经历')
    for p in r.get('projects', []) or []:
        head_bits = [str(p.get('name', ''))]
        if p.get('duration'):
            head_bits.append(str(p['duration']))
        lines.append(' | '.join(b for b in head_bits if b))
        if p.get('description'):
            lines.append(str(p['description']))
        for b in p.get('bullets', []) or []:
            lines.append(f'- {b}')
        lines.append('')

    # skills (CN persona 用 dict)
    lines.append('技能')
    sk = r.get('skills') or {}
    if isinstance(sk, dict):
        if sk.get('technical'):
            lines.append('编程语言/方法: ' + '; '.join(sk['technical']))
        if sk.get('tools'):
            lines.append('软件工具: ' + '; '.join(sk['tools']))
        if sk.get('languages'):
            lines.append('语言: ' + '; '.join(sk['languages']))
    elif isinstance(sk, list):
        lines.append('; '.join(str(x) for x in sk))

    return '\n'.join(lines)


def _persona_to_resume_text_en(persona: dict) -> str:
    """EN persona → English resume text。section heading 用 Education / Experience /
    Projects / Skills。 日期沿 persona 原字段 (P1 用 'Sep 2024'; P3 用 '09/2024'),
    测试 _DATE_TOKEN 多格式。
    """
    r = persona['resume']
    bi = r.get('basic_info', {}) or {}
    lines: list[str] = []

    if bi.get('name'):
        lines.append(bi['name'])
    contact_bits = []
    if bi.get('email'):
        contact_bits.append(bi['email'])
    if bi.get('phone'):
        contact_bits.append(bi['phone'])
    if bi.get('location'):
        contact_bits.append(bi['location'])
    if bi.get('linkedin'):
        contact_bits.append(bi['linkedin'])
    if bi.get('github'):
        contact_bits.append(bi['github'])
    if contact_bits:
        lines.append(' | '.join(contact_bits))
    if bi.get('headline'):
        lines.append(bi['headline'])
    lines.append('')

    lines.append('Education')
    for e in r.get('education', []) or []:
        head_bits = [str(e.get('school', ''))]
        deg_major = ' '.join(b for b in [str(e.get('degree', '')), str(e.get('major', ''))] if b).strip()
        if deg_major:
            head_bits.append(deg_major)
        if e.get('start_date') or e.get('end_date'):
            head_bits.append(f"{e.get('start_date', '')} – {e.get('end_date', '')}")
        lines.append(' | '.join(b for b in head_bits if b))
        for h in e.get('highlights', []) or []:
            lines.append(f'- {h}')
        lines.append('')

    lines.append('Experience')
    for it in r.get('internships', []) or []:
        head_bits = [str(it.get('company', ''))]
        if it.get('role'):
            head_bits.append(str(it['role']))
        if it.get('start_date') or it.get('end_date'):
            head_bits.append(f"{it.get('start_date', '')} – {it.get('end_date', '')}")
        lines.append(' | '.join(b for b in head_bits if b))
        for b in it.get('bullets', []) or []:
            lines.append(f'- {b}')
        lines.append('')

    lines.append('Projects')
    for p in r.get('projects', []) or []:
        head_bits = [str(p.get('name', ''))]
        if p.get('duration'):
            head_bits.append(str(p['duration']))
        lines.append(' | '.join(b for b in head_bits if b))
        if p.get('description'):
            lines.append(str(p['description']))
        for b in p.get('bullets', []) or []:
            lines.append(f'- {b}')
        lines.append('')

    lines.append('Skills')
    sk = r.get('skills') or {}
    if isinstance(sk, dict):
        if sk.get('technical'):
            lines.append('Programming/Methods: ' + '; '.join(sk['technical']))
        if sk.get('tools'):
            lines.append('Tools: ' + '; '.join(sk['tools']))
        if sk.get('languages'):
            lines.append('Languages: ' + '; '.join(sk['languages']))
    elif isinstance(sk, list):
        lines.append('; '.join(str(x) for x in sk))

    return '\n'.join(lines)


def _summarize_profile(profile: Any, resume_text: str) -> dict:
    """关键字段摘要。"""
    sections = _extract_sections(resume_text)
    return {
        'name': profile.basic_info.get('name', ''),
        'n_education': len(profile.education),
        'n_internships': len(profile.internships),
        'n_projects': len(profile.projects),
        'inferred_tracks': list(profile.inferred_tracks),
        'inferred_offices': list(profile.inferred_offices),
        'inferred_roles': list(profile.inferred_roles),
        'skills_technical': list(profile.skills.technical),
        'skills_technical_n': len(profile.skills.technical),
        'skills_tools_n': len(profile.skills.tools),
        # section line-counts (debugging 用 — 看 heading 是否被识别)
        'section_lines': {k: len(v) for k, v in sections.items()},
    }


def _eval_one(persona_id: str, cn_persona: dict, en_persona: dict) -> dict:
    target_track = cn_persona.get('scenario_config', {}).get('target_track', '')
    target_canonical = canonicalize_track(target_track) if target_track else ''

    cn_text = _persona_to_resume_text_cn(cn_persona)
    en_text = _persona_to_resume_text_en(en_persona)

    cn_profile = build_heuristic_resume_profile(cn_text)
    en_profile = build_heuristic_resume_profile(en_text)

    cn_summary = _summarize_profile(cn_profile, cn_text)
    en_summary = _summarize_profile(en_profile, en_text)

    # 命中判断: target_canonical 是否出现在 inferred_tracks 里 (canonicalize 后)
    cn_track_canons = {canonicalize_track(t) for t in cn_summary['inferred_tracks']}
    en_track_canons = {canonicalize_track(t) for t in en_summary['inferred_tracks']}

    cn_hit = target_canonical in cn_track_canons if target_canonical else False
    en_hit = target_canonical in en_track_canons if target_canonical else False

    return {
        'persona_id': persona_id,
        'target_track_raw': target_track,
        'target_canonical': target_canonical,
        'cn': cn_summary,
        'en': en_summary,
        'cn_track_canons': sorted(cn_track_canons),
        'en_track_canons': sorted(en_track_canons),
        'cn_hit_target': cn_hit,
        'en_hit_target': en_hit,
        'consistent_education_count': cn_summary['n_education'] == en_summary['n_education'],
        'consistent_internships_count': cn_summary['n_internships'] == en_summary['n_internships'],
        'consistent_projects_count': cn_summary['n_projects'] == en_summary['n_projects'],
        'cn_resume_chars': len(cn_text),
        'en_resume_chars': len(en_text),
    }


def main() -> None:
    results: list[dict] = []
    for n in range(1, 9):
        pid = f'P{n}'
        cn_path = CN_DIR / f'{pid}.json'
        en_path = EN_DIR / f'{pid}.json'
        if not cn_path.exists():
            print(f'skip {pid}: CN file missing')
            continue
        if not en_path.exists():
            print(f'skip {pid}: EN file missing')
            continue
        cn_persona = json.loads(cn_path.read_text(encoding='utf-8'))
        en_persona = json.loads(en_path.read_text(encoding='utf-8'))
        res = _eval_one(pid, cn_persona, en_persona)
        results.append(res)

    # stdout pretty summary
    print('\n=== TL;DR ===')
    print(f"{'PID':<5} {'target_canonical':<22} {'CN':<5} {'EN':<5} {'edu eq':<7} {'intern eq':<10} {'proj eq':<8}")
    for r in results:
        print(
            f"{r['persona_id']:<5} {r['target_canonical']:<22} "
            f"{'✓' if r['cn_hit_target'] else '✗':<5} "
            f"{'✓' if r['en_hit_target'] else '✗':<5} "
            f"{str(r['consistent_education_count']):<7} "
            f"{str(r['consistent_internships_count']):<10} "
            f"{str(r['consistent_projects_count']):<8}"
        )

    print('\n=== Detail per persona ===')
    for r in results:
        print(f"\n--- {r['persona_id']} | target={r['target_canonical']!r} ---")
        print(f"CN: edu={r['cn']['n_education']} intern={r['cn']['n_internships']} "
              f"proj={r['cn']['n_projects']} tech_skills={r['cn']['skills_technical_n']} "
              f"offices={r['cn']['inferred_offices']} sections={r['cn']['section_lines']}")
        print(f"    inferred_tracks={r['cn']['inferred_tracks']}")
        print(f"    canonicalized={r['cn_track_canons']}  hit_target={r['cn_hit_target']}")
        print(f"EN: edu={r['en']['n_education']} intern={r['en']['n_internships']} "
              f"proj={r['en']['n_projects']} tech_skills={r['en']['skills_technical_n']} "
              f"offices={r['en']['inferred_offices']} sections={r['en']['section_lines']}")
        print(f"    inferred_tracks={r['en']['inferred_tracks']}")
        print(f"    canonicalized={r['en_track_canons']}  hit_target={r['en_hit_target']}")
        print(f"    cn_skills={r['cn']['skills_technical']}")
        print(f"    en_skills={r['en']['skills_technical']}")

    cn_hits = sum(1 for r in results if r['cn_hit_target'])
    en_hits = sum(1 for r in results if r['en_hit_target'])
    print(f'\nTotals: CN {cn_hits}/{len(results)}  |  EN {en_hits}/{len(results)}')

    out_path = OUT_DIR / 'cn_en_eval_2026_05_22.json'
    out_path.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f'\nDetailed dump -> {out_path}')


if __name__ == '__main__':
    main()
