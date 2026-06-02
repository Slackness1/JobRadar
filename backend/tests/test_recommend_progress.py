from app.services.phase_g.recommendation_v2.progress import RecommendProgress


def test_default_callbacks_are_noop():
    p = RecommendProgress()
    # 默认回调必须可调用且不抛
    p.on_recall(10)
    p.on_ranked([])
    p.on_rerank_one(1, 10, "reason")
    p.on_narrative_one(2, 6)
