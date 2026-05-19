import json
from typing import Any, Callable
from urllib import request as urllib_request

from app.schemas_resume_copilot import (
    ResumePreferencePayload,
    ResumeProfilePayload,
    ResumeRecommendationItem,
)
from app.services.resume_copilot.agent.budget import AgentBudget
from app.services.resume_copilot.agent.prompt import build_system_prompt
from app.services.resume_copilot.agent.tools import ToolResult
from app.services.resume_copilot.llm import build_resume_llm_client

TraceRecorder = Callable[..., None]


def _normalize_tool_args(tool_name: str, args: dict) -> dict:
    """Fix common LLM argument hallucinations before calling the tool."""
    if tool_name == 'get_company_intel':
        # LLM often passes company_names (plural list) instead of company_name (str)
        if 'company_names' in args and 'company_name' not in args:
            names = args['company_names']
            args = {**args, 'company_name': names[0] if isinstance(names, list) and names else str(names)}
            del args['company_names']  # type: ignore[reportArgumentType]
        # Drop any unknown keys
        return {k: v for k, v in args.items() if k == 'company_name'}
    if tool_name == 'search_candidates':
        # LLM sometimes adds limit= or top_k=
        return {k: v for k, v in args.items() if k in ('query', 'filters')}
    if tool_name == 'inspect_jobs':
        return {k: v for k, v in args.items() if k == 'job_ids'}
    # Phase 0 (D-4): 'search_web' arg normalizer removed with the tool.
    return args


_FORCE_FINISH = (
    '\n\n⚠️ BUDGET_EXHAUSTED — Call finalize NOW with the best candidates you have. '
    'Return JSON with action="finalize" and no other tool.'
)
_MALFORMED_RETRY = (
    '\n\nYour previous response was not valid JSON. '
    'Return ONLY a JSON object with keys: thought, action, args, reasoning_display.'
)


