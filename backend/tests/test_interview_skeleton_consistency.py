"""Skeleton ↔ ProgressRail label consistency guards.

历史 bad case：前端 ProgressRail 写死 6 个标签（自我介绍/项目/技术取舍/不确定决策/
为什么公司/反问），但后端 SKELETON_QUESTIONS['default'] 后 4 题问的是
"最能体现能力/为什么对岗位/团队冲突/给自己建议" — 从第 3 题开始 rail 在说谎。

修复后 backend 是唯一真相源（GET /api/interview/skeleton 返回 topic_labels
+ questions），ProgressRail 拉这个端点。这里钉死后端契约：
- topic_labels 和 default skeleton 必须等长
- 每个 track 的 skeleton 长度都等于 topic_labels 长度
- 每个 skeleton 第 i 题文字必须能"看出"它对应第 i 个 topic_label

实现这些 invariant 的方式是命名约定 — 不强求自然语言匹配，但用关键词查表确保
人改 skeleton 时不会偷偷错位。
"""
from app.services.interview.adaptive import SKELETON_QUESTIONS, SKELETON_TOPIC_LABELS

# Per topic_label index, 至少出现一个关键词（出现任一即可）
# 用来防止"调换两题次序但忘改 topic_labels"这种漂移。
_TOPIC_KEYWORDS_BY_INDEX: list[list[str]] = [
    ["自我介绍"],                  # 0 自我介绍与来意
    ["项目", "你做了什么", "目标"],  # 1 主导过的核心项目
    ["取舍", "权衡", "选型", "为什么这么选"],  # 2 关键技术 / 业务取舍
    ["不确定", "信息不完整", "决策", "推动"],  # 3 在不确定下的决策
    ["这家公司", "选这家", "为什么选", "为什么"],  # 4 为什么是这家公司
    ["反过来问", "反问", "你想"],   # 5 反问环节
]


def test_topic_labels_match_default_skeleton_length():
    assert len(SKELETON_TOPIC_LABELS) == len(SKELETON_QUESTIONS["default"])


def test_every_chip_skeleton_has_same_length_as_topic_labels():
    n = len(SKELETON_TOPIC_LABELS)
    for chip, skeleton in SKELETON_QUESTIONS.items():
        assert len(skeleton) == n, (
            f"chip '{chip}' has {len(skeleton)} questions but topic_labels has {n}"
        )


def test_each_topic_index_has_keyword_match_in_default_skeleton():
    skeleton = SKELETON_QUESTIONS["default"]
    for i, keywords in enumerate(_TOPIC_KEYWORDS_BY_INDEX):
        q = skeleton[i]
        assert any(k in q for k in keywords), (
            f"default skeleton[{i}] '{q}' doesn't contain any of the expected "
            f"keywords for topic '{SKELETON_TOPIC_LABELS[i]}': {keywords}. "
            f"Did you swap question order without updating SKELETON_TOPIC_LABELS?"
        )


def test_each_topic_index_has_keyword_match_in_all_chip_skeletons():
    for chip, skeleton in SKELETON_QUESTIONS.items():
        for i, keywords in enumerate(_TOPIC_KEYWORDS_BY_INDEX):
            q = skeleton[i]
            assert any(k in q for k in keywords), (
                f"chip '{chip}' skeleton[{i}] '{q}' doesn't contain any of "
                f"the expected keywords for topic '{SKELETON_TOPIC_LABELS[i]}': "
                f"{keywords}"
            )


def test_skeleton_endpoint_returns_labels_and_questions():
    """Smoke test the /skeleton endpoint shape via TestClient."""
    from fastapi.testclient import TestClient
    from app.main import app
    client = TestClient(app)
    resp = client.get('/api/interview/skeleton', params={'chip': '数据分析师'})
    assert resp.status_code == 200
    data = resp.json()
    assert data['chip'] == '数据分析师'
    assert data['matched'] is True
    assert data['topic_labels'] == list(SKELETON_TOPIC_LABELS)
    assert len(data['questions']) == len(SKELETON_TOPIC_LABELS)


def test_skeleton_endpoint_falls_back_to_default_for_unknown_chip():
    from fastapi.testclient import TestClient
    from app.main import app
    client = TestClient(app)
    resp = client.get('/api/interview/skeleton', params={'chip': '量子计算工程师'})
    assert resp.status_code == 200
    data = resp.json()
    assert data['matched'] is False
    assert data['questions'] == SKELETON_QUESTIONS['default']
