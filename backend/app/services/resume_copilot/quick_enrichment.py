import json
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor, wait as futures_wait
from dataclasses import dataclass
from html import unescape
from typing import Callable
from urllib import parse, request
from urllib.error import HTTPError, URLError

from app import config
from app.models import Job
from app.schemas_resume_copilot import (
    ResumeAgentTraceItem,
    ResumePreferencePayload,
    ResumeProfilePayload,
    ResumeQuickEnrichmentProfile,
    ResumeQuickEnrichmentSource,
    ResumeRecommendationItem,
)
from app.services.resume_copilot.llm import build_resume_llm_client

TraceRecorder = Callable[[str, str, str], None]


@dataclass(slots=True)
class SearchResult:
    title: str
    url: str
    snippet: str = ''


def _http_json(
    url: str,
    payload: dict | None = None,
    headers: dict[str, str] | None = None,
    timeout: int = 12,
) -> dict:
    request_headers = {
        'User-Agent': 'Mozilla/5.0',
        'Accept': 'application/json',
    }
    if headers:
        request_headers.update(headers)
    data = None
    if payload is not None:
        data = json.dumps(payload).encode('utf-8')
        request_headers['Content-Type'] = 'application/json'
    req = request.Request(url, data=data, headers=request_headers, method='POST' if payload is not None else 'GET')
    with request.urlopen(req, timeout=timeout) as response:
        return json.loads(response.read().decode('utf-8'))


def _http_text(url: str, timeout: int = 12) -> str:
    req = request.Request(
        url,
        headers={
            'User-Agent': 'Mozilla/5.0',
            'Accept': 'text/html,text/plain;q=0.9,*/*;q=0.8',
        },
    )
    with request.urlopen(req, timeout=timeout) as response:
        return response.read().decode('utf-8', 'ignore')


def _call_chat_json(system_prompt: str, user_payload: dict, timeout_seconds: int | None = None) -> dict:
    client = build_resume_llm_client()
    payload = {
        'model': client.model,
        'response_format': {'type': 'json_object'},
        'messages': [
            {'role': 'system', 'content': system_prompt},
            {'role': 'user', 'content': json.dumps(user_payload, ensure_ascii=False)},
        ],
        'stream': False,
    }
    req = request.Request(
        client.chat_completions_url,
        data=json.dumps(payload).encode('utf-8'),
        headers={
            'Authorization': f'Bearer {client.api_key}',
            'Content-Type': 'application/json',
        },
        method='POST',
    )
    with request.urlopen(req, timeout=timeout_seconds or client.timeout_seconds) as response:
        body = json.loads(response.read().decode('utf-8'))
    content = body['choices'][0]['message']['content']
    return json.loads(content)


def _build_fallback_queries(job: Job, track_label: str, role_family: str) -> list[str]:
    company = str(job.company or '').strip()
    title = str(job.job_title or '').strip()
    department = str(job.department or '').strip()
    base_queries = [
        f'{company} {title} 校招 职责 部门',
        f'{company} {title} 面经 岗位 方向',
        f'{company} {department or title} 技术 业务 团队',
        f'{company} {track_label or role_family or title} 岗位 业务',
    ]
    deduped: list[str] = []
    for item in base_queries:
        normalized = ' '.join(item.split())
        if normalized and normalized not in deduped:
            deduped.append(normalized)
    return deduped[: max(2, config.RESUME_COPILOT_QUICK_ENRICHMENT_QUERY_COUNT)]


def generate_search_queries(
    job: Job,
    recommendation: ResumeRecommendationItem,
    profile: ResumeProfilePayload,
    preferences: ResumePreferencePayload | None,
) -> list[str]:
    fallback_queries = _build_fallback_queries(job, recommendation.matched_track_label, recommendation.matched_role_family)
    client = build_resume_llm_client()
    if not client.api_key:
        return fallback_queries

    try:
        result = _call_chat_json(
            (
                'You generate 2-4 short Chinese search queries for quick job intelligence enrichment. '
                'Return JSON with key queries. Focus on role orientation, team, responsibilities, and candidate fit.'
            ),
            {
                'company': job.company,
                'department': job.department,
                'job_title': job.job_title,
                'matched_track': recommendation.matched_track_label,
                'matched_role_family': recommendation.matched_role_family,
                'candidate_summary': profile.candidate_summary,
                'preferred_tracks': preferences.preferred_tracks if preferences else [],
            },
            timeout_seconds=min(client.timeout_seconds, 10),
        )
        raw_queries = result.get('queries', [])
        queries = []
        for value in raw_queries:
            normalized = ' '.join(str(value).split())
            if normalized and normalized not in queries:
                queries.append(normalized)
        return queries[: max(2, config.RESUME_COPILOT_QUICK_ENRICHMENT_QUERY_COUNT)] or fallback_queries
    except Exception:
        return fallback_queries


