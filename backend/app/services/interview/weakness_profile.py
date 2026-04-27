"""Aggregate per-turn scoring into a session-level weakness profile.

Pure function — no I/O, no LLM. Caller passes a list of score_json strings
(typically from `interview_turns.score_json`) and gets back a structured
profile that downstream consumers (adaptive picker, report) can use.
"""
from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass, field


@dataclass(slots=True)
class WeaknessProfile:
    avg_score: int | None = None
    weak_topics: list[str] = field(default_factory=list)
    strong_topics: list[str] = field(default_factory=list)
    gap_warnings: list[str] = field(default_factory=list)


def compute_weakness(score_jsons: list[str | None]) -> WeaknessProfile:
    """Aggregate a list of score_json strings into a weakness profile.

    Malformed JSON entries are silently skipped (not raised). None entries
    are also skipped — they represent turns whose score hasn't been computed
    yet.
    """
    profile = WeaknessProfile()
    overalls: list[int] = []
    miss_counter: Counter[str] = Counter()
    hit_counter: Counter[str] = Counter()

    for raw in score_jsons:
        if not raw:
            continue
        try:
            obj = json.loads(raw) if isinstance(raw, str) else raw
        except (json.JSONDecodeError, ValueError):
            continue
        if not isinstance(obj, dict):
            continue

        try:
            overalls.append(int(obj.get("overall", 0)))
        except (TypeError, ValueError):
            pass

        for miss in obj.get("misses") or []:
            if isinstance(miss, str) and miss.strip():
                miss_counter[miss.strip()] += 1
        for hit in obj.get("hits") or []:
            if isinstance(hit, str) and hit.strip():
                hit_counter[hit.strip()] += 1

    if overalls:
        profile.avg_score = round(sum(overalls) / len(overalls))

    profile.weak_topics = [t for t, _ in miss_counter.most_common(5)]
    profile.strong_topics = [t for t, _ in hit_counter.most_common(5)]

    if profile.avg_score is not None and profile.avg_score < 60:
        profile.gap_warnings.append("整体分数偏低，建议针对薄弱主题反复练习")

    return profile
