"""中→英简历翻译 — 纯函数(日期/数字锁/标题映射)+ LLM provider + translate_profile。"""
from __future__ import annotations

import json
import re
import urllib.request as urllib_request
from pathlib import Path

from app import config
from app.services.resume_copilot.llm import build_resume_llm_client

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


# ── B3: translate_profile ─────────────────────────────────────────────────────

_I18N_DIR = Path(__file__).parent / 'i18n'


def _load_json(name: str) -> dict:
    try:
        return json.loads((_I18N_DIR / name).read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return {}


def _glossary() -> dict:
    return _load_json('finance_glossary.json')


def _org_names() -> dict:
    return _load_json('org_names.json')


def _system_prompt() -> str:
    gloss = _glossary()
    gloss_lines = '\n'.join(f'  {k} → {v}' for k, v in gloss.items())
    return (
        'You translate Chinese finance/quant résumé text into professional English for '
        'buy-side/sell-side applications. Rules:\n'
        '1. Preserve ALL numbers and metrics EXACTLY — never invent, drop, or alter a number.\n'
        '2. Keep technical tokens as-is (Python, LightGBM, PyTorch, LSTM, Sharpe).\n'
        '3. Use this finance glossary where applicable:\n' + gloss_lines + '\n'
        '4. Return ONLY a JSON array of translated strings, same length and order as the input array. '
        'No commentary.'
    )


class OpenAICompatibleTranslator:
    """翻译 provider — 同 scoring.py 的 urllib + json_object 范式。可注入 fake 测试。"""
    def __init__(self, client=None) -> None:
        self.client = client or build_resume_llm_client(model=config.RESUME_COPILOT_TRANSLATE_MODEL)

    def translate(self, strings: list[str]) -> list[str]:
        payload = {
            'model': self.client.model,
            'response_format': {'type': 'json_object'},
            'reasoning_effort': 'medium',
            'max_tokens': 4000,
            'messages': [
                {'role': 'system', 'content': _system_prompt()},
                {'role': 'user', 'content': json.dumps({'strings': strings}, ensure_ascii=False)},
            ],
        }
        req = urllib_request.Request(
            self.client.chat_completions_url,
            data=json.dumps(payload).encode('utf-8'),
            headers={'Authorization': f'Bearer {self.client.api_key}', 'Content-Type': 'application/json'},
            method='POST',
        )
        with urllib_request.urlopen(req, timeout=self.client.timeout_seconds) as resp:
            body = json.loads(resp.read().decode('utf-8'))
        content = body['choices'][0]['message']['content']
        data = json.loads(content)
        out = data.get('strings') if isinstance(data, dict) else data
        if not isinstance(out, list) or len(out) != len(strings):
            raise ValueError('translator: response length mismatch')
        return [str(x) for x in out]


# 需要翻译的字符串字段路径收集 / 回填 ──────────────────────────────────────────

def _collect_strings(profile: dict) -> list[tuple]:
    """返回 [(getter_key_path, source_text)] 的顺序列表。仅收可译文本(不含 email/date/section label/机构名)。"""
    jobs: list[tuple] = []
    jobs.append((('name',), profile.get('name', '')))
    jobs.append((('skillsText',), profile.get('skillsText', '')))
    for si, sec in enumerate(profile.get('sections', [])):
        t = sec.get('type')
        if t == 'timeline':
            for ii, it in enumerate(sec.get('items', [])):
                for fld in ('sub', 'course', 'desc'):
                    if it.get(fld):
                        jobs.append((('sections', si, 'items', ii, fld), it[fld]))
                if it.get('location'):
                    jobs.append((('sections', si, 'items', ii, 'location'), it['location']))
                for bi, b in enumerate(it.get('bullets') or []):
                    jobs.append((('sections', si, 'items', ii, 'bullets', bi), b))
        elif t == 'paragraphs':
            for pi, p in enumerate(sec.get('items', [])):
                jobs.append((('sections', si, 'items', pi), p))
        elif t == 'tags':
            for gi, g in enumerate(sec.get('items', [])):
                jobs.append((('sections', si, 'items', gi), g))
    return jobs


def _set_path(profile: dict, path: tuple, value) -> None:
    cur = profile
    for key in path[:-1]:
        cur = cur[key]
    cur[path[-1]] = value


def translate_profile(profile: dict, *, provider=None) -> dict:
    """中→英翻译。provider 可注入(fake 不联网)。返回 {profile, warnings}。"""
    import copy
    out = copy.deepcopy(profile)
    prov = provider or OpenAICompatibleTranslator()

    jobs = _collect_strings(out)
    sources = [src for _, src in jobs]
    translated = prov.translate(sources) if sources else []

    warnings: list[dict] = []
    for (path, src), en in zip(jobs, translated):
        # 数字锁:EN 出现源里没有的数字 → 标警(保留译文,显式提示核实)。
        extra = numbers_in(en) - numbers_in(src)
        if extra:
            warnings.append({'path': '.'.join(str(x) for x in path), 'extra': '、'.join(sorted(extra))})
        _set_path(out, path, en)

    # 翻译前快照每个 timeline item 的源 org(机构名表用源中文匹配,不被 LLM 译文污染)
    src_orgs = {}
    for sec in profile.get('sections', []):
        if sec.get('type') == 'timeline':
            for ii, it in enumerate(sec.get('items', [])):
                src_orgs[(sec.get('id'), ii)] = it.get('org', '')

    # 机构官方英文名 + 日期格式化 + 固定英文标题(确定性后处理,覆盖 LLM)。
    orgs = _org_names()
    for sec in out.get('sections', []):
        sec['label'] = en_section_label(sec.get('id', ''), sec.get('label', ''))
        if sec.get('type') == 'timeline':
            for ii, it in enumerate(sec.get('items', [])):
                src_org = src_orgs.get((sec.get('id'), ii), '')
                it['org'] = orgs.get(src_org, src_org)  # 命中名表用官方名,否则保留源中文
                if it.get('date'):
                    it['date'] = format_date_en(it['date'])
    return {'profile': out, 'warnings': warnings}
