import inspect

import app.services.resume_copilot.workflow as wf


def test_v2_on_branch_guards_react_agent():
    """v2 开启路径不得实例化 ReActAgent —— ReActAgent( 必须在 RECOMMENDATION_V2_ENABLED
    判断之后(else 分支)。完整端到端质量/耗时由 Task 6 的 A/B eval 把关。"""
    src = inspect.getsource(wf.run_resume_generate_workflow)
    assert "RECOMMENDATION_V2_ENABLED" in src, "workflow 应按 v2 开关分支"
    assert "ReActAgent(" in src, "v2 OFF 分支仍应保留 ReAct"
    assert src.index("ReActAgent(") > src.index("RECOMMENDATION_V2_ENABLED"), \
        "ReActAgent 应在 v2 开关判断之后(else 分支)"


def test_recommend_progress_constructed():
    """workflow 应构造 RecommendProgress 并把进度回调接进推荐调用。"""
    src = inspect.getsource(wf.run_resume_generate_workflow)
    assert "RecommendProgress(" in src
    assert "progress=progress" in src
