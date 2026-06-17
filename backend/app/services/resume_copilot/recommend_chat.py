"""Unit C: NL 推荐 agent 一轮 orchestrator。

parse_intent → apply_delta → 持久化 working_query → search_candidates → 返回。
remember 非空 → L3 写统一记忆(经 dispatcher.write_memory, 唯一写入路径)。
chitchat/intel 不重排 feed(feed=None)。
"""
from __future__ import annotations

import json
import logging
from datetime import datetime

from app.services.resume_copilot.working_query import WorkingQuery, apply_delta
from app.services.resume_copilot.recommend_intent import parse_intent
from app.services.resume_copilot.recommend_search import search_candidates

logger = logging.getLogger(__name__)

# 触发重排(检索)的 intent —— 起跑推荐 / 改动工作查询都重跑召回。
# recommend = 学生直接要一批推荐(首轮/换一批),即使没新增筛选也要从种子查询召回出 feed,
# 否则会掉进 chitchat 空屏(修 P0-1:NL 起不了推荐)。
_RERANK_INTENTS = ("recommend", "refine", "company_focus")


def _load_query(db, session) -> WorkingQuery:
    raw = getattr(session, "working_query_json", None)
    if raw:
        try:
            return WorkingQuery(**json.loads(raw))
        except Exception:
            logger.warning("recommend_chat: bad working_query_json, re-seeding", exc_info=True)
    return seed_query_for_session(db, session)


def seed_query_for_session(db, session) -> WorkingQuery:
    from app.services.resume_copilot.working_query import seed_working_query
    confirmed: list[str] = []
    rows: list[dict] = []
    try:
        from app.services.resume_copilot.recommendation import _v2_extract_preferred_sub_cats
        from app.routers.resume_copilot import _load_profile_and_prefs
        profile, prefs = _load_profile_and_prefs(db, getattr(session, "id", None))
        confirmed = _v2_extract_preferred_sub_cats(profile, prefs) or []
    except Exception:
        logger.warning("recommend_chat seed: load confirmed sub_cats failed", exc_info=True)
    try:
        rows = _active_preference_rows(db, getattr(session, "user_key", None))
    except Exception:
        logger.warning("recommend_chat seed: load preference rows failed", exc_info=True)
    # P0-3 兜底:没确认过子赛道时(简历传了但没走完确认页 / 老会话 / 克隆账号),
    # 从简历正文推断 1-3 个种子, 否则种子空 → 召回 0 → 学生首次就空屏。
    if not confirmed:
        confirmed = _infer_seed_sub_cats(db, session)
    return seed_working_query(confirmed_sub_cats=confirmed, preference_rows=rows)


def _infer_seed_sub_cats(db, session) -> list[str]:
    """简历 → 1-3 个最匹配子赛道(复用确认页同款 LLM 预勾器)。

    仅在 confirmed 为空时调用; 失败 / 无简历 → 返 [](不硬塞全集当种子, 免召回全库噪声)。
    """
    summary = (
        getattr(session, "extracted_text", None)
        or getattr(session, "resume_text", None)
        or ""
    ).strip()
    if not summary:
        return []
    try:
        from app.services.phase_g.knowledge_synthesis import SUBCAT_TO_STRATEGY
        from app.services.resume_copilot.subcat_suggest import suggest_sub_cats
    except Exception:
        logger.warning("recommend_chat seed: infer imports failed", exc_info=True)
        return []
    cands = [c for c in SUBCAT_TO_STRATEGY.keys() if c]
    if not cands:
        return []
    try:
        picked = suggest_sub_cats(summary, cands)
    except Exception:
        logger.warning("recommend_chat seed: suggest_sub_cats failed", exc_info=True)
        return []
    # suggest 失败会回落"全部候选"; 那种情况(几十个)别当种子, 取空。正常 ≤3 个直接用。
    if picked and len(picked) <= 5:
        logger.info("recommend_chat seed: inferred %s from resume (no confirmed)", picked)
        return picked
    return []


def _active_preference_rows(db, user_key) -> list[dict]:
    """读 user 的活跃 preference 行(给 working_query seed 用)。直读列名见 models.AccountMemory。"""
    if not user_key or db is None:
        return []
    from sqlalchemy import text
    out: list[dict] = []
    sql = (
        "SELECT payload_json FROM account_memory "
        "WHERE user_key=:u AND category='preference' AND COALESCE(is_archived,0)=0"
    )
    for (pj,) in db.execute(text(sql), {"u": user_key}).fetchall():
        try:
            p = json.loads(pj) if pj else {}
            if p.get("dimension") and p.get("value"):
                out.append({"dimension": p["dimension"], "value": p["value"]})
        except Exception:
            continue
    return out


