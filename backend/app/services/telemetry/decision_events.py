"""决策事件埋点的写入 + 聚合 (2026-06-06)。

这是整个产品里 fallback / 护栏 / 分支触发的**单一落点**:所有想知道
"这个分支到底有没有真在触发、命中率多少"的地方,都调 record_event 写一条,
之后一句 SQL 即可回答。设计思路与 Context Registry / Subagent base 一致 ——
**埋点是 best-effort, 永不拖垮主流程**。

铁律:
  - record_event 永不 raise;任何异常吞掉 + warning, 返回 False。
  - 自开短生命周期 session 写自己的 row, **不碰调用方的事务**
    (避免误 commit 调用方半成品 / 把埋点失败传染给主逻辑)。
  - detail 只存够定位的最小信息;**禁止灌简历原文 / PII** (SAIF 学生账号)。
"""
from __future__ import annotations

import json
import logging
import os
from typing import Any, Callable

logger = logging.getLogger(__name__)

# detail_json 截断上限 — 防止误塞大对象 (本就只该放最小定位信息)。
_DETAIL_MAX_CHARS = 2000


def _enabled() -> bool:
    """埋点总开关 — 默认 OFF (与项目 strangler-fig flag 习惯一致: flag-OFF =
    与上线前 byte-identical)。dev/prod 在 .env.local 里 export
    DECISION_TELEMETRY_ENABLED=1 打开。"""
    return os.environ.get("DECISION_TELEMETRY_ENABLED", "0") == "1"


def _default_factory() -> Callable[[], Any]:
    from app.database import SessionLocal

    return SessionLocal


def record_event(
    event_name: str,
    *,
    session_id: int | None = None,
    purpose: str | None = None,
    hit: bool = True,
    detail: dict[str, Any] | None = None,
    session_factory: Callable[[], Any] | None = None,
) -> bool:
    """写一条决策事件。返回 True=写成功, False=失败(已吞)。永不 raise。

    Args:
        event_name: 事件名 (如 'recall_thin' / 'canonicalize_unmapped' / 'company_fallback')
        session_id: 关联的 resume_copilot session (可空)
        purpose: 场景 (如 'recommendation' / 'parse' / 'platforms')
        hit: 该事件语义下"命中/触发"为 True (fallback 触发即 True)
        detail: 最小定位信息 dict, **禁 PII**;序列化后超 2000 字截断
        session_factory: 注入用 (测试);显式传入即视为测试路径, 绕过总开关。
            默认 None → 走 app.database.SessionLocal, 受 DECISION_TELEMETRY_ENABLED 控制。
    """
    try:
        # flag OFF 且非测试注入 → no-op。显式传 session_factory (单测) 仍走写入路径。
        if session_factory is None and not _enabled():
            return False
        from app.models import DecisionEvent

        factory = session_factory or _default_factory()
        detail_json = (
            json.dumps(detail, ensure_ascii=False)[:_DETAIL_MAX_CHARS]
            if detail
            else None
        )
        s = factory()
        try:
            s.add(
                DecisionEvent(
                    event_name=event_name,
                    session_id=session_id,
                    purpose=purpose,
                    hit=hit,
                    detail_json=detail_json,
                )
            )
            s.commit()
            return True
        finally:
            s.close()
    except Exception:  # noqa: BLE001 — 埋点失败绝不传播
        logger.warning("record_event(%s) failed", event_name, exc_info=True)
        return False


def event_counts(
    *, session_factory: Callable[[], Any] | None = None
) -> dict[str, int]:
    """按 event_name 聚合计数。失败返回空 dict (永不 raise)。"""
    try:
        from sqlalchemy import func

        from app.models import DecisionEvent

        factory = session_factory or _default_factory()
        s = factory()
        try:
            rows = (
                s.query(DecisionEvent.event_name, func.count())
                .group_by(DecisionEvent.event_name)
                .all()
            )
            return {name: int(n) for name, n in rows}
        finally:
            s.close()
    except Exception:  # noqa: BLE001
        logger.warning("event_counts failed", exc_info=True)
        return {}
