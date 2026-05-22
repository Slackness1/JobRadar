import time
from dataclasses import dataclass, field

DEFAULT_PER_TOOL_LIMITS: dict[str, int] = {
    'search_candidates': 4,
    'inspect_jobs': 3,
    'get_company_intel': 5,
    # Phase 0 (D-4): 'search_web' tool removed with snapshot system.
    'finalize': 1,
}


@dataclass
class AgentBudget:
    max_total_calls: int = 12
    max_seconds: int = 150
    per_tool_limits: dict[str, int] = field(
        default_factory=lambda: dict(DEFAULT_PER_TOOL_LIMITS)
    )
    _call_counts: dict[str, int] = field(default_factory=dict, init=False, repr=False)
    _start_time: float = field(default_factory=time.monotonic, init=False, repr=False)

    def check(self, tool_name: str) -> tuple[bool, str]:
        """Returns (allowed, rejection_reason). Empty reason means allowed."""
        if not self.is_time_ok():
            return False, 'TIME_BUDGET_EXHAUSTED'
        if tool_name != 'finalize':
            non_finalize = sum(
                v for k, v in self._call_counts.items() if k != 'finalize'
            )
            if non_finalize >= self.max_total_calls:
                return False, 'TOTAL_BUDGET_EXHAUSTED'
        limit = self.per_tool_limits.get(tool_name, 0)
        if self._call_counts.get(tool_name, 0) >= limit:
            return False, 'TOOL_LIMIT_REACHED'
        return True, ''

    def record(self, tool_name: str) -> None:
        self._call_counts[tool_name] = self._call_counts.get(tool_name, 0) + 1

    def remaining(self) -> dict[str, int]:
        return {
            tool: max(0, limit - self._call_counts.get(tool, 0))
            for tool, limit in self.per_tool_limits.items()
        }

    def is_time_ok(self) -> bool:
        return time.monotonic() - self._start_time <= self.max_seconds
