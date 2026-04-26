from unittest.mock import patch

from app.services.interview.nowcoder import summarizer
from app.services.interview.nowcoder.scraper import PostDetail


def _post(company="字节", date="26-4-14", pos="数据分析", qs="拆解DAU下降5%; A/B样本量计算") -> PostDetail:
    return PostDetail(pid="x", company=company, interview_date=date, position=pos, questions_text=qs, parse_status="ok")


def test_summarize_returns_empty_when_no_posts():
    assert summarizer.summarize_keyword("产品经理", []) == ""


def test_summarize_calls_llm_with_compact_input():
    posts = [_post(), _post(company="美团", qs="评估新功能成功标准; 留存归因")]
    with patch.object(summarizer, "_call_llm", return_value="## 高频考察方向\n- 指标拆解\n- A/B 实验") as mock:
        out = summarizer.summarize_keyword("数据分析师", posts)
    assert "高频考察方向" in out
    sent_prompt = mock.call_args.args[0]
    assert "数据分析师" in sent_prompt
    assert "字节" in sent_prompt and "美团" in sent_prompt


def test_summarize_returns_empty_on_llm_failure():
    posts = [_post()]
    with patch.object(summarizer, "_call_llm", side_effect=RuntimeError("upstream down")):
        out = summarizer.summarize_keyword("产品经理", posts)
    assert out == ""


def test_summarize_caps_post_count():
    posts = [_post(qs=f"问题{i}") for i in range(50)]
    with patch.object(summarizer, "_call_llm", return_value="ok") as mock:
        summarizer.summarize_keyword("k", posts)
    sent_prompt = mock.call_args.args[0]
    # Should not include all 50; we cap input to keep prompt small
    assert sent_prompt.count("问题") <= 20
