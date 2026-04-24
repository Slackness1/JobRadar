import importlib

import pytest

from app import config
from app.services.resume_copilot import ResumeUploadError
from app.services.resume_copilot.ingest import extract_resume_text_from_pdf, validate_pdf_upload
from app.services.resume_copilot.llm import OpenAICompatibleLLMClient, build_resume_llm_client
from app.services.resume_copilot.parser import (
    build_heuristic_resume_profile,
    build_resume_parser_provider,
    parse_resume_text_to_profile,
)


class _FakePage:
    def __init__(self, text: str) -> None:
        self._text = text

    def extract_text(self) -> str:
        return self._text


class _FakePdfReader:
    def __init__(self, _stream) -> None:
        self.pages = [_FakePage('Jane Doe'), _FakePage('Python\nSQL')]


class _FakeResumeParserProvider:
    def __init__(self, payload):
        self.payload = payload

    def parse_resume_text(self, _resume_text: str):
        return self.payload


def test_validate_pdf_upload_rejects_non_pdf_extension():
    with pytest.raises(ResumeUploadError) as exc:
        validate_pdf_upload('resume.docx', 'application/pdf')

    assert exc.value.code == 'INVALID_FILE_TYPE'


def test_validate_pdf_upload_tolerates_missing_content_type_for_pdf_name():
    validate_pdf_upload('resume.pdf', '')


def test_extract_resume_text_from_pdf_reads_all_pages(monkeypatch):
    monkeypatch.setattr('app.services.resume_copilot.ingest.PdfReader', _FakePdfReader)

    text = extract_resume_text_from_pdf(b'%PDF-test%')

    assert text == 'Jane Doe\n\nPython\nSQL'


def test_extract_resume_text_from_pdf_raises_assertable_error_for_empty_text(monkeypatch):
    class _EmptyPdfReader:
        def __init__(self, _stream) -> None:
            self.pages = [_FakePage(''), _FakePage('   ')]

    monkeypatch.setattr('app.services.resume_copilot.ingest.PdfReader', _EmptyPdfReader)

    with pytest.raises(ResumeUploadError, match='did not contain readable text'):
        extract_resume_text_from_pdf(b'%PDF-test%')


def test_parse_resume_text_to_profile_returns_typed_payload_from_provider_json():
    profile = parse_resume_text_to_profile(
        'Jane Doe\nEducation\nProjects',
        provider=_FakeResumeParserProvider(
            {
                'basic_info': {'name': 'Jane Doe', 'email': 'jane@example.com'},
                'education': [
                    {
                        'school': 'Test University',
                        'degree': 'BS',
                        'major': 'Computer Science',
                    }
                ],
                'projects': [
                    {
                        'name': 'JobRadar',
                        'role': 'Builder',
                        'tech_stack': ['Python', 'React'],
                        'bullets': ['Built features'],
                    }
                ],
                'skills': {
                    'technical': ['Python'],
                    'tools': ['Git'],
                    'languages': ['English'],
                },
                'candidate_summary': 'Strong builder',
                'inferred_roles': ['Backend Engineer'],
                'inferred_tracks': ['Internet'],
            }
        ),
    )

    assert profile.basic_info['name'] == 'Jane Doe'
    assert profile.education[0].school == 'Test University'
    assert profile.projects[0].tech_stack == ['Python', 'React']
    assert profile.skills.technical == ['Python']
    assert profile.inferred_roles == ['Backend Engineer']


def test_parse_resume_text_to_profile_falls_back_when_provider_json_shape_is_invalid():
    profile = parse_resume_text_to_profile(
        'Jane Doe\njane@example.com\nPython',
        provider=_FakeResumeParserProvider({'education': 'not-a-list'}),
    )

    assert profile.basic_info['name'] == 'Jane Doe'
    assert profile.basic_info['email'] == 'jane@example.com'
    assert 'Python' in profile.skills.technical


