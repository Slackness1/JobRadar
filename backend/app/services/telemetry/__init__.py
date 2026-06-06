"""统一决策事件埋点 — 一张表收所有 fallback / 护栏 / 分支的触发。

对外只暴露两个函数:
  - record_event:写一条决策事件 (best-effort, 永不 raise)
  - event_counts:按 event_name 聚合计数 (一句 SQL 回答"哪个分支真在触发")
"""
from app.services.telemetry.decision_events import event_counts, record_event

__all__ = ["record_event", "event_counts"]
