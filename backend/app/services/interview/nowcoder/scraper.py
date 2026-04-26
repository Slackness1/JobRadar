import html
import re
import urllib.parse
import urllib.request
from dataclasses import dataclass

_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
_HEADERS = {"User-Agent": _UA, "Accept-Language": "zh-CN,zh;q=0.9"}
_SEARCH_URL = "https://www.nowcoder.com/search/all?query={q}&type=all"
_POST_URL = "https://www.nowcoder.com/discuss/{pid}"
_TIMEOUT_SECONDS = 20

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
    req = urllib.request.Request(url, headers=_HEADERS)
    with urllib.request.urlopen(req, timeout=_TIMEOUT_SECONDS) as r:
        return r.read().decode("utf-8", errors="replace")


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
        out.append(PostMeta(pid=pid, title=title))
        if len(out) >= limit:
            break
    return out


def fetch_post(pid: str) -> PostDetail:
    url = _POST_URL.format(pid=pid)
    htm = _fetch(url)
    desc_m = _META_DESC_RE.search(htm)
    if not desc_m:
        return PostDetail(pid=pid, company="", interview_date="", position="", questions_text="", parse_status="failed")
    desc = html.unescape(desc_m.group(1))
    desc = re.split(r'_牛客网_', desc, maxsplit=1)[0]

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

    have_any = any(fields.values())
    have_questions = bool(fields["questions_text"])
    if not have_any:
        status = "failed"
    elif not have_questions:
        status = "partial"
    else:
        status = "ok"
    return PostDetail(pid=pid, parse_status=status, **fields)
