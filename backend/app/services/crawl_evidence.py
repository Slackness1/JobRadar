from __future__ import annotations

import re
from html import unescape
from typing import Iterable, List

from app.services.crawl_taxonomy import CrawlEvidence


def trim_html_snippet(html: str, max_chars: int = 1200) -> str:
    value = (html or "").strip()
    if len(value) <= max_chars:
        return value
    return value[:max_chars]


def extract_text_snippets(html: str, max_items: int = 5, max_chars: int = 180) -> List[str]:
    text = unescape(re.sub(r"<[^>]+>", " ", html or ""))
    text = re.sub(r"\s+", " ", text).strip()
    if not text:
        return []

    chunks = []
    cursor = 0
    while cursor < len(text) and len(chunks) < max_items:
        chunk = text[cursor: cursor + max_chars].strip()
        if chunk:
            chunks.append(chunk)
        cursor += max_chars
    return chunks


def normalize_xhr_urls(urls: Iterable[str], limit: int = 10) -> List[str]:
    seen = set()
    result: List[str] = []
    for url in urls or []:
        value = (url or "").strip()
        if not value or value in seen:
            continue
        seen.add(value)
        result.append(value)
        if len(result) >= limit:
            break
    return result


def build_evidence(
    final_url: str = "",
    page_title: str = "",
    xhr_urls: Iterable[str] | None = None,
    html_initial: str = "",
    html_rendered: str = "",
    dom_count_before: int = 0,
    dom_count_after: int = 0,
    screenshot_path: str = "",
    detected_detail_links: Iterable[str] | None = None,
    ats_fingerprint_hits: Iterable[str] | None = None,
    failure_reason: str = "",
    notes: Iterable[str] | None = None,
) -> CrawlEvidence:
    rendered = html_rendered or html_initial
    return CrawlEvidence(
        final_url=final_url,
        page_title=page_title,
        first_xhr_urls=normalize_xhr_urls(xhr_urls),
        key_text_snippets=extract_text_snippets(rendered),
        html_initial_snippet=trim_html_snippet(html_initial),
        html_rendered_snippet=trim_html_snippet(rendered),
        dom_count_before=dom_count_before,
        dom_count_after=dom_count_after,
        screenshot_path=screenshot_path,
        detected_detail_links=normalize_xhr_urls(detected_detail_links, limit=10),
        ats_fingerprint_hits=normalize_xhr_urls(ats_fingerprint_hits, limit=10),
        failure_reason=failure_reason,
        notes=[note for note in (notes or []) if note],
    )
