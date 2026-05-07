import html
import random
import re
import time
import urllib.parse
from dataclasses import dataclass

import httpx

_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
_HEADERS = {"User-Agent": _UA, "Accept-Language": "zh-CN,zh;q=0.9"}
_SEARCH_URL = "https://www.nowcoder.com/search/all?query={q}&type=all"
_POST_URL = "https://www.nowcoder.com/discuss/{pid}"
_TIMEOUT_SECONDS = 20
_FETCH_MAX_ATTEMPTS = 2  # 1 initial + 1 retry
_FETCH_BACKOFF_BASE_SECONDS = 2.0

# Module-level persistent client: pools TCP/TLS connections across all
# requests in this process. ThreadPoolExecutor workers share it safely
# (httpx.Client is thread-safe). Saves ~150-300ms per request on the
# nowcoder.com handshake — adds up to ~30s/run on a 160-request batch.
_HTTP_CLIENT = httpx.Client(
    headers=_HEADERS,
    timeout=_TIMEOUT_SECONDS,
    follow_redirects=True,
)

_SEARCH_LINK_RE = re.compile(
    r'href="/discuss/(\d+)\?sourceSSR=search"[^>]*>([^<]+)<'
)
_META_DESC_RE = re.compile(r'<meta name="description" content="([^"]+)"')


@dataclass(slots=True, frozen=True)
class PostMeta:
    pid: str
    title: str


@dataclass(slots=True)
class PostDetail:
    pid: str
    company: str
    interview_date: str
    position: str
    questions_text: str
    parse_status: str  # "ok" | "partial" | "failed"


def _fetch(url: str) -> str:
    """Fetch URL with one retry on transient failures (network / 5xx / 429).

    Uses module-level _HTTP_CLIENT so TCP/TLS connections are pooled across
    requests. Backoff before retry is _FETCH_BACKOFF_BASE_SECONDS + jitter.
    Re-raises the last exception after _FETCH_MAX_ATTEMPTS. 4xx (except 429)
    fail fast — retrying a 404 is pointless.
    """
    last_exc: Exception | None = None
    for attempt in range(_FETCH_MAX_ATTEMPTS):
        try:
            r = _HTTP_CLIENT.get(url)
        except httpx.HTTPError as e:  # network / timeout / protocol error
            last_exc = e
        else:
            if r.status_code < 400:
                return r.text
            if r.status_code != 429 and not (500 <= r.status_code < 600):
                r.raise_for_status()  # 4xx non-429 → raise immediately
            last_exc = httpx.HTTPStatusError(
                f"HTTP {r.status_code} from {url}", request=r.request, response=r,
            )
        if attempt + 1 < _FETCH_MAX_ATTEMPTS:
            time.sleep(_FETCH_BACKOFF_BASE_SECONDS + random.uniform(0, 1.0))
    assert last_exc is not None
    raise last_exc


_NOISE_TITLE_RE = re.compile(r'(求面经|求面试|求经验|求帮助|求大佬|求问|求指导|求建议|急求|求带|没人面|有没有人|有人面过|有谁面过|跪求)')


def _is_noise_title(title: str) -> bool:
    return bool(_NOISE_TITLE_RE.search(title))


def search(query: str, limit: int = 10) -> list[PostMeta]:
    url = _SEARCH_URL.format(q=urllib.parse.quote(query))
    htm = _fetch(url)
    out: list[PostMeta] = []
    seen: set[str] = set()
    for m in _SEARCH_LINK_RE.finditer(htm):
        pid, title = m.group(1), m.group(2).strip()
        if pid in seen:
            continue
        seen.add(pid)
        if _is_noise_title(title):
            continue
        out.append(PostMeta(pid=pid, title=title))
        if len(out) >= limit:
            break
    return out


_MIN_QUESTIONS_LEN = 50

# Stopwords that mark the END of a company name in a post title.
# When scanning the leading run of CJK/letters/digits, truncate at the first match.
_TITLE_STOP_RE = re.compile(
    r'(面经|校招|春招|秋招|社招|内推|提前批|实习|笔试|一面|二面|三面|终面|HR面|'
    r'产品|前端|后端|算法|数据|运营|测试|分析师|工程师|开发|经理|研究员|管培生|总行|信科)'
)
# Leading "company-like" run: stops at common separators (space, dash, paren, dot etc.)
_TITLE_HEAD_RE = re.compile(r'^([^-_\s·.（()「【\[]+)')


def parse_company_from_title(title: str) -> str:
    if not title:
        return ""
    head_m = _TITLE_HEAD_RE.match(title.strip())
    if not head_m:
        return ""
    head = head_m.group(1)
    stop_m = _TITLE_STOP_RE.search(head)
    if stop_m:
        head = head[: stop_m.start()]
    return head[:8].strip()


def fetch_post(pid: str, title: str = "") -> PostDetail:
    url = _POST_URL.format(pid=pid)
    htm = _fetch(url)
    desc_m = _META_DESC_RE.search(htm)
    if not desc_m:
        return PostDetail(pid=pid, company="", interview_date="", position="", questions_text="", parse_status="failed")
    desc = html.unescape(desc_m.group(1))
    desc = re.split(r'_牛客网_', desc, maxsplit=1)[0].strip()

    fields = {"company": "", "interview_date": "", "position": "", "questions_text": ""}
    label_map = [
        ("📍面试公司", "company"),
        ("🕐面试时间", "interview_date"),
        ("💻面试岗位", "position"),
        ("❓面试问题", "questions_text"),
        ("面试公司", "company"),
        ("面试时间", "interview_date"),
        ("面试岗位", "position"),
        ("面试问题", "questions_text"),
    ]
    boundary = r'(?=📍|🕐|💻|❓|面试公司|面试时间|面试岗位|面试问题|$)'
    for label, key in label_map:
        if fields[key]:
            continue
        pat = rf'{re.escape(label)}[：: ]\s*(.+?){boundary}'
        m = re.search(pat, desc)
        if m:
            fields[key] = m.group(1).strip()

    # Fallback for free-form posts (the common case): use the whole meta
    # description as the questions text. The summarizer LLM will filter
    # out narrative noise downstream.
    if not fields["questions_text"] and len(desc) >= _MIN_QUESTIONS_LEN:
        fields["questions_text"] = desc

    if not fields["company"] and title:
        fields["company"] = parse_company_from_title(title)

    if fields["questions_text"]:
        status = "ok"
    elif any(fields.values()):
        status = "partial"
    else:
        status = "failed"
    return PostDetail(pid=pid, parse_status=status, **fields)
