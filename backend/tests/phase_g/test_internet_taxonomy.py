from app.services.phase_g.knowledge_synthesis import SUBCAT_TO_STRATEGY
from app.services.phase_g.sub_cat_enricher import STRATEGY_TYPES

INTERNET_SUBCATS = [
    "产品经理", "产品运营", "互联网软件研发", "数据分析与商业分析",
    "芯片硬件与汽车工程", "数据平台与基础设施研发", "综合管培与战略项目",
    "电商与商业化运营", "内容与社区运营", "体验设计与用户研究",
    "销售客户成功与解决方案", "游戏策划与发行运营",
]

def test_internet_strategy_registered():
    assert "互联网" in STRATEGY_TYPES

def test_internet_subcats_mapped():
    for sc in INTERNET_SUBCATS:
        assert SUBCAT_TO_STRATEGY.get(sc) == "互联网", f"{sc} 未映射到 互联网"

def test_new_ai_subcat_mapped():
    assert SUBCAT_TO_STRATEGY.get("搜索推荐广告算法") == "AI 应用_PM_开发"
    # spec §2.1 的已有 6 桶须齐全(本 base 缺 AI应用开发工程师,须补)
    assert SUBCAT_TO_STRATEGY.get("AI应用开发工程师") == "AI 应用_PM_开发"


def test_internet_kb_rows_seeded():
    import sqlite3
    c = sqlite3.connect("data/jobradar.db").cursor()
    got = {r[0] for r in c.execute(
        "SELECT sub_cat FROM knowledge_subcategories WHERE strategy_type IN ('互联网','AI 应用_PM_开发')").fetchall()}
    for sc in INTERNET_SUBCATS + ["搜索推荐广告算法", "AI应用开发工程师"]:
        assert sc in got, f"{sc} 未入 knowledge_subcategories"