def _call_llm(messages: list[dict], timeout_seconds: int = 30) -> str:
    client = build_resume_llm_client()
    payload = {
        'model': client.model,
        'response_format': {'type': 'json_object'},
        'messages': messages,
        'stream': False,
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
    with urllib_request.urlopen(req, timeout=timeout_seconds) as response:
        body = json.loads(response.read().decode('utf-8'))
    return body['choices'][0]['message']['content']


def _coerce_recommendation(
    raw: Any,
    candidates_by_id: dict[str, ResumeRecommendationItem],
) -> ResumeRecommendationItem | None:
    if not isinstance(raw, dict):
        return None
    job_id = str(raw.get('job_id', ''))
    base = candidates_by_id.get(job_id)
    if base is None:
        return None
    return base.model_copy(update={
        'final_score': int(raw.get('final_score', base.final_score) or 0),
        'used_ai': True,
        'why_recommended': [str(v) for v in raw.get('why_recommended', [])],
        'strengths': [str(v) for v in raw.get('strengths', [])],
        'risks': [str(v) for v in raw.get('risks', [])],
        'target_direction': str(raw.get('target_direction', '') or ''),
    })


class ReActAgent:
    def __init__(self, tools: dict[str, Callable], budget: AgentBudget | None = None) -> None:
        self.tools = tools
        self.budget = budget or AgentBudget()

    def run(
        self,
        profile: ResumeProfilePayload,
        preferences: ResumePreferencePayload | None,
        candidates: list[ResumeRecommendationItem],
        trace_recorder: TraceRecorder | None = None,
        direction_results: list | None = None,
    ) -> list[ResumeRecommendationItem]:
        candidates_by_id = {item.job_id: item for item in candidates}
        client = build_resume_llm_client()
        messages: list[dict] = [
            {'role': 'system', 'content': build_system_prompt(profile, preferences, candidates, self.budget, direction_results=direction_results)}
        ]
        step_index = 0
        _force_finish_sent = False

        while True:
            # Inject force-finish once when time or total budget is up
            if not self.budget.is_time_ok() and not _force_finish_sent:
                messages.append({'role': 'user', 'content': _FORCE_FINISH})
                _force_finish_sent = True
            elif _force_finish_sent and not self.budget.is_time_ok():
                # LLM ignored force-finish — give up
                return self._fallback(candidates)

            # Call LLM
            last_content = '{}'
            try:
                last_content = _call_llm(messages, timeout_seconds=min(30, client.timeout_seconds))
                parsed = json.loads(last_content)
            except (json.JSONDecodeError, KeyError, Exception):
                # Retry once
                messages.append({'role': 'assistant', 'content': last_content})
                messages.append({'role': 'user', 'content': _MALFORMED_RETRY})
                try:
                    last_content = _call_llm(messages, timeout_seconds=min(30, client.timeout_seconds))
                    parsed = json.loads(last_content)
                except Exception:
                    return self._fallback(candidates)

            action = str(parsed.get('action', ''))
            args = parsed.get('args', {})
            reasoning_display = str(parsed.get('reasoning_display', ''))
            step_index += 1

            # Emit "running" trace so spinner appears immediately
            if trace_recorder:
                trace_recorder(
                    message=reasoning_display,
                    status='running',
                    tool=action,
                    step_index=step_index,
                    result_summary='',
                )

            # Handle finalize
            if action == 'finalize':
                recs_raw = args.get('recommendations', []) if isinstance(args, dict) else []
                results = [
                    r for r in (
                        _coerce_recommendation(raw, candidates_by_id) for raw in recs_raw
                    )
                    if r is not None
                ]
                if not results:
                    results = list(candidates[:10])
                results.sort(key=lambda x: x.final_score, reverse=True)
                if trace_recorder:
                    trace_recorder(
                        message=reasoning_display,
                        status='completed',
                        tool='finalize',
                        step_index=step_index,
                        result_summary=f'输出 {len(results)} 个推荐岗位',
                    )
                return results

            # Check for unknown tool before budget (so UNKNOWN_TOOL observation is returned)
            tool_fn = self.tools.get(action)
            if tool_fn is None and action != 'finalize':
                observation = f'UNKNOWN_TOOL: {action}'
                messages.append({'role': 'assistant', 'content': last_content})
                messages.append({'role': 'user', 'content': f'Observation: {observation}'})
                continue

            # Check budget
            allowed, budget_reason = self.budget.check(action)
            if not allowed:
                if budget_reason in ('TOTAL_BUDGET_EXHAUSTED', 'TIME_BUDGET_EXHAUSTED'):
                    if trace_recorder:
                        trace_recorder(
                            message='预算已用完，正在生成最终推荐',
                            status='completed',
                            tool=action,
                            step_index=step_index,
                            result_summary=budget_reason,
                        )
                    if not _force_finish_sent:
                        messages.append({'role': 'assistant', 'content': last_content})
                        messages.append({'role': 'user', 'content': _FORCE_FINISH})
                        _force_finish_sent = True
                    continue
                observation = f'TOOL_LIMIT_REACHED for {action}'
                messages.append({'role': 'assistant', 'content': last_content})
                messages.append({'role': 'user', 'content': f'Observation: {observation}'})
                continue

            # Execute tool
            if tool_fn is None:
                observation = f'UNKNOWN_TOOL: {action}'
                result_summary = observation
            else:
                try:
                    call_args = _normalize_tool_args(action, args if isinstance(args, dict) else {})
                    tool_result: ToolResult = tool_fn(**call_args)
                    self.budget.record(action)
                    observation = (
                        json.dumps(tool_result.data, ensure_ascii=False)
                        if tool_result.data is not None
                        else tool_result.summary
                    )
                    result_summary = tool_result.summary
                except Exception as exc:
                    observation = f'TOOL_ERROR: {exc}'
                    result_summary = f'工具出错：{exc}'

            if trace_recorder:
                trace_recorder(
                    message=reasoning_display,
                    status='completed',
                    tool=action,
                    step_index=step_index,
                    result_summary=result_summary,
                )

            # Rebuild system prompt with updated budget remaining counts
            messages[0] = {
                'role': 'system',
                'content': build_system_prompt(profile, preferences, candidates, self.budget, direction_results=direction_results),
            }
            messages.append({'role': 'assistant', 'content': last_content})
            messages.append({'role': 'user', 'content': f'Observation: {observation}'})

    def _fallback(self, candidates: list[ResumeRecommendationItem]) -> list[ResumeRecommendationItem]:
        return list(candidates[:10])
