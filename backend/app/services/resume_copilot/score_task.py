"""简历打分后台任务 (Hub ③④⑤ 手术的后端半边)。

旧形态: POST /score 同步阻塞 75-90s —— 浏览器长连接占满 6 连接池(「返回工作台」
卡死)、超时即整单作废、前端思考卡只能播 5s 假动画。

新形态: start 立即返回, 打分在服务端线程里跑完(切对话/关页面都不中断 = 「后台
继续跑」), status 轮询拿真实阶段(prepare → llm → parse → done/failed), 完成后的
报告留在进程内存里供报告面板 / 编辑页复用 —— 一次交互只打一遍 LLM。

为什么是进程内存而不是 DB 列: 报告是可重跑的派生数据, 不值得为它加 schema
(且避免与其它会话的 WIP migration 抢 alembic head)。后端重启丢任务 → status
返回 none, 前端诚实提示重跑, 不装完成。
"""
from __future__ import annotations

import json
import logging
import os
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path

from app import config
from app.database import SessionLocal
from app.schemas_resume_copilot import (
    ResumePreferencePayload,
    ResumeProfilePayload,
)

logger = logging.getLogger(__name__)

# 完成的报告除了留进程内存, 再落一份磁盘缓存(与情报卡 data/_intel_cache 同套路):
# 进程内存重启即丢 → 学生刷新/服务重启后打分结果消失、得重打一遍(烧 LLM+等 40s)。
# 磁盘缓存让 done 报告跨重启存活、单机多请求共享; 仍是可重算派生数据, 不进 DB schema
# (避免与其它会话 WIP migration 抢 alembic head)。
_CACHE_DIR = str(Path(__file__).resolve().parents[3] / "data" / "_score_cache")


def _cache_path(session_id: int) -> str:
    return os.path.join(_CACHE_DIR, f"{int(session_id)}.json")


