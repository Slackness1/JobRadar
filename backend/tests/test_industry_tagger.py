"""Phase 6 mvp — industry_tagger unit tests。"""
from app.services.resume_copilot.industry_tagger import tag_industries


def test_tmt_半导体():
    assert 'TMT' in tag_industries('研究员（半导体）')


def test_tmt_硬科技():
    assert 'TMT' in tag_industries('项目实习生-投资分析（硬科技方向）')


def test_制造_军工():
    assert '制造' in tag_industries('研究员（军工）')


def test_消费():
    assert '消费' in tag_industries('食品饮料行业研究员')


def test_医药():
    assert '医药' in tag_industries('项目实习生-投资分析（生物医药方向）')


def test_固收():
    tags = tag_industries('固收策略研究员')
    assert '固收' in tags


def test_FOF():
    assert 'FOF' in tag_industries('FOF基金经理')


def test_FOF_2():
    assert 'FOF' in tag_industries('多资产研究员')


def test_宏观策略_国内():
    assert '宏观策略' in tag_industries('研究员（国内宏观）')


def test_宏观策略_海外():
    assert '宏观策略' in tag_industries('研究员（海外宏观）')


def test_量化中频():
    assert '量化中频' in tag_industries('定量研究员（金工方向）')


def test_IBD_股权():
    assert 'IBD-股权' in tag_industries('IPO 投资经理')


def test_IBD_并购():
    assert 'IBD-并购' in tag_industries('并购财务顾问助理')


def test_max_2_tags():
    """硬科技 + 半导体都命中 TMT,只返一个;再有别的行业才出第 2 个。"""
    tags = tag_industries('生物医药 + TMT 行研双方向')
    assert len(tags) <= 2


def test_empty_returns_empty():
    assert tag_industries('') == []
    assert tag_industries('', '') == []


def test_no_industry_match_returns_empty():
    """普通 ops 岗位 (前面 5a 已经被拦截),无 industry 关键词 → 空 list。"""
    assert tag_industries('行政专员') == []


def test_新能源_独立行业():
    """新能源不能被「制造」抢走 — 顺序保证 新能源 优先。"""
    assert '新能源' in tag_industries('新能源车研究员')


def test_销售交易():
    assert '销售交易' in tag_industries('机构销售助理')
