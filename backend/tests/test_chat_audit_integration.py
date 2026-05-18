"""chat.py audit_draft 集成单元测试。

覆盖:
  - _profile_to_evidence_list 把整份 profile 转 Evidence + 自动抽 tag
  - _audit_rewrite_options 接 audit_draft + 填 audit_risks + warning_severity
  - _filter_audit_risks_against_original 差量过滤 leadership/tech token
"""
from __future__ import annotations

import pytest

from app.schemas_resume_copilot import RewriteOption
from app.services.resume_copilot.chat import (
    _audit_rewrite_options,
    _filter_audit_risks_against_original,
    _profile_to_evidence_list,
)
from app.services.resume_copilot.plan import RiskFlag


@pytest.fixture
def saif_profile_dict():
    return {
        'candidate_summary': '上海高金 SAIF 金融硕士,投研方向',
        'education': [{
            'school': '上海交通大学高级金融学院',
            'degree': '金融硕士',
            'major': '金融硕士',
            'highlights': ['GPA 3.8'],
        }],
        'internships': [{
            'company': '中信证券',
            'role': '行研助理',
            'bullets': [
                '参与跟踪 5 只半导体股票,撰写 3 篇深度报告',
                '协助高级分析师整理财务模型',
            ],
        }],
        'projects': [{
            'name': '量化因子项目',
            'role': '主程',
            'tech_stack': ['Python', 'pandas'],
            'bullets': ['搭建多因子模型,IR 提升 20%'],
        }],
        'skills': {
            'technical': ['Python', 'SQL'],
            'tools': ['Wind', 'Bloomberg'],
            'languages': ['英语'],
        },
        'awards': ['CFA Level II 通过'],
        'languages': ['中文', 'English'],
    }


class TestProfileToEvidence:
    def test_收集所有bullets(self, saif_profile_dict):
        ev = _profile_to_evidence_list(saif_profile_dict)
        texts = [e.text for e in ev]
        assert any('参与跟踪 5 只半导体股票' in t for t in texts)
        assert any('搭建多因子模型,IR 提升 20%' in t for t in texts)
        assert any('CFA Level II' in t for t in texts)

    def test_含技术栈作为证据(self, saif_profile_dict):
        ev = _profile_to_evidence_list(saif_profile_dict)
        texts = [e.text for e in ev]
        # 技术栈是单独 evidence
        assert 'Python' in texts
        assert 'Wind' in texts

    def test_empty_profile返空列表(self):
        ev = _profile_to_evidence_list({})
        assert ev == []


class TestAuditRewriteOptions:
    def _mk_opt(self, original, improved, opt_id='A'):
        return RewriteOption(
            option_id=opt_id, label=f'方案 {opt_id}',
            section='internships', field_path='internships.0.bullets',
            target_title='中信证券 · 行研助理',
            original=[original], improved=[improved], rationale='',
        )

    def test_clean_rewrite_info严重度(self, saif_profile_dict):
        opt = self._mk_opt(
            '参与跟踪 5 只半导体股票,撰写 3 篇深度报告',
            '跟踪 5 只半导体股票,撰写 3 篇深度报告',
        )
        _audit_rewrite_options([opt], saif_profile_dict)
        # 没有 audit_risks
        assert opt.audit_risks == []
        assert opt.warning_severity == 'info'

    def test_数字编造_severe(self, saif_profile_dict):
        # 改成 30 只 (原本 5 只)
        opt = self._mk_opt(
            '参与跟踪 5 只半导体股票,撰写 3 篇深度报告',
            '主导跟踪 30 只半导体股票,撰写 15 篇深度报告',
        )
        _audit_rewrite_options([opt], saif_profile_dict)
        assert opt.warning_severity == 'severe'
        kinds = {r['kind'] for r in opt.audit_risks}
        assert 'overclaim' in kinds

    def test_角色升级_差量检查_original无主导则severe(self, saif_profile_dict):
        # original 是"参与/协助",improved 是"主导" → 应 flag
        opt = self._mk_opt(
            '参与跟踪 5 只半导体股票,撰写 3 篇深度报告',
            '主导跟踪 5 只半导体股票,撰写 3 篇深度报告',
        )
        _audit_rewrite_options([opt], saif_profile_dict)
        kinds = {r['kind'] for r in opt.audit_risks}
        assert 'leadership_unverified' in kinds

    def test_角色保留_差量检查_original已有主导则clean(self, saif_profile_dict):
        # original 已含"主导",improved 保留之 → 不应 flag
        opt = self._mk_opt(
            '主导某项目,跟踪 5 只半导体股票',
            '主导某项目,跟踪 5 只半导体股票,撰写 3 篇深度报告',
        )
        _audit_rewrite_options([opt], saif_profile_dict)
        # leadership 应被过滤
        kinds = {r['kind'] for r in opt.audit_risks}
        assert 'leadership_unverified' not in kinds

    def test_tech_unverified_新引入(self, saif_profile_dict):
        # 改写引入了 Bloomberg 但原文没有 (虽然 skills.tools 有 Bloomberg,
        # 差量对比的是 original 文本,不是整 profile evidence — 注意:
        # audit_draft 看 evidence 池,Bloomberg 在 skills tools 里,
        # 所以 tag_techs/all_text 含 Bloomberg,不会触发 tech_unverified)
        opt = self._mk_opt(
            '参与跟踪 5 只半导体股票',
            '使用 Bloomberg 跟踪 5 只半导体股票,撰写报告',
        )
        _audit_rewrite_options([opt], saif_profile_dict)
        # Bloomberg 在 skills,不算 unverified
        # 但 Python 不会触发 (在 evidence 里)
        # 如果引入 Reuters 才会触发
        opt2 = self._mk_opt(
            '参与跟踪 5 只半导体股票',
            '使用 Reuters 跟踪 5 只半导体股票,撰写报告',
        )
        _audit_rewrite_options([opt2], saif_profile_dict)
        # Reuters 不在 evidence,且 original 没有 → severe
        kinds = {r['kind'] for r in opt2.audit_risks}
        assert 'tech_unverified' in kinds


class TestFilterAgainstOriginal:
    def test_保留original已有leadership(self):
        flags = [RiskFlag(kind='leadership_unverified', detail="draft uses '主导' but no verb_subject=self", blocking=True)]
        original = '主导某项目'
        out = _filter_audit_risks_against_original(flags, original)
        assert out == []

    def test_保留original已有tech(self):
        flags = [RiskFlag(kind='tech_unverified', detail="draft mentions 'React' not in evidence", blocking=True)]
        original = '用 React 写前端'
        out = _filter_audit_risks_against_original(flags, original)
        assert out == []

    def test_新引入leadership不过滤(self):
        flags = [RiskFlag(kind='leadership_unverified', detail="draft uses '主导' but no verb_subject=self", blocking=True)]
        original = '参与某项目'  # 没主导
        out = _filter_audit_risks_against_original(flags, original)
        assert len(out) == 1

    def test_overclaim数字不走差量过滤(self):
        # overclaim 维度不应被差量过滤 (数字编造不允许)
        flags = [RiskFlag(kind='overclaim', detail="draft contains '50' not in evidence", blocking=True)]
        original = '50 家公司'  # 即便 original 含 50, overclaim 仍 flag (这层防护更严)
        out = _filter_audit_risks_against_original(flags, original)
        assert len(out) == 1  # overclaim 不被过滤