def test_parse_resume_text_to_profile_normalizes_language_objects_and_fills_experience_sections():
    resume_text = """
周传博
cz9z@outlook.com
教育背景
英国帝国理工学院 数据科学硕士 2024.09-至今
实习经历
中智管理咨询有限公司 产品数据分析实习生 上海 2024.05-2024.09
手机银行 App 用户增长与流失预警分析
• 主导 A/B 测试，使页面转化率提升 15%
项目与论文
CRUK 英国癌症研究中心 研究助理 2025.05-2025.07
NLP/文本挖掘/LLM 应用
• 设计并落地 LLM 语义分析流水线
技能与资质
• 编程语言: Python, SQL
• 软件工具: Tableau, Excel
• 语言: 普通话 (母语), 英语 (TOEFL 109)
"""

    profile = parse_resume_text_to_profile(
        resume_text,
        provider=_FakeResumeParserProvider(
            {
                'basic_info': {'name': '周传博', 'email': 'cz9z@outlook.com'},
                'education': [
                    {
                        'school': '英国帝国理工学院',
                        'degree': '硕士',
                        'major': '数据科学',
                        'start_date': '2024.09',
                        'end_date': '至今',
                    }
                ],
                'internships': [],
                'projects': [],
                'skills': {
                    'technical': ['Python'],
                    'tools': [],
                    'languages': [],
                },
                'languages': [
                    {'language': '普通话', 'proficiency': '母语'},
                    {'language': '英语', 'proficiency': 'TOEFL 109'},
                ],
                'candidate_summary': 'Data candidate',
                'inferred_roles': [],
                'inferred_tracks': [],
            }
        ),
    )

    assert profile.languages == ['普通话 (母语)', '英语 (TOEFL 109)']
    assert len(profile.internships) == 1
    assert profile.internships[0].company == '中智管理咨询有限公司'
    assert 'A/B 测试' in profile.internships[0].bullets[1]
    assert len(profile.projects) == 1
    assert 'LLM 语义分析流水线' in profile.projects[0].bullets[1]


def test_parse_resume_text_to_profile_normalizes_contact_links_and_sanitizes_summary():
    profile = parse_resume_text_to_profile(
        """
周传博 | +86 195-2279-3128 | cz9z@outlook.com | GitHub: github.com/Slackness1
教育背景
英国帝国理工学院 数据科学硕士 2024.09-至今
""",
        provider=_FakeResumeParserProvider(
            {
                'basic_info': {
                    '姓名': '周传博',
                    '邮箱': 'cz9z@outlook.com',
                    'GitHub': 'github.com/Slackness1',
                },
                'education': [],
                'skills': {},
                'candidate_summary': '周传博 | +86 195-2279-3128 | cz9z@outlook.com | 教育背景 | 英国帝国理工学院 数据科学硕士 2024.09-至今',
            }
        ),
    )

    assert profile.basic_info['name'] == '周传博'
    assert profile.basic_info['email'] == 'cz9z@outlook.com'
    assert profile.basic_info['phone'] == '+86 195-2279-3128'
    assert profile.basic_info['github'] == 'github.com/Slackness1'
    assert profile.candidate_summary == ''


def test_build_heuristic_resume_profile_extracts_education_internships_projects_and_languages():
    resume_text = """
周传博
cz9z@outlook.com
教育背景
英国帝国理工学院 数据科学硕士 2024.09-至今
英国剑桥大学 理论经济学硕士 2022.10-2024.03
实习经历
中智管理咨询有限公司 产品数据分析实习生 上海 2024.05-2024.09
手机银行 App 用户增长与流失预警分析
• 基于 K-Means 聚类构建用户分层体系
项目与论文
CRUK 英国癌症研究中心 研究助理 2025.05-2025.07
NLP/文本挖掘/LLM 应用
• 设计并落地 LLM 语义分析流水线
技能与资质
• 编程语言: Python, SQL
• 软件工具: Tableau, Excel
• 语言: 普通话 (母语), 英语 (TOEFL 109)
"""

    profile = build_heuristic_resume_profile(resume_text)

    assert len(profile.education) == 2
    assert profile.education[0].school == '英国帝国理工学院'
    assert profile.education[0].degree == '硕士'
    assert profile.education[0].major == '数据科学'
    assert len(profile.internships) == 1
    assert profile.internships[0].company == '中智管理咨询有限公司'
    assert 'K-Means' in profile.internships[0].bullets[1]
    assert len(profile.projects) == 1
    assert profile.projects[0].name == 'CRUK 英国癌症研究中心'
    assert profile.projects[0].role == '研究助理'
    assert profile.languages == ['普通话 (母语)', '英语 (TOEFL 109)']
    assert 'Python' in profile.skills.technical
    assert 'Tableau' in profile.skills.tools


def test_build_heuristic_resume_profile_keeps_contacts_out_of_candidate_summary():
    resume_text = """
周传博
+86 195-2279-3128 | cz9z@outlook.com | GitHub: github.com/Slackness1
教育背景
英国帝国理工学院 数据科学硕士 2024.09-至今
"""

    profile = build_heuristic_resume_profile(resume_text)

    assert profile.basic_info['email'] == 'cz9z@outlook.com'
    assert profile.basic_info['phone'] == '+86 195-2279-3128'
    assert profile.basic_info['github'] == 'github.com/Slackness1'
    assert profile.candidate_summary == ''


