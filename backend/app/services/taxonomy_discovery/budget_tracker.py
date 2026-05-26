"""全局 $10 预算 tracker, 多 subagent 共享, 文件锁防 race (spec §8)。"""
from __future__ import annotations

import fcntl
import json
from collections import defaultdict
from contextlib import contextmanager
from pathlib import Path


class BudgetExceededError(RuntimeError):
    """超预算就 raise, caller 必须 catch 并 graceful stop。"""


class BudgetTracker:
    def __init__(self, state_file: Path, limit_usd: float) -> None:
        self.state_file = Path(state_file)
        self.limit_usd = limit_usd
        if not self.state_file.exists():
            self.state_file.parent.mkdir(parents=True, exist_ok=True)
            self.state_file.write_text(json.dumps({"spent": 0.0, "by_category": {}}))

    @contextmanager
    def _locked(self):
        """文件锁, 避免 6 subagent 并发改同一个 state。"""
        with open(self.state_file, "r+") as f:
            fcntl.flock(f.fileno(), fcntl.LOCK_EX)
            try:
                f.seek(0)
                state = json.load(f)
                yield state
                f.seek(0)
                f.truncate()
                json.dump(state, f)
            finally:
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)

    def spent(self) -> float:
        with self._locked() as s:
            return float(s["spent"])

    def remaining(self) -> float:
        return self.limit_usd - self.spent()

    def can_afford(self, amount_usd: float) -> bool:
        return self.spent() + amount_usd <= self.limit_usd

    def charge(self, amount_usd: float, category: str) -> None:
        with self._locked() as s:
            new_total = float(s["spent"]) + amount_usd
            if new_total > self.limit_usd:
                raise BudgetExceededError(
                    f"charge {amount_usd:.4f} ({category}) 会让总开销 {new_total:.4f} 超过 ${self.limit_usd}"
                )
            s["spent"] = new_total
            by_cat = defaultdict(float, s.get("by_category", {}))
            by_cat[category] += amount_usd
            s["by_category"] = dict(by_cat)

    def breakdown(self) -> dict[str, float]:
        with self._locked() as s:
            return dict(s.get("by_category", {}))