def search_with_tavily(query: str, max_results: int = 3) -> list[SearchResult]:
    if not config.TAVILY_API_KEY:
        return []
    response = _http_json(
        'https://api.tavily.com/search',
        payload={
            'api_key': config.TAVILY_API_KEY,
            'query': query,
            'search_depth': 'basic',
            'max_results': max_results,
            'include_raw_content': False,
            'include_answer': False,
        },
        timeout=10,
    )
    results = []
    for item in response.get('results', [])[:max_results]:
        url = str(item.get('url', '') or '')
        if not url:
            continue
        results.append(
            SearchResult(
                title=str(item.get('title', '') or ''),
                url=url,
                snippet=str(item.get('content', '') or item.get('snippet', '') or ''),
            )
        )
    return results


def search_with_duckduckgo(query: str, max_results: int = 3) -> list[SearchResult]:
    html = _http_text(f'https://html.duckduckgo.com/html/?q={parse.quote(query)}', timeout=10)
    pattern = re.compile(
        r'<a[^>]*class="result__a"[^>]*href="(?P<url>[^"]+)"[^>]*>(?P<title>.*?)</a>.*?(?:<a[^>]*class="result__snippet"[^>]*>(?P<snippet>.*?)</a>|<div[^>]*class="result__snippet"[^>]*>(?P<snippet_div>.*?)</div>)',
        re.S,
    )
    results: list[SearchResult] = []
    for match in pattern.finditer(html):
        url = unescape(re.sub(r'<.*?>', '', match.group('url') or '')).strip()
        title = unescape(re.sub(r'<.*?>', '', match.group('title') or '')).strip()
        snippet = unescape(re.sub(r'<.*?>', '', match.group('snippet') or match.group('snippet_div') or '')).strip()
        if not url or not title:
            continue
        results.append(SearchResult(title=title, url=url, snippet=snippet))
        if len(results) >= max_results:
            break
    return results


def search_web(query: str, max_results: int = 3) -> list[SearchResult]:
    try:
        tavily_results = search_with_tavily(query, max_results=max_results)
        if tavily_results:
            return tavily_results
    except Exception:
        pass
    if not config.RESUME_COPILOT_ALLOW_PUBLIC_SEARCH_FALLBACK:
        return []
    try:
        return search_with_duckduckgo(query, max_results=max_results)
    except Exception:
        return []


def extract_with_jina_reader(url: str) -> str:
    request_url = f'https://r.jina.ai/http://{url}' if not url.startswith('http://') and not url.startswith('https://') else f'https://r.jina.ai/{url}'
    return _http_text(request_url, timeout=12)


def extract_with_firecrawl(url: str) -> str:
    if not config.FIRECRAWL_API_KEY:
        return ''
    response = _http_json(
        'https://api.firecrawl.dev/v1/scrape',
        payload={'url': url, 'formats': ['markdown']},
        headers={'Authorization': f'Bearer {config.FIRECRAWL_API_KEY}'},
        timeout=12,
    )
    data = response.get('data') or {}
    return str(data.get('markdown', '') or '')


def extract_page_text(url: str) -> str:
    try:
        content = extract_with_firecrawl(url)
        if content:
            return content
    except Exception:
        pass
    try:
        return extract_with_jina_reader(url)
    except Exception:
        return ''


