"""Provider registry + fetch helpers.

Module-level state is intentional: providers register at app startup, gateway
code reads them per request. Registration is single-process; no thread safety
needed beyond Python's GIL because the list is append-only after bootstrap().
"""
from __future__ import annotations

import logging
import os

from app.services.llm_context.base import ContextProvider, ContextRequest

logger = logging.getLogger(__name__)
_PROVIDERS: list[ContextProvider] = []

# 是否开 token trace log。为 phase D (加 5th provider) 排雷:测当前 4 provider
# 的实际 token 占用,看距离 context 上限还有多少 headroom。
#   LLM_CTX_TRACE=1   每次 fetch_blocks 打一行 [ctx_trace] 到 logger.info
#   LLM_CTX_TRACE=0   关 (默认; 生产想开就 export 一下)
_TRACE_ENABLED = os.environ.get("LLM_CTX_TRACE", "0") == "1"

# Chinese-mixed text 的粗 token 估算: 平均 2.0 chars/token (DeepSeek/Qwen).
# 英文 ~3.5, 数字/符号 ~4-5。混合中文以 2.0 为下限,保守估高。
_CHARS_PER_TOKEN = 2.0


def _est_tokens(s: str) -> int:
    return max(1, int(len(s or "") / _CHARS_PER_TOKEN))


def register(provider: ContextProvider) -> None:
    """Add a provider. Call from bootstrap(). Idempotent on (name)."""
    existing = {p.name for p in _PROVIDERS}
    if provider.name in existing:
        return
    _PROVIDERS.append(provider)


def registered_names() -> list[str]:
    return [p.name for p in _PROVIDERS]


def _allowed(provider: ContextProvider, allow: set[str] | None) -> bool:
    if allow is not None:
        return provider.name in allow
    # Optional ENV gate: LLM_CONTEXT_PROVIDERS=podcast,memory selects subset.
    env = os.environ.get("LLM_CONTEXT_PROVIDERS", "").strip()
    if env:
        return provider.name in {x.strip() for x in env.split(",") if x.strip()}
    return True


def fetch_blocks(req: ContextRequest, *, allow: set[str] | None = None) -> list[str]:
    """Run all applicable providers; return their non-empty output blocks.

    A provider that raises is silently logged and skipped — context is best-effort
    and must never break the gateway LLM call.

    A provider may return ``(block, terminate=True)`` to short-circuit the
    pipeline (used by SensitiveTopicProvider). When that happens the block is
    appended and remaining providers are skipped.
    """
    out: list[str] = []
    # trace 记录: [(provider_name, chars, est_tokens, applied, terminated), ...]
    trace: list[tuple[str, int, int, bool, bool]] = [] if _TRACE_ENABLED else []
    for p in _PROVIDERS:
        if not _allowed(p, allow):
            continue
        try:
            if not p.applies_to(req):
                if _TRACE_ENABLED:
                    trace.append((p.name, 0, 0, False, False))
                continue
            result = p.fetch(req)
        except Exception as exc:
            logger.warning("provider %s fetch failed: %s", p.name, exc)
            if _TRACE_ENABLED:
                trace.append((p.name, 0, 0, False, False))
            continue
        if isinstance(result, tuple):
            block, terminate = result
        else:
            block, terminate = result, False
        if block and block.strip():
            out.append(block)
            if _TRACE_ENABLED:
                trace.append((p.name, len(block), _est_tokens(block), True, terminate))
        elif _TRACE_ENABLED:
            trace.append((p.name, 0, 0, True, terminate))
        if terminate:
            logger.info("provider %s requested early-terminate; skipping remaining providers", p.name)
            break

    if _TRACE_ENABLED:
        per_prov = ", ".join(
            f"{name}={chars}c/{tok}t{'!' if term else ''}{'' if applied else 'X'}"
            for name, chars, tok, applied, term in trace
        )
        total_chars = sum(c for _, c, _, _, _ in trace)
        total_tok = sum(t for _, _, t, _, _ in trace)
        logger.info(
            "[ctx_trace] purpose=%s providers=%d blocks=%d total=%dc/%dt · %s",
            getattr(req, "purpose", "?"),
            len(trace), len(out), total_chars, total_tok, per_prov,
        )
    return out


def fetch_blocks_for_jobs(
    base_req: ContextRequest,
    jobs: list[dict],
    *,
    allow: set[str] | None = None,
) -> dict[str, list[str]]:
    """Convenience for per-item providers (recommendation rerank).

    Returns {job["id"]: [block, ...]} for each job with at least one non-empty
    contribution. base_req carries shared fields (db, profile, preferences);
    we shallow-copy and inject .job per iteration.
    """
    from dataclasses import replace
    out: dict[str, list[str]] = {}
    for j in jobs:
        job_id = str(j.get("id") or "")
        if not job_id:
            continue
        sub_req = replace(base_req, job=j)
        blocks = fetch_blocks(sub_req, allow=allow)
        if blocks:
            out[job_id] = blocks
    return out


def format_per_job_aggregated(by_job_id: dict[str, list[str]], *, header: str) -> str:
    """Concatenate per-job blocks (from any number of providers) into a single
    prompt-ready string. Each job's blocks are grouped under a `job_id=...` line."""
    if not by_job_id:
        return ""
    sections = [f"[{header}]"]
    for job_id, blocks in by_job_id.items():
        if not blocks:
            continue
        sections.append(f"\njob_id={job_id}:")
        for block in blocks:
            for line in block.split("\n"):
                sections.append(f"  {line}")
    return "\n".join(sections)