def _save_cached(session_id: int, report: dict) -> None:
    try:
        os.makedirs(_CACHE_DIR, exist_ok=True)
        with open(_cache_path(session_id), "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False)
    except Exception as exc:  # noqa: BLE001 — 缓存写失败不该影响打分主流程
        logger.warning("score cache write failed for session %s: %s", session_id, exc)


def _load_cached(session_id: int) -> dict | None:
    try:
        with open(_cache_path(session_id), encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return None
    except Exception as exc:  # noqa: BLE001
        logger.warning("score cache read failed for session %s: %s", session_id, exc)
        return None

# 后台路径放宽 LLM 超时: 同步时代 90s 超时砍掉了 ~一半本可成功的打分(实测 75-90s);
# 现在没有浏览器连接在等, 多等一会儿换成功率是纯赚。
BACKGROUND_TIMEOUT_FLOOR_SECONDS = 180

# 阶段流转(真实, 不是表演): prepare=取画像/评分细则, llm=单次评审调用在途,
# parse=整理维度与缺口。前端把它映射到思考卡节点。
STAGES = ("prepare", "llm", "parse")


@dataclass
class ScoreTask:
    session_id: int
    status: str = "running"  # running | done | failed
    stage: str = "prepare"
    started_at: float = field(default_factory=time.time)
    finished_at: float | None = None
    report: dict | None = None
    error: str = ""

    def snapshot(self) -> dict:
        elapsed = (self.finished_at or time.time()) - self.started_at
        return {
            "status": self.status,
            "stage": self.stage,
            "elapsed_seconds": round(elapsed, 1),
            "report": self.report,
            "error": self.error,
        }


# session_id → 最近一个任务(running 或已完成)。完成的留着当服务端缓存 ——
# 报告面板 / 编辑页直接复用, 不再各自重打 LLM。
_tasks: dict[int, ScoreTask] = {}
_lock = threading.Lock()


def _done_snapshot_from_report(report: dict) -> dict:
    return {"status": "done", "stage": "done", "elapsed_seconds": None, "report": report, "error": ""}


def get_task_snapshot(session_id: int) -> dict:
    with _lock:
        task = _tasks.get(session_id)
    if task is not None:
        return task.snapshot()
    # 进程内存没有(从没跑过, 或重启清掉了) → 回落磁盘缓存, 让 done 报告跨重启存活,
    # 不再"刷新即 none / 得重打"。缓存也没有才是真 none。
    cached = _load_cached(session_id)
    if cached is not None:
        return _done_snapshot_from_report(cached)
    return {"status": "none", "stage": "", "elapsed_seconds": None, "report": None, "error": ""}


def start_score_task(
    session_id: int,
    profile: ResumeProfilePayload,
    target_track: str,
    preferences: ResumePreferencePayload | None,
    *,
    force: bool = False,
    provider_factory=None,
) -> dict:
    """启动(或复用)这份简历的打分任务。

    - 已有 running 任务 → 直接挂上它(天然去重: 对话技能与报告面板同时要分,
      只打一遍 LLM)。
    - 已有 done 任务且非 force → 复用现成报告。
    - force=True(用户在对话里明确再要一次打分)→ 重开新任务。
    """
    with _lock:
        existing = _tasks.get(session_id)
        if existing is not None:
            if existing.status == "running":
                return existing.snapshot()
            if existing.status == "done" and not force:
                return existing.snapshot()
        # 内存里没有 done 任务但磁盘有缓存(重启后) → 非 force 直接复用, 不再重打 LLM。
        if existing is None and not force:
            cached = _load_cached(session_id)
            if cached is not None:
                task = ScoreTask(
                    session_id=session_id, status="done", stage="done",
                    report=cached, finished_at=time.time(),
                )
                _tasks[session_id] = task
                return task.snapshot()
        task = ScoreTask(session_id=session_id)
        _tasks[session_id] = task

    worker = threading.Thread(
        target=_run,
        args=(task, profile, target_track, preferences, provider_factory),
        name=f"score-task-{session_id}",
        daemon=True,
    )
    worker.start()
    return task.snapshot()


def _build_provider():
    # 局部 import: scoring 模块在测试里会被 monkeypatch, 延迟绑定保持可注入。
    from app.services.resume_copilot import scoring as scoring_mod

    provider = scoring_mod.OpenAICompatibleResumeScorer()
    # 放宽后台超时(只抬不降, env 配得更高时尊重 env)。
    client = getattr(provider, "client", None)
    if client is not None and getattr(client, "timeout_seconds", 0) < BACKGROUND_TIMEOUT_FLOOR_SECONDS:
        client.timeout_seconds = BACKGROUND_TIMEOUT_FLOOR_SECONDS
    return provider


def _run(
    task: ScoreTask,
    profile: ResumeProfilePayload,
    target_track: str,
    preferences: ResumePreferencePayload | None,
    provider_factory,
) -> None:
    from app.services.resume_copilot import scoring as scoring_mod

    db = SessionLocal()  # 并行任务自开 session, 绝不与请求线程共享(CLAUDE.md 铁律)
    try:
        provider = (provider_factory or _build_provider)()

        # score_resume 内部是 prepare(rubric/redact) → 单次 LLM → parse;
        # 用 provider 包装把「LLM 在途」这个真实节点暴露出来。
        class _StagedProvider:
            def __init__(self, inner):
                self._inner = inner

            def score(self, messages_payload):
                task.stage = "llm"
                raw = self._inner.score(messages_payload)
                task.stage = "parse"
                return raw

        report = scoring_mod.score_resume(
            db,
            profile,
            target_track,
            preferences=preferences,
            provider=_StagedProvider(provider),
        )
        task.report = {
            "session_id": task.session_id,
            "target_track": report.target_track,
            "overall_current": report.overall_current,
            "overall_potential_low": report.overall_potential_low,
            "overall_potential_high": report.overall_potential_high,
            "summary": report.summary,
            "dimensions": [d.model_dump() for d in report.dimensions],
            "section_gaps": [g.model_dump() for g in report.section_gaps],
            "used_ai": report.used_ai,
        }
        task.status = "done"
        task.stage = "done"
        _save_cached(task.session_id, task.report)  # 落磁盘 → 跨重启存活, 不必重打
    except Exception as exc:  # noqa: BLE001 — 任务边界, 失败要落成可轮询的诚实状态
        logger.warning("score task failed for session %s: %s", task.session_id, exc)
        task.status = "failed"
        task.error = str(exc)[:200]
    finally:
        task.finished_at = time.time()
        db.close()


def _reset_for_tests() -> None:
    with _lock:
        _tasks.clear()
    # 清磁盘缓存, 保证各测试隔离(否则上个测试给 session 1 写的报告会被下个测试读到)。
    try:
        for fn in os.listdir(_CACHE_DIR):
            if fn.endswith(".json"):
                os.remove(os.path.join(_CACHE_DIR, fn))
    except FileNotFoundError:
        pass
