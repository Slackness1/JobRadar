"""慢路: 对一批 job 跑 Pro 精排 + 理由。复用 recommendation_v2 慢路, 失败回落原 item。

这是 NL 推荐子项里**唯一**允许跑 Pro(rerank_top_n / generate_narrative)的地方。
快路(recommend-chat / working-query / update)绝不调 Pro。
"""
from __future__ import annotations

import json
import logging
from typing import Any

logger = logging.getLogger(__name__)

_ANCHOR_LABELS = ["赛道契合", "平台梯队", "岗位画像", "不确定点"]


def _resolve_query(db, session):
    """解析本会话的工作查询, 与 feed 的产出源保持一致。

    关键: feed 可能由 reseed 铺出 (按画像 seed_query), 而 reseed 对 demo 只读会话
    **不回写** working_query_json。若深挖只读 working_query_json, demo 会话拿到空查询 →
    search_candidates 召回的是另一批岗 → 目标 job_id 永远不在里面 → 深挖恒空。
    故 working_query 为空时回落到与 reseed 同源的 seed_query_for_session, 让候选集对齐。
    """
    from app.services.resume_copilot.working_query import WorkingQuery

    raw = getattr(session, "working_query_json", None)
    if raw:
        try:
            return WorkingQuery(**json.loads(raw))
        except Exception:  # noqa: BLE001
            pass
    try:
        from app.services.resume_copilot.recommend_chat import seed_query_for_session

        return seed_query_for_session(db, session)
    except Exception:  # noqa: BLE001
        return WorkingQuery()


def _persisted_run_items(db, session) -> list:
    """读已落库的推荐 run.recommendations_json, 转成 ResumeRecommendationItem(与
    feed 同型)。深挖兜底用 —— 没有 run / 解析失败都安静返空, 绝不抛。"""
    try:
        from app.models import ResumeRecommendationRun
        from app.schemas_resume_copilot import ResumeRecommendationItem

        sid = getattr(session, "id", None)
        if sid is None:
            return []
        run = (
            db.query(ResumeRecommendationRun)
            .filter(ResumeRecommendationRun.session_id == sid)
            .first()
        )
        if run is None:
            return []
        raw = getattr(run, "recommendations_json", "[]") or "[]"
        return [ResumeRecommendationItem.model_validate(d) for d in json.loads(raw)]
    except Exception:  # noqa: BLE001
        logger.warning("deepen: load persisted run items failed", exc_info=True)
        return []


def deepen_jobs(db, session, job_ids: list[str]) -> list[dict]:
    """对 job_ids 跑 Pro 精排 + 4-anchor 理由。永不抛出, 失败回落规则 item。"""
    if not job_ids:
        return []
    from app.services.resume_copilot.recommend_search import search_candidates

    q = _resolve_query(db, session)
    try:
        feed = search_candidates(db, q, limit=60)
    except Exception:  # noqa: BLE001
        logger.warning("deepen: search_candidates failed", exc_info=True)
        feed = []

    def jid(it: Any) -> Any:
        return it.get("job_id") if isinstance(it, dict) else getattr(it, "job_id", None)

    wanted = {str(x) for x in job_ids}
    targets = [it for it in feed if str(jid(it)) in wanted]
    # 兜底: 学生要深挖的岗若不在重搜的 feed 里(被多样性限流踢掉 / 查询已漂移),
    # 回落到已落库的推荐 run —— 凡是"曾经展示过的岗"都该能深挖, 不能恒空
    # (轮次9: 只对话的新用户深挖恒返空)。
    if len(targets) < len(wanted):
        found = {str(jid(it)) for it in targets}
        for it in _persisted_run_items(db, session):
            j = str(jid(it))
            if j in wanted and j not in found:
                targets.append(it)
                found.add(j)
    if not targets:
        return []
    try:
        deepened = _deepen_targets(db, session, targets)
    except Exception:  # noqa: BLE001
        logger.warning("deepen slow-path unavailable, returning rule items", exc_info=True)
        deepened = [(it, None) for it in targets]
    return [_shape_deepen_item(it, nar) for it, nar in deepened]