def _write_preference_memory(*, db, user_key, dimension, value, session_id):
    """L3: 经唯一写入路径落 account_memory preference 行。绝不直插。

    write_memory(db, *, user_key, category, summary, payload, source_module,
                 source_session_id=...) — 见 app/services/memory/dispatcher.py。
    payload 接受 dict 或 pydantic model; PreferencePayload(dimension, value),
    dimension 受 Literal[city|industry|role|comp|company_type|stage] 约束。
    """
    from app.services.memory.dispatcher import write_memory
    from app.services.memory.schemas import PreferencePayload
    return write_memory(
        db,
        user_key=user_key,
        category="preference",
        summary=f"偏好·{dimension}:{value}"[:80],
        payload=PreferencePayload(dimension=dimension, value=value),
        source_module="recommend_chat",
        source_session_id=session_id,
    )


def run_recommend_turn(*, db, session, message: str, client=None) -> dict:
    """跑一轮 NL 推荐对话。返回 shape 前端依赖, 不要改:
    intent / reply / feed / working_query / trace / remembered。
    """
    q = _load_query(db, session)
    parsed = parse_intent(message, current_query=q.model_dump(), client=client)
    intent = parsed["intent"]

    feed = None
    if intent in _RERANK_INTENTS:
        q = apply_delta(q, parsed.get("query_delta") or {})
        try:
            session.working_query_json = json.dumps(q.model_dump(), ensure_ascii=False)
        except Exception:
            logger.warning("recommend_chat: persist working_query failed", exc_info=True)
        feed = search_candidates(db, q)
        # 把对话推出来的 feed 落库到 ResumeRecommendationRun —— 否则只聊天、从没点
        # "生成"的新用户(轮次9 的 B/C persona)GET /recommendations 恒 404、深挖恒空、
        # 方向分析永远没数据。落库后这条链就活了。详见 _persist_feed_to_run。
        _persist_feed_to_run(db, session, feed)

    rem = parsed.get("remember")
    remembered = None
    if rem and rem.get("dimension") and rem.get("value") and getattr(session, "user_key", None):
        try:
            _write_preference_memory(
                db=db,
                user_key=session.user_key,
                dimension=rem["dimension"],
                value=rem["value"],
                session_id=getattr(session, "id", None),
            )
            remembered = {"dimension": rem["dimension"], "value": rem["value"]}
        except Exception:
            logger.warning("recommend_chat: L3 preference write failed", exc_info=True)

    trace = {
        "intent": intent,
        "query_delta": parsed.get("query_delta") or {},
        "remember_note": _remember_note(rem, remembered),
    }
    return {
        "intent": intent,
        "reply": parsed.get("reply"),
        "feed": feed,
        "working_query": q.model_dump(),
        "trace": trace,
        "remembered": remembered,
    }


def _persist_feed_to_run(db, session, feed) -> None:
    """把 chat feed 落到 ResumeRecommendationRun.recommendations_json。

    守一条不回归的铁律: **绝不覆盖 generate 跑出的 AI 精排结果**(used_ai=1 +
    completed)—— 那批带 4-anchor 叙事, Hub 推荐面板靠它。只在"无 run / run 不是
    AI 完成态"时写, 正好覆盖真正的受害者(只对话、从没 generate 过的新用户)。
    feed 形状即 ResumeRecommendationItem, model_dump 后可被 GET 端点原样 re-validate。
    """
    if not feed or db is None:
        return
    from app.models import ResumeRecommendationRun
    from app.services.resume_copilot.state import RunStatus

    sid = getattr(session, "id", None)
    if sid is None:
        return
    run = (
        db.query(ResumeRecommendationRun)
        .filter(ResumeRecommendationRun.session_id == sid)
        .first()
    )
    if run is not None and int(getattr(run, "used_ai", 0) or 0) == 1 \
            and str(getattr(run, "status", "")) == RunStatus.COMPLETED.value:
        return  # 保护 generate 的 AI 精排结果, 不被规则版 feed 覆盖
    try:
        payload = json.dumps(
            [it if isinstance(it, dict) else it.model_dump() for it in feed],
            ensure_ascii=False,
        )
    except Exception:
        logger.warning("recommend_chat: serialize feed for run failed", exc_info=True)
        return
    if run is None:
        run = ResumeRecommendationRun(session_id=sid)
        db.add(run)
    run.status = RunStatus.COMPLETED.value
    run.used_ai = 0
    run.error_message = ""
    run.fallback_reason = ""
    run.recommendations_json = payload
    run.updated_at = datetime.utcnow()
    try:
        session.recommendation_status = RunStatus.COMPLETED.value
    except Exception:
        pass


def _remember_note(rem, remembered) -> str:
    if remembered:
        return f"{remembered['dimension']}={remembered['value']} · 稳定偏好, 已升 L3"
    if rem:
        return "识别到偏好但未写库(缺登录/写失败)"
    return "一次性调整, 不升 L3"