def summarize_lightweight_profile(
    job: Job,
    recommendation: ResumeRecommendationItem,
    queries: list[str],
    search_results: list[SearchResult],
    extracted_pages: list[str],
) -> ResumeQuickEnrichmentProfile:
    client = build_resume_llm_client()
    fallback = ResumeQuickEnrichmentProfile(
        summary='暂未拿到足够公开信息，先按岗位标题与 JD 做基础判断。',
        likely_orientation='待确认',
        likely_department=str(job.department or '') or '待确认',
        target_track_fit=recommendation.matched_track_label or '待确认',
        uncertainty_points=['公开网页证据不足'],
        search_queries=queries,
        sources=[
            ResumeQuickEnrichmentSource(title=item.title, url=item.url, snippet=item.snippet)
            for item in search_results[:3]
        ],
    )
    if not client.api_key:
        return fallback

    try:
        result = _call_chat_json(
            (
                'You summarize quick web evidence for a campus recruiting role. '
                'Return JSON with keys: summary, likely_orientation, likely_department, '
                'target_track_fit, uncertainty_points. Keep it short and concrete in Chinese.'
            ),
            {
                'company': job.company,
                'job_title': job.job_title,
                'department': job.department,
                'matched_track': recommendation.matched_track_label,
                'matched_role_family': recommendation.matched_role_family,
                'search_queries': queries,
                'search_results': [
                    {'title': item.title, 'url': item.url, 'snippet': item.snippet}
                    for item in search_results[:4]
                ],
                'page_evidence': extracted_pages[:2],
            },
            timeout_seconds=min(client.timeout_seconds, 12),
        )
        return ResumeQuickEnrichmentProfile(
            summary=str(result.get('summary', '') or fallback.summary),
            likely_orientation=str(result.get('likely_orientation', '') or '待确认'),
            likely_department=str(result.get('likely_department', '') or fallback.likely_department),
            target_track_fit=str(result.get('target_track_fit', '') or fallback.target_track_fit),
            uncertainty_points=[str(value) for value in result.get('uncertainty_points', []) if str(value).strip()] or fallback.uncertainty_points,
            search_queries=queries,
            sources=[
                ResumeQuickEnrichmentSource(title=item.title, url=item.url, snippet=item.snippet)
                for item in search_results[:3]
            ],
        )
    except Exception:
        return fallback


def _fit_score_delta(target_track_fit: str) -> int:
    lowered = target_track_fit.lower()
    if any(keyword in lowered for keyword in ('强匹配', '高度匹配', '很像', '匹配度高', 'strong')):
        return 5
    if any(keyword in lowered for keyword in ('中等', '部分', '还算', 'medium', '一般匹配')):
        return 2
    if any(keyword in lowered for keyword in ('偏离', '较弱', '不太像', 'weak', '低匹配')):
        return -4
    return 0


