from fastapi.testclient import TestClient

from app.main import app
from app.services.resume_copilot import translator as T


def test_format_date_en_single():
    assert T.format_date_en("2024-06") == "Jun 2024"


def test_format_date_en_range():
    assert T.format_date_en("2024-06 - 2024-12") == "Jun 2024 – Dec 2024"


def test_format_date_en_passthrough_unknown():
    assert T.format_date_en("2024 寒假") == "2024 寒假"


def test_numbers_in_extracts():
    assert "0.8" in T.numbers_in("single-factor Sharpe > 0.8")
    assert "12" in T.numbers_in("submitted 12 factors")


def test_en_section_label_by_id():
    assert T.en_section_label("intern", "实习经历") == "Work Experience"
    assert T.en_section_label("proj", "项目经历") == "Projects"


def test_en_section_label_unknown_falls_back_to_source():
    assert T.en_section_label("custom", "证书") == "证书"


class _FakeProvider:
    """回固定译文,模拟 LLM 把 zh strings 映射成 en(含一处凭空多出的数字,验数字锁)。"""
    def __init__(self, mapping):
        self.mapping = mapping

    def translate(self, strings):
        return [self.mapping.get(s, s) for s in strings]


def _sample_profile():
    return {
        'name': '韩怀宇',
        'email': 'a@b.com',
        'skillsText': 'Python、回测框架',
        'sections': [
            {'id': 'intern', 'label': '实习经历', 'type': 'timeline', 'items': [
                {'org': '九坤投资', 'date': '2024-06 - 2024-12', 'location': '北京',
                 'desc': '提交12个因子,入库4个'},
            ]},
            {'id': 'honor', 'label': '所获荣誉', 'type': 'tags', 'items': ['ACM金牌']},
        ],
    }


def test_translate_profile_structure_and_labels():
    prof = _sample_profile()
    fake = _FakeProvider({
        '韩怀宇': 'Huaiyu Han', 'Python、回测框架': 'Python, backtesting framework',
        '九坤投资': 'XXX', '提交12个因子,入库4个': 'submitted 12 factors, 4 accepted', 'ACM金牌': 'ACM Gold',
    })
    out = T.translate_profile(prof, provider=fake)
    p = out['profile']
    # 结构对齐
    assert [s['id'] for s in p['sections']] == ['intern', 'honor']
    # 固定英文标题
    assert p['sections'][0]['label'] == 'Work Experience'
    assert p['sections'][1]['label'] == 'Honors & Awards'
    # 机构名表覆盖 LLM(九坤投资 → Ubiquant,不用 fake 的 'XXX')
    assert p['sections'][0]['items'][0]['org'] == 'Ubiquant'
    # 日期格式化
    assert p['sections'][0]['items'][0]['date'] == 'Jun 2024 – Dec 2024'
    # email 原样
    assert p['email'] == 'a@b.com'


def test_translate_profile_number_lock_flags_fabrication():
    prof = _sample_profile()
    fake = _FakeProvider({'提交12个因子,入库4个': 'submitted 12 factors, 99 accepted'})  # 99 凭空
    out = T.translate_profile(prof, provider=fake)
    warns = out['warnings']
    assert any('99' in w.get('extra', '') for w in warns)


def test_translate_profile_rejects_short_provider_output():
    import pytest
    prof = _sample_profile()
    class _ShortProvider:
        def translate(self, strings):
            return strings[:-1]  # drops one
    with pytest.raises(ValueError):
        T.translate_profile(prof, provider=_ShortProvider())


def test_translate_endpoint_roundtrip(monkeypatch):
    # 用 fake provider,避免联网
    fake = _FakeProvider({'韩怀宇': 'Huaiyu Han'})
    monkeypatch.setattr(T, 'OpenAICompatibleTranslator', lambda *a, **k: fake)
    client = TestClient(app)
    body = {'profile': _sample_profile(), 'target': 'en'}
    r = client.post('/api/resume-copilot/translate-profile', json=body)
    assert r.status_code == 200
    data = r.json()
    assert data['profile']['sections'][0]['label'] == 'Work Experience'
    assert 'warnings' in data
