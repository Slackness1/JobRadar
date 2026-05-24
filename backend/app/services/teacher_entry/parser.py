"""Teacher quick-entry parser: URL / OCR / JD-text → structured job draft.

Strategy:
- `link`: fetch URL HTML (httpx, 8s), strip to text, then LLM extracts.
- `text`: pass text directly to LLM.
- `ocr`:  treat as already-extracted text (frontend-side or future OCR).

LLM is the same DeepSeek client used by resume-copilot. Falls back to a
heuristic extractor if the LLM call fails so the form stays usable when
the API key is missing or rate-limited.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from typing import Optional
from urllib import request as urllib_request

import httpx

logger = logging.getLogger(__name__)

from app.services.resume_copilot.llm import build_resume_llm_client


# 公司名简易词典 — 用于 heuristic fallback；LLM 路径不依赖
_COMPANY_HINTS = [
    '中金', '中信', '中信建投', '招商', '招行', '工行', '建行', '中行', '农行', '交行',
    '腾讯', '阿里', '蚂蚁', '字节', '美团', '京东', '华为', '小米', '百度', '滴滴',
    '中金公司', '国家电网', '中海油', '中石油', '中石化', '中建', '中国电信', '中国移动',
    '蚂蚁集团', '招商银行', '平安银行', '平安集团',
]
_LOCATION_HINTS = [
    '北京', '上海', '深圳', '广州', '杭州', '南京', '苏州', '成都', '武汉',
    '西安', '重庆', '天津', '青岛', '厦门', '香港', '新加坡', '远程', 'Remote',
]


@dataclass
class ParsedDraft:
    title: str = ''
    company: str = ''
    location: str = ''
    jd_summary: str = ''
    deadline: str = ''
    salary: str = ''
    detail_url: str = ''
    suggested_track: str = 'other'        # finance | fintech | other
    suggested_tags: list[str] = field(default_factory=list)
    confidence: float = 0.0               # 0–100

    def as_dict(self) -> dict:
        return {
            'title': self.title,
            'company': self.company,
            'location': self.location,
            'jd_summary': self.jd_summary,
            'deadline': self.deadline,
            'salary': self.salary,
            'detail_url': self.detail_url,
            'suggested_track': self.suggested_track,
            'suggested_tags': self.suggested_tags,
            'confidence': self.confidence,
        }


def parse_source(
    source_type: str,
    payload: str,
    *,
    qr_url_candidates: Optional[list[str]] = None,
) -> list[ParsedDraft]:
    """Parse one source into 0+ job drafts.

    一条信息里可能包含多个岗位（教师常见：一张微信群截图列了 3 个、
    一篇公众号文章里 5 个 JD）。LLM prompt 已经允许 1..N。

    `qr_url_candidates` 是 OCR 路径预先扫到的二维码 URL 列表（按显眼程度
    排序，第一个通常是海报最大那个 QR）。我们把它注入 LLM prompt 当做
    "投递链接候选"，LLM 可以择优填进 detail_url；如果 LLM 没填，最后
    用第一个 QR URL 兜底。

    Return value:
    - `[]`  — LLM 成功且明确判断"没有岗位"（用户粘贴的可能根本不是 JD）
    - `[d1, d2, ...]` — LLM / heuristic 抽到的 N 个岗位
    """
    payload = (payload or '').strip()
    if not payload:
        return []

    detail_url = ''
    raw_text = payload

    if source_type == 'link':
        detail_url = payload
        raw_text = _fetch_url_text(payload) or ''
        if not raw_text:
            raw_text = f'仅有链接，未能抓取页面正文：{payload}'

    raw_text = raw_text[:6000]

    llm_drafts = _llm_extract(raw_text, hint_url=detail_url, qr_url_candidates=qr_url_candidates)
    if llm_drafts is None:
        # LLM 整体不可用（网络/超时/key 缺失）→ 启发式兜底
        drafts = [_heuristic_extract(raw_text)]
    else:
        # LLM 可用：尊重它的判断（即使是 0 个）
        drafts = llm_drafts

    if detail_url:
        for d in drafts:
            if not d.detail_url:
                d.detail_url = detail_url

    # QR 兜底：LLM 没填 detail_url 但我们扫到了二维码 → 把第一个 QR URL 灌进去
    if qr_url_candidates:
        first_qr = qr_url_candidates[0]
        for d in drafts:
            if not d.detail_url:
                d.detail_url = first_qr

    return drafts


# ---------------- URL fetch ----------------

_TAG_RE = re.compile(r'<[^>]+>')
_WS_RE = re.compile(r'\s+')


def _fetch_url_text(url: str) -> Optional[str]:
    if not (url.startswith('http://') or url.startswith('https://')):
        return None
    try:
        with httpx.Client(
            timeout=8.0,
            follow_redirects=True,
            headers={
                'User-Agent': (
                    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) '
                    'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36'
                ),
                'Accept': 'text/html,application/xhtml+xml',
                'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            },
        ) as client:
            resp = client.get(url)
            if resp.status_code >= 400:
                return None
            html = resp.text
    except (httpx.HTTPError, OSError):
        return None
    return _strip_html(html)


def _strip_html(html: str) -> str:
    # 简单粗暴：去掉 <script>/<style> 块 → 剥标签 → 压缩空白
    cleaned = re.sub(r'<script[\s\S]*?</script>', ' ', html, flags=re.IGNORECASE)
    cleaned = re.sub(r'<style[\s\S]*?</style>', ' ', cleaned, flags=re.IGNORECASE)
    cleaned = _TAG_RE.sub(' ', cleaned)
    cleaned = _WS_RE.sub(' ', cleaned)
    return cleaned.strip()


# ---------------- LLM extract ----------------

_LLM_SYSTEM_PROMPT = (
    'You are extracting campus-recruitment job postings into structured JSON. '
    'The raw text may contain ONE OR MORE distinct job postings (e.g. a WeChat '
    'group screenshot listing 3 positions, or an article describing 5 JDs). '
    'Detect every distinct posting and return them all.\n\n'
    'Return a single JSON object with key "jobs" whose value is a list. Each '
    'list item must have these fields:\n'
    '- title (string): job title in Chinese if the source is Chinese; e.g. "量化研究员 (MMT)"\n'
    '- company (string): company name in Chinese; e.g. "中金公司". Leave empty "" '
    'if the source genuinely does NOT name a company (don\'t guess).\n'
    '- location (string): primary city; e.g. "北京". Leave empty "" if the source '
    'does NOT explicitly mention a city for THIS job (do NOT default to the company HQ).\n'
    '- jd_summary (string): 1–2 sentences in Chinese, ≤ 80 chars, describing the role\n'
    '- deadline (string): "YYYY-MM-DD" if visible, else "" \n'
    '- salary (string): visible salary range or "" \n'
    '- suggested_track (string): one of "finance" (纯金融 — 投行/资管/券商/银行/保险/PE/VC/量化), '
    '"fintech" (FinTech — AI 应用 / 数据 / 工程方向), or "other" (其他 — 央国企/快消/咨询/制造)\n'
    '- suggested_tags (array of ≤ 4 short Chinese tags): e.g. ["券商 T1", "量化", "北京"]\n'
    '- confidence (number 0–100): your confidence in extracting THIS particular item. '
    'If company is empty, confidence should be ≤ 50.\n\n'
    'Splitting rules (IMPORTANT — past failure modes):\n'
    '- Different titles, different companies, or clearly numbered (1./2./3. or 一/二/三) '
    'sections → separate jobs.\n'
    '- Titles separated by 顿号 / 逗号 / 斜杠 (e.g. "投行业务、投行销售" or '
    '"基金经理/研究员/交易员") → split into ONE job per title.\n'
    '- TABLE-style or "集团总览" layouts that list MULTIPLE member companies / '
    'subsidiaries / departments side by side (one per row or column) → produce '
    'ONE job per row/company. Do NOT collapse 14 group subsidiaries into a single '
    'aggregated draft. Cap at 10 items if the table is huge — pick the first 10 distinct rows.\n'
    '- Do NOT invent jobs that are not in the source.\n\n'
    'Few-shot examples:\n'
    'Input: "国信证券投资银行事业部实习生招聘｜投行业务、投行销售｜深圳/上海/北京/杭州"\n'
    'Output (2 items):\n'
    '{"jobs":[{"title":"投行业务实习生","company":"国信证券","location":"深圳",...},'
    '{"title":"投行销售实习生","company":"国信证券","location":"深圳",...}]}\n\n'
    'Input: "中国国新2026春招｜诚通基金·投资经理·上海｜诚通租赁·风控·北京｜国新国际·研究员·香港"\n'
    'Output (3 items, one per subsidiary):\n'
    '{"jobs":[{"title":"投资经理","company":"诚通基金","location":"上海",...},'
    '{"title":"风控","company":"诚通租赁","location":"北京",...},'
    '{"title":"研究员","company":"国新国际","location":"香港",...}]}\n\n'
    'Return ONLY the JSON object, no preamble, no code fence.'
)


def _llm_extract(
    raw_text: str,
    *,
    hint_url: str = '',
    qr_url_candidates: Optional[list[str]] = None,
) -> Optional[list[ParsedDraft]]:
    """Returns None if LLM failed (caller should fallback), [] / [...] if LLM ran."""
    try:
        from app import config
        client = build_resume_llm_client(model=config.TEACHER_ENTRY_MODEL)
    except Exception:
        return None
    if not client.api_key:
        return None

    user_content = raw_text
    if hint_url:
        user_content = f'[页面 URL]: {hint_url}\n\n[页面正文]:\n{raw_text}'
    if qr_url_candidates:
        # 让 LLM 知道有哪些扫码链接候选，方便它选最贴 detail_url 的那个
        qr_block = '\n'.join(f'  - {u}' for u in qr_url_candidates[:5])
        user_content = (
            f'[投递链接候选 — 从图里二维码扫出来的，请从这些 URL 里挑最像真投递入口的填进 detail_url；'
            f'如果都不像投递链接就保持 detail_url 为空]:\n{qr_block}\n\n{user_content}'
        )

    # Phase 2 (2026-05-24): pro + reasoning_effort=high。老师端是 admin one-shot
    # 解析,质量决定 ingest 进知识库的岗位准确度,值 pro。
    payload = {
        'model': client.model,
        'temperature': 0.1,
        'response_format': {'type': 'json_object'},
        'reasoning_effort': 'high',
        'max_tokens': 8000,
        'messages': [
            {'role': 'system', 'content': _LLM_SYSTEM_PROMPT},
            {'role': 'user', 'content': user_content},
        ],
    }
    req = urllib_request.Request(
        client.chat_completions_url,
        data=json.dumps(payload).encode('utf-8'),
        headers={
            'Authorization': f'Bearer {client.api_key}',
            'Content-Type': 'application/json',
        },
        method='POST',
    )
    try:
        with urllib_request.urlopen(req, timeout=client.timeout_seconds) as resp:
            body = resp.read().decode('utf-8', errors='replace')
    except Exception as exc:
        # 网络/超时/解码/连接断开等都视为 LLM 不可用，回落 heuristic
        logger.warning('teacher_entry LLM request failed: %s', exc)
        return None

    try:
        envelope = json.loads(body)
        content = envelope['choices'][0]['message']['content']
        data = json.loads(content)
    except Exception as exc:
        logger.warning('teacher_entry LLM response unparseable: %s', exc)
        return None

    # 兼容三种返回形态：
    #   { "jobs": [ {...}, {...} ] }   — 推荐
    #   [ {...}, {...} ]               — 偶尔 LLM 直出列表
    #   { ...一个岗位... }             — 万一 LLM 忘了包 jobs 字段
    items_raw: list = []
    if isinstance(data, dict):
        if 'jobs' in data and isinstance(data['jobs'], list):
            items_raw = data['jobs']
        elif any(k in data for k in ('title', 'company', 'jd_summary')):
            items_raw = [data]
    elif isinstance(data, list):
        items_raw = data

    out: list[ParsedDraft] = []
    for item in items_raw[:10]:
        if isinstance(item, dict):
            out.append(_coerce_parsed(item))
    return out


def _coerce_parsed(data: dict) -> ParsedDraft:
    track = str(data.get('suggested_track') or 'other').strip().lower()
    if track not in {'finance', 'fintech', 'other'}:
        track = 'other'

    tags_raw = data.get('suggested_tags') or []
    tags: list[str] = []
    if isinstance(tags_raw, list):
        for t in tags_raw[:4]:
            if isinstance(t, str) and t.strip():
                tags.append(t.strip())

    try:
        confidence = float(data.get('confidence') or 0)
    except (TypeError, ValueError):
        confidence = 0.0
    confidence = max(0.0, min(100.0, confidence))

    company_clean = str(data.get('company') or '').strip()
    if not company_clean or _COMPANY_PLACEHOLDER_RE.match(company_clean):
        confidence = min(confidence, 50.0)

    return ParsedDraft(
        title=str(data.get('title') or '').strip(),
        company=company_clean,
        location=str(data.get('location') or '').strip(),
        jd_summary=str(data.get('jd_summary') or '').strip(),
        deadline=str(data.get('deadline') or '').strip(),
        salary=str(data.get('salary') or '').strip(),
        detail_url=str(data.get('detail_url') or '').strip(),
        suggested_track=track,
        suggested_tags=tags,
        confidence=confidence,
    )


# ---------------- Heuristic fallback ----------------

# Company-name 占位/缺失检测 — 命中后 confidence 强制压到 ≤50，
# 避免老师对一条没公司名的高信心 draft 直接 submit。
_COMPANY_PLACEHOLDER_RE = re.compile(
    r'^[?？_\-\s.·、]*$|^(未知|未识别|未提供|unknown|n/?a|null|none)$',
    re.IGNORECASE,
)

_TITLE_HINT_RE = re.compile(r'(?:岗位|职位|招聘)[：:\s]*([^\n。]{2,40})')
_FIN_HINT_RE = re.compile(r'量化|投行|资管|券商|银行|保险|信托|基金|PE|VC|风控|信贷|理财')
_FINTECH_HINT_RE = re.compile(r'AI|算法|数据|后端|前端|工程师|开发|model|LLM', re.IGNORECASE)


def _heuristic_extract(text: str) -> ParsedDraft:
    """Best-effort regex-only fallback when LLM is unavailable."""
    title_match = _TITLE_HINT_RE.search(text)
    title = title_match.group(1).strip() if title_match else (text.split('\n', 1)[0][:40] or '未识别岗位')

    company = ''
    for c in _COMPANY_HINTS:
        if c in text:
            company = c
            break

    location = ''
    for loc in _LOCATION_HINTS:
        if loc in text:
            location = loc
            break

    if _FIN_HINT_RE.search(text):
        track = 'finance'
    elif _FINTECH_HINT_RE.search(text):
        track = 'fintech'
    else:
        track = 'other'

    tags: list[str] = []
    if location:
        tags.append(location)
    if _FIN_HINT_RE.search(text):
        tags.append('金融')

    summary = ' '.join(text.split())[:80]

    return ParsedDraft(
        title=title,
        company=company,
        location=location,
        jd_summary=summary,
        suggested_track=track,
        suggested_tags=tags,
        confidence=40.0,  # 启发式置信度恒定 40
    )
