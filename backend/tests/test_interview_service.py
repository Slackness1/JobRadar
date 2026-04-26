import json
import pytest

from app.services.interview.llm import build_interview_system_prompt, INTERVIEW_END_MARKER
from app.services.interview.report import parse_report_json


def test_system_prompt_contains_target_job():
    prompt = build_interview_system_prompt("蚂蚁集团数据分析师")
    assert "蚂蚁集团数据分析师" in prompt


def test_system_prompt_contains_end_marker():
    prompt = build_interview_system_prompt("test job")
    assert INTERVIEW_END_MARKER in prompt


def test_system_prompt_mentions_behavioral_questions():
    prompt = build_interview_system_prompt("test job")
    assert "行为" in prompt


def test_parse_report_json_valid():
    raw = json.dumps({
        "overall_score": 78,
        "dimensions": [
            {"name": "表达清晰度", "score": 80, "comment": "清晰"},
            {"name": "逻辑结构", "score": 75, "comment": "较好"},
            {"name": "岗位匹配度", "score": 82, "comment": "匹配"},
            {"name": "抗压表现", "score": 70, "comment": "一般"},
        ],
        "highlights": ["亮点1"],
        "improvements": ["改进1"],
        "overall_comment": "总体不错",
    })
    result = parse_report_json(raw)
    assert result["overall_score"] == 78
    assert len(result["dimensions"]) == 4
    assert result["highlights"] == ["亮点1"]


def test_parse_report_json_clamps_score():
    raw = json.dumps({"overall_score": 150, "dimensions": [], "highlights": [], "improvements": [], "overall_comment": ""})
    result = parse_report_json(raw)
    assert result["overall_score"] == 100


def test_parse_report_json_handles_missing_fields():
    raw = json.dumps({})
    result = parse_report_json(raw)
    assert "overall_score" in result
    assert "dimensions" in result


from unittest.mock import patch
from app.services.interview.nowcoder.intel_provider import IntelView


def test_system_prompt_no_db_uses_base_only():
    prompt = build_interview_system_prompt("产品经理", db=None)
    assert "高频考察方向" not in prompt
    assert "产品经理" in prompt


def test_system_prompt_injects_intel_when_present():
    fake = IntelView(keyword="产品经理", summary_md="## 高频考察方向\n- 用户增长", source_count=8)
    with patch("app.services.interview.llm.intel_provider.get_intel_for_target_job", return_value=fake):
        prompt = build_interview_system_prompt("字节产品经理实习", db="dummy")
    assert "高频考察方向" in prompt
    assert "用户增长" in prompt
    assert "8 条" in prompt or "8条" in prompt


def test_system_prompt_no_intel_uses_base_only():
    with patch("app.services.interview.llm.intel_provider.get_intel_for_target_job", return_value=None):
        prompt = build_interview_system_prompt("宁德时代电芯研发", db="dummy")
    assert "高频考察方向" not in prompt