def _deepen_targets(db, session, targets: list) -> list[tuple[Any, dict | None]]:
    """对 targets 跑真正的 v2 慢路 (Pro rerank + narrative), 返回 [(item, narrative_dict)]。

    复用 recommendation_v2 的 rerank_top_n / generate_narrative —— 与
    recommendation.py::_recommend_v2_dispatcher 同样的调用约定。
    targets 是 search_candidates 吐的 ResumeRecommendationItem; 用 job_id join 回
    真正的 Job ORM 行喂给 Pro。
    """
    from app.models import Job
    from app.services.phase_g.recommendation_v2.narrative import generate_narrative
    from app.services.phase_g.recommendation_v2.rerank import rerank_top_n

    def jid(it: Any) -> Any:
        return it.get("job_id") if isinstance(it, dict) else getattr(it, "job_id", None)

    job_id_list = [str(jid(it)) for it in targets]
    jobs = db.query(Job).filter(Job.job_id.in_(job_id_list)).all()
    job_by_id = {str(j.job_id): j for j in jobs}

    # student_profile 必须喂**真实简历经历** —— 否则叙事 LLM 没料可用就会照抄 prompt 例子
    # (实测给互联网产品学生编出"200亿消费股深度报告"投研资历, 违"不编造"铁律)。
    wq = _resolve_query(db, session)
    student_profile = _student_profile_for_deepen(db, session, wq.effective_sub_cats())

    # rerank: 喂 [(job, base_score 0-1)] —— base 用规则的 final_score 归一到 0-1。
    ranked_with_score: list[tuple[Any, float]] = []
    for it in targets:
        j = job_by_id.get(str(jid(it)))
        if j is None:
            continue
        rule_final = it.get("final_score") if isinstance(it, dict) else getattr(it, "final_score", 0)
        ranked_with_score.append((j, float(rule_final or 0) / 100.0))

    rerank_by_job: dict[str, dict[str, Any]] = {}
    if ranked_with_score:
        reranked = rerank_top_n(student_profile, ranked_with_score, n=len(ranked_with_score))
        for r in reranked:
            rerank_by_job[str(r["job"].job_id)] = r

    out: list[tuple[Any, dict | None]] = []
    for it in targets:
        jstr = str(jid(it))
        j = job_by_id.get(jstr)
        r = rerank_by_job.get(jstr)
        narrative: dict | None = None
        if j is not None:
            try:
                narrative = generate_narrative(student_profile, j, llm_rerank=r)
            except Exception:  # noqa: BLE001
                logger.warning("deepen: generate_narrative failed for %s", jstr, exc_info=True)
                narrative = None
        # 把 rerank 的 final_score (0-1) 拍回 0-100 给 enhanced_score 用
        if r is not None:
            it = _attach_enhanced(it, r.get("final_score"))
        out.append((it, narrative))
    return out


def _student_profile_for_deepen(db, session, preferred_sub_cats: list) -> dict[str, Any]:
    """从会话真实简历画像装 student_profile(背景 + 真实经历亮点), 供叙事 grounding。

    hidden_highlights 只放**简历里真实出现的**经历(实习/项目 bullet + 奖项), 空就空 ——
    叙事 prompt 已要求"没有对口经历就明说, 绝不编造"(配合本函数防止 LLM 凭空安资历)。
    """
    name = ""
    background = ""
    highlights: list[str] = []
    try:
        from app.routers.resume_copilot import _load_profile_and_prefs
        profile, _prefs = _load_profile_and_prefs(db, getattr(session, "id", None))
        if profile is not None:
            bi = getattr(profile, "basic_info", None)
            name = str(getattr(bi, "name", "") or "") if bi is not None else ""
            background = str(getattr(profile, "candidate_summary", "") or "")
            for it in (getattr(profile, "internships", None) or [])[:4]:
                comp = str(getattr(it, "company", "") or "").strip()
                role = str(getattr(it, "role", "") or "").strip()
                for b in (getattr(it, "bullets", None) or [])[:2]:
                    b = str(b or "").strip()
                    if b:
                        highlights.append(f"{comp}·{role}: {b}" if (comp or role) else b)
            for pj in (getattr(profile, "projects", None) or [])[:3]:
                pn = str(getattr(pj, "name", "") or "").strip()
                for b in (getattr(pj, "bullets", None) or [])[:2]:
                    b = str(b or "").strip()
                    if b:
                        highlights.append(f"项目「{pn}」: {b}" if pn else b)
            for aw in (getattr(profile, "awards", None) or [])[:3]:
                aw = str(aw or "").strip()
                if aw:
                    highlights.append(aw)
    except Exception:  # noqa: BLE001
        logger.warning("deepen: load profile for highlights failed", exc_info=True)
    return {
        "name": name,
        "background": background[:600],
        "hidden_highlights": highlights[:8],
        "preferred_sub_cats": preferred_sub_cats,
    }


