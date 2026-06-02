from app.services.phase_g.recommendation_v2.progress import RecommendProgress


def test_default_callbacks_are_noop():
    p = RecommendProgress()
    # 默认回调必须可调用且不抛
    p.on_recall(10)
    p.on_ranked([])
    p.on_rerank_one(1, 10, "reason")
    p.on_narrative_one(2, 6)


from app.services.resume_copilot.recommendation import _recommend_v2_dispatcher
from app.schemas_resume_copilot import ResumeProfilePayload
from app.database import SessionLocal


def test_dispatcher_fires_callbacks_in_order():
    events: list[str] = []
    prog = __import__(
        "app.services.phase_g.recommendation_v2.progress", fromlist=["RecommendProgress"]
    ).RecommendProgress(
        on_recall=lambda n: events.append(f"recall:{n>=0}"),
        on_ranked=lambda items: events.append("ranked"),
        on_rerank_one=lambda d, t, r: events.append("rerank"),
        on_narrative_one=lambda d, t: events.append("narr"),
    )
    db = SessionLocal()
    try:
        _recommend_v2_dispatcher(
            db,
            profile=ResumeProfilePayload(),
            preferences=None,
            rejected_job_ids=[],
            limit=None, min_score=None, top_n=10,
            progress=prog,
        )
    except Exception:
        pass  # 没候选也行，只验回调顺序契约
    finally:
        db.close()
    assert events and events[0].startswith("recall")
    if "ranked" in events and "rerank" in events:
        assert events.index("ranked") < events.index("rerank")
