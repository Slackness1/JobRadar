from app.services.intel.source_score import compute_source_score, platform_of

def test_platform_of_by_prefix():
    assert platform_of("zh_abc") == "zhihu"
    assert platform_of("xhs_abc") == "xhs"
    assert platform_of("xhsp_1") == "xhs"
    assert platform_of("bili_BV1") == "bilibili"
    assert platform_of("pod_x") == "podcast"

def test_high_engagement_zhihu_with_author_scores_mid_high():
    s = compute_source_score("zh_x", liked=200, comment=33, signal_score=200, author_name="王某")
    assert 0.45 <= s <= 0.85  # 知乎 ceiling 0.85，高赞有作者

def test_marketing_gate_tanks_score():
    s = compute_source_score("xhs_x", liked=500, comment=50, signal_score=500,
                             author_name="某机构", marketing_text="扫码进群领取资料")
    assert s <= 0.20

def test_empty_signals_floor():
    s = compute_source_score("xhsp_1", liked=0, comment=0, signal_score=0, author_name="")
    assert 0.0 <= s <= 0.15