def _attach_enhanced(it: Any, final_score_0_1) -> Any:
    """把 Pro rerank 的 final_score(0-1) 折成 0-100 暂存在 item 上, 供 shaping 取。"""
    try:
        enhanced = int(round(float(final_score_0_1) * 100)) if final_score_0_1 is not None else None
    except Exception:  # noqa: BLE001
        enhanced = None
    if enhanced is None:
        return it
    if isinstance(it, dict):
        it = dict(it)
        it["_enhanced_pro"] = enhanced
        return it
    d = it.model_dump() if hasattr(it, "model_dump") else dict(getattr(it, "__dict__", {}))
    d["_enhanced_pro"] = enhanced
    return d


def _shape_deepen_item(it: Any, narrative: dict | None) -> dict:
    """确保每条带 enhanced_score + anchors(<=4 段 [label,text]) + used_ai=True。

    item 既可能是 ResumeRecommendationItem (pydantic), 也可能已被 _attach_enhanced
    转成 dict。统一转 dict 后挂字段 —— item 模型无 anchors 字段, 必须走 dict 出参。
    """
    if isinstance(it, dict):
        d = dict(it)
    elif hasattr(it, "model_dump"):
        d = it.model_dump()
    else:
        d = dict(getattr(it, "__dict__", {}))

    enhanced = d.pop("_enhanced_pro", None)
    if enhanced is None:
        enhanced = d.get("enhanced_score") or d.get("final_score") or 0
    d["enhanced_score"] = int(enhanced or 0)
    d["anchors"] = _narrative_to_anchors(narrative)
    d["used_ai"] = True
    return d


def _narrative_to_anchors(nar) -> list[list[str]]:
    """把 generate_narrative 的输出折成 <=4 段 [label, text], 每段内容互不相同。

    新 schema: nar={anchor_points: [{key, text}], narrative, anchors_used}。
    anchor_points 里每条 text 已经是**彼此不同**的一句话, 直接映中文标签即可 ——
    这是修「三条一样」的核心: 不再把同一段 narrative 复制到多个锚点。
    旧 schema(只有 narrative 整段文本)兜底成单段, 也绝不复制。
    """
    if nar is None:
        return []
    if isinstance(nar, dict):
        idx_map = {"A": 0, "B": 1, "C": 2, "D": 3}
        points = nar.get("anchor_points")
        if isinstance(points, list) and points:
            out: list[list[str]] = []
            seen: set[str] = set()
            for p in points:
                if not isinstance(p, dict):
                    continue
                key = str(p.get("key") or "").strip().upper()
                text = str(p.get("text") or "").strip()
                if key not in idx_map or not text:
                    continue
                norm = text.replace(" ", "")
                if norm in seen:  # 二次去重, 杜绝重复段
                    continue
                seen.add(norm)
                out.append([_ANCHOR_LABELS[idx_map[key]], text])
            if out:
                return out[:4]
        # 兜底: 没有结构化锚点 → 单段, 不复制
        text = str(nar.get("narrative") or "").strip()
        return [[_ANCHOR_LABELS[0], text]] if text else []
    # 防御: 其它形态 (list / str)
    if isinstance(nar, list):
        out: list[list[str]] = []
        for i, v in enumerate(nar[:4]):
            if isinstance(v, (list, tuple)) and len(v) == 2:
                out.append([str(v[0]), str(v[1])])
            else:
                out.append([_ANCHOR_LABELS[i] if i < 4 else "理由", str(v)])
        return out
    return [["理由", str(nar)]] if nar else []