def _enrich_single_job(
    index: int,
    item: ResumeRecommendationItem,
    job: Job,
    profile: ResumeProfilePayload,
    preferences: ResumePreferencePayload | None,
    deadline: float,
    search_cache: dict,
    cache_lock: threading.Lock,
) -> tuple[int, ResumeRecommendationItem, list[tuple[str, str, str]]]:
    """Enrich one job with web search + LLM summarization.

    Returns (index, updated_item, trace_events). Trace events are replayed
    sequentially by the caller so DB writes stay single-threaded.
    """
    trace_events: list[tuple[str, str, str]] = []

    if time.monotonic() >= deadline:
        return index, item, trace_events

    trace_events.append(('Agent 1', f'为「{item.job_title}」生成检索 query。', 'running'))
    queries = generate_search_queries(job, item, profile, preferences)
    trace_events.append(('Agent 1', f'已生成 {len(queries)} 个 query。', 'completed'))

    cache_key = (str(job.company or '').strip(), item.matched_role_family or str(job.job_title or '').strip())
    with cache_lock:
        cached = search_cache.get(cache_key)

    if cached is not None:
        results, extracted_pages = cached
        trace_events.append(('Agent 2', f'命中搜索缓存，{len(results)} 条结果复用。', 'completed'))
        trace_events.append(('Agent 3', f'缓存页面正文 {len(extracted_pages)} 条复用。', 'completed'))
    else:
        results: list[SearchResult] = []
        seen_urls: set[str] = set()
        for query in queries[: max(2, config.RESUME_COPILOT_QUICK_ENRICHMENT_QUERY_COUNT)]:
            if time.monotonic() >= deadline:
                break
            for sr in search_web(query, max_results=3):
                if sr.url not in seen_urls:
                    seen_urls.add(sr.url)
                    results.append(sr)
                    if len(results) >= 4:
                        break
            if len(results) >= 4:
                break

        trace_events.append(('Agent 2', f'搜索命中 {len(results)} 条公开结果。', 'completed' if results else 'running'))

        extracted_pages: list[str] = []
        per_page_budget = max(4.0, (deadline - time.monotonic()) / max(1, len(results[:2])))
        for result in results[:2]:
            if time.monotonic() >= deadline:
                break
            page_text = extract_page_text(result.url)
            if page_text:
                extracted_pages.append(page_text[:5000])
            _ = per_page_budget  # budget computed but extraction timeout is internal

        trace_events.append(('Agent 3', f'抽取 {len(extracted_pages)} 条正文用于轻量画像。', 'completed'))

        with cache_lock:
            if cache_key not in search_cache:
                search_cache[cache_key] = (results, extracted_pages)

    enrichment_profile = summarize_lightweight_profile(job, item, queries, results, extracted_pages)
    score_delta = _fit_score_delta(enrichment_profile.target_track_fit)
    has_public_evidence = bool(results or extracted_pages)

    updated_item = item.model_copy(
        update={
            'quick_enrichment_profile': enrichment_profile,
            'enhanced_score': max(0, item.enhanced_score + score_delta) if has_public_evidence else item.enhanced_score,
            'final_score': max(0, item.enhanced_score + score_delta) if has_public_evidence else item.final_score,
            'topic_cache_status': 'quick_enriched' if results else item.topic_cache_status,
            'topic_summary': enrichment_profile.summary or item.topic_summary,
            'why_recommended': item.why_recommended + (
                [f'快增强判断：{enrichment_profile.target_track_fit}']
                if has_public_evidence and enrichment_profile.target_track_fit
                else []
            ),
        }
    )

    trace_events.append((
        'Agent 4',
        f'轻量岗位画像完成：{enrichment_profile.likely_orientation or "待确认"}，'
        f'{enrichment_profile.likely_department or "部门待确认"}。',
        'completed',
    ))

    return index, updated_item, trace_events


def enrich_recommendations_quickly(
    profile: ResumeProfilePayload,
    preferences: ResumePreferencePayload | None,
    items: list[ResumeRecommendationItem],
    job_by_job_id: dict[str, Job] | None = None,
    trace_recorder: TraceRecorder | None = None,
) -> list[ResumeRecommendationItem]:
    if not config.RESUME_COPILOT_QUICK_ENRICHMENT_ENABLED or not items:
        return items

    deadline = time.monotonic() + max(8, config.RESUME_COPILOT_QUICK_ENRICHMENT_TIMEOUT_SECONDS)
    enriched_items = list(items)
    top_n = min(len(items), max(1, config.RESUME_COPILOT_QUICK_ENRICHMENT_TOP_N))

    if trace_recorder:
        trace_recorder('Agent 1', f'开始 10–20 秒快增强，并行处理前 {top_n} 个岗位。', 'running')

    search_cache: dict = {}
    cache_lock = threading.Lock()

    job_list = []
    for index in range(top_n):
        item = enriched_items[index]
        job = (job_by_job_id or {}).get(item.job_id) or Job(
            company=item.company,
            job_title=item.job_title,
            department='',
            detail_url=item.detail_url,
            job_req='',
            job_duty='',
        )
        job_list.append((index, item, job))

    remaining = max(0.0, deadline - time.monotonic())
    with ThreadPoolExecutor(max_workers=top_n) as executor:
        futures = {
            executor.submit(_enrich_single_job, idx, itm, jb, profile, preferences, deadline, search_cache, cache_lock): idx
            for idx, itm, jb in job_list
        }
        done, _ = futures_wait(futures.keys(), timeout=remaining)

    for future in done:
        try:
            index, updated_item, trace_events = future.result(timeout=0)
            enriched_items[index] = updated_item
            if trace_recorder:
                for agent, message, status in trace_events:
                    trace_recorder(agent, message, status)
        except Exception:
            pass

    if trace_recorder:
        trace_recorder('Agent 1', '快增强完成，已把轻量岗位画像写回推荐结果。', 'completed')

    return enriched_items


def serialize_agent_trace(items: list[ResumeAgentTraceItem]) -> str:
    return json.dumps([item.model_dump() for item in items], ensure_ascii=False)
