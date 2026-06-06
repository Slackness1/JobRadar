"""先验硬规则路由单测。返回 (is_hard, matched_pattern_name)。"""
from __future__ import annotations

from app.services.phase_g.quality_cascade.hard_patterns import is_hard_pattern


def test_retail_sales_title_is_hard():
    hard, name = is_hard_pattern(company="某银行", title="理财经理", duty="", req="")
    assert hard is True
    assert name == "retail_or_channel_sales"


def test_generic_sales_without_institutional_signal_is_hard():
    hard, _ = is_hard_pattern(company="某券商", title="客户经理", duty="维护客户", req="")
    assert hard is True


def test_institutional_sales_signal_not_hard():
    # JD 含机构信号(机构客户/路演) → flash 配 KB 足够, 不必升级
    hard, _ = is_hard_pattern(
        company="中金公司", title="销售交易", duty="服务机构客户, 组织路演", req=""
    )
    assert hard is False


def test_middle_back_office_is_hard():
    hard, name = is_hard_pattern(company="某公募", title="投资监督岗", duty="", req="")
    assert hard is True
    assert name == "middle_back_office"


def test_foreign_english_title_is_hard():
    hard, name = is_hard_pattern(company="Optiver", title="Quant Researcher", duty="", req="")
    assert hard is True
    assert name == "foreign_english_role"


def test_plain_research_role_not_hard():
    hard, name = is_hard_pattern(company="易方达基金", title="权益研究员", duty="行业研究", req="")
    assert hard is False
    assert name is None