def test_build_heuristic_resume_profile_merges_wrapped_internship_bullets():
    resume_text = """
周传博
实习经历
中科创达软件有限公司 商业分析实习生 伦敦 2025.01-2025.05
欧洲新能源市场进入战略
• 算法优化：主导为 RL 交易算法进行特征工程（整合电网频率、卫星云图等数据），回测验证使模型夏普比率提升 0.15，高波动
日 Alpha 收益提升 12%。
浙商证券股份有限公司 投资银行部 债券承做实习生 上海 2023.08–2024.02
• 行业研究/洞察（专题）：在导师指导下完成内部研究，以半导体/
先进制造产业链为主线，形成可用于项目讨论的分析框架
• 政策与工具梳理：输出 “合
规边界清单 + 风险点提示”
"""

    profile = build_heuristic_resume_profile(resume_text)

    assert len(profile.internships) == 2
    assert profile.internships[0].bullets[1] == (
        '算法优化：主导为 RL 交易算法进行特征工程（整合电网频率、卫星云图等数据），'
        '回测验证使模型夏普比率提升 0.15，高波动日 Alpha 收益提升 12%。'
    )
    assert profile.internships[1].bullets[0] == (
        '行业研究/洞察（专题）：在导师指导下完成内部研究，以半导体/先进制造产业链为主线，'
        '形成可用于项目讨论的分析框架'
    )
    assert profile.internships[1].bullets[1] == '政策与工具梳理：输出 “合规边界清单 + 风险点提示”'


def test_build_resume_parser_provider_requires_api_key(monkeypatch):
    monkeypatch.delenv('RESUME_COPILOT_LLM_API_KEY', raising=False)
    importlib.reload(config)

    with pytest.raises(ValueError, match='RESUME_COPILOT_LLM_API_KEY'):
        build_resume_parser_provider()


def test_build_resume_llm_client_uses_config_defaults(monkeypatch):
    monkeypatch.delenv('RESUME_COPILOT_MAX_UPLOAD_MB', raising=False)
    monkeypatch.delenv('RESUME_COPILOT_LLM_BASE_URL', raising=False)
    monkeypatch.delenv('RESUME_COPILOT_LLM_API_KEY', raising=False)
    monkeypatch.delenv('RESUME_COPILOT_LLM_MODEL', raising=False)
    monkeypatch.delenv('RESUME_COPILOT_LLM_TIMEOUT_SECONDS', raising=False)
    monkeypatch.delenv('RESUME_COPILOT_RERANK_TOP_N', raising=False)
    importlib.reload(config)

    client = build_resume_llm_client()

    assert config.RESUME_COPILOT_MAX_UPLOAD_MB == 10
    assert config.RESUME_COPILOT_LLM_BASE_URL == 'https://open.bigmodel.cn/api/paas/v4'
    assert config.RESUME_COPILOT_LLM_API_KEY == ''
    assert config.RESUME_COPILOT_LLM_MODEL == 'glm-5.0'
    assert config.RESUME_COPILOT_LLM_TIMEOUT_SECONDS == 30
    assert config.RESUME_COPILOT_RERANK_TOP_N == 20
    assert isinstance(client, OpenAICompatibleLLMClient)
    assert client.base_url == 'https://open.bigmodel.cn/api/paas/v4'
    assert client.model == 'glm-5.0'
    assert client.timeout_seconds == 30
    assert client.chat_completions_url == 'https://open.bigmodel.cn/api/paas/v4/chat/completions'


def test_build_resume_llm_client_allows_env_override(monkeypatch):
    monkeypatch.setenv('RESUME_COPILOT_LLM_BASE_URL', 'https://llm.example.com/v1/')
    monkeypatch.setenv('RESUME_COPILOT_LLM_API_KEY', 'test-key')
    monkeypatch.setenv('RESUME_COPILOT_LLM_MODEL', 'custom-model')
    monkeypatch.setenv('RESUME_COPILOT_LLM_TIMEOUT_SECONDS', '45')
    monkeypatch.setenv('RESUME_COPILOT_MAX_UPLOAD_MB', '12')
    monkeypatch.setenv('RESUME_COPILOT_RERANK_TOP_N', '8')
    importlib.reload(config)

    client = build_resume_llm_client()

    assert config.RESUME_COPILOT_MAX_UPLOAD_MB == 12
    assert config.RESUME_COPILOT_RERANK_TOP_N == 8
    assert client.base_url == 'https://llm.example.com/v1'
    assert client.api_key == 'test-key'
    assert client.model == 'custom-model'
    assert client.timeout_seconds == 45
    assert client.chat_completions_url == 'https://llm.example.com/v1/chat/completions'
