import os, pytest
pytestmark = pytest.mark.skipif(not os.environ.get("RUN_LLM_TESTS"), reason="需 RUN_LLM_TESTS=1 + LLM key")

from app.services.phase_g.sub_cat_enricher import pass1_classify_strategy

CASES = [
    ({"company": "字节跳动", "job_title": "AI产品经理-大模型方向", "job_duty": "负责大模型应用产品设计、需求分析、PRD", "job_req": ""}, "AI 应用_PM_开发"),
    ({"company": "字节跳动", "job_title": "后端开发实习生-抖音", "job_duty": "Java 后端服务开发、接口设计", "job_req": ""}, "互联网"),
    ({"company": "美团", "job_title": "产品运营实习生", "job_duty": "用户增长、活动运营、数据复盘", "job_req": ""}, "互联网"),
    ({"company": "快手", "job_title": "推荐算法实习生", "job_duty": "推荐召回排序模型、特征工程", "job_req": ""}, "AI 应用_PM_开发"),
    ({"company": "京东", "job_title": "京东管培生-战略方向", "job_duty": "轮岗培养、战略分析、项目管理", "job_req": ""}, "互联网"),
    ({"company": "美团", "job_title": "骑手运营", "job_duty": "配送调度、骑手管理", "job_req": ""}, None),
    ({"company": "字节跳动", "job_title": "招聘HR实习生", "job_duty": "简历筛选、面试安排", "job_req": ""}, None),
    ({"company": "淘天集团", "job_title": "电商商家运营", "job_duty": "商家招商、活动策划、商业化", "job_req": ""}, "互联网"),
]

@pytest.mark.parametrize("job,expected", CASES)
def test_pass1_routes(job, expected):
    out = pass1_classify_strategy(job)
    assert out["strategy_type"] == expected, f"{job['job_title']} → {out['strategy_type']} (期望 {expected})"
