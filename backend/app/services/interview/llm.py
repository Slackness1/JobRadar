import json
from typing import Iterator, Optional
from urllib import request as urllib_request

from sqlalchemy.orm import Session

from app.services.interview.adaptive import SKELETON_TOPIC_LABELS
from app.services.interview.anchors import load_rubric_anchors, load_qa_seeds
from app.services.interview.nowcoder import intel_provider
from app.services.resume_copilot.llm import build_resume_llm_client

INTERVIEW_END_MARKER = '[INTERVIEW_END]'

_TURN_LIMIT = 14
_JD_PROMPT_TRUNCATE = 1800  # JD 太长会冲掉 anchor — 截 1.8KB 已足够提炼焦点


def _build_jerry_style_block() -> str:
    """从 anchors 抽 3 条最 actionable 的面试官行动准则，注入 system prompt。"""
    anchors = load_rubric_anchors()
    by_id = {d['id']: d for d in anchors['dimensions']}
    pieces: list[str] = []
    pieces.append('## 面试官风格（资深战略咨询 senior 老师风格）')
    pieces.append('- **不要做评价**：每轮只问，不要点评候选人答得好不好；评分留给最后报告。')
    pieces.append('- **读场**：候选人停在第一层时主动追问'
                  '"客户/团队的痛点是什么"或'
                  '"那个项目最后给业务带来了什么变化"；候选人钻进第三层细节时'
                  '把话拉回到"那这个决策背后的取舍是什么"。')
    pieces.append('- **追问优先级**（高→低）：'
                  '(1) 客户痛点缺失；(2) 量化结果缺失；(3) 关键取舍/方法理由缺失；'
                  '(4) 候选人逻辑跳跃；(5) 候选人答得过短(<50字)。')
    structure = by_id.get('structure', {})
    motivation = by_id.get('motivation', {})
    if structure:
        pieces.append(f"- **结构感**：参考资深面试官「{structure['rationale']}」 — "
                      f"如果候选人讲到 90s 还没出现明确结构（"
                      f"'我做的三件事' / '痛点→目标→方法→交付'），就用一个具体的追问把话题收回来。")
    if motivation:
        pieces.append(f"- **动机维度**：「{motivation['rationale']}」 — "
                      f"问'为什么是这家公司'时不要满足于"
                      f"'我喜欢咨询的工作方式'这种飘话；让候选人给一个具体的近期项目/动态。")
    return '\n'.join(pieces)


def _build_jd_focus_block(jd_content: str) -> str:
    """让 LLM 自己从 JD 提炼 2-3 个考察重点（在 system prompt 中显式告诉它怎么用 JD）。"""
    trimmed = jd_content.strip()[:_JD_PROMPT_TRUNCATE]
    return (
        '## 岗位 JD（用来定制考察重点）\n'
        f'```\n{trimmed}\n```\n'
        '从这份 JD 里提炼 2-3 个本岗位的**核心考察点**（比如要求的具体技术栈、'
        '业务领域、协作模式），在第 2 题（项目深挖）和第 3 题（关键取舍）的追问里'
        '主动落到这些点上 — 但不要简单把 JD 原文当问题念出来。'
    )


def _build_track_qa_block(target_job: str) -> str:
    """根据 track / target_job 拉 2 条最相关的 Jerry QA seed 作为 few-shot 启发。"""
    seeds = load_qa_seeds()
    keywords = {'数据分析师': '数据分析', '产品经理': '咨询', '前端开发': '咨询',
                '后端开发': '咨询', '金融科技': '金融科技', '量化': '量化',
                '科技咨询': '科技咨询', '咨询': '咨询'}
    relevant_tracks: list[str] = []
    for k, v in keywords.items():
        if k in target_job:
            relevant_tracks.append(v)
    if not relevant_tracks:
        relevant_tracks = ['咨询', '金融科技']
    matched: list[dict] = []
    for s in seeds:
        track_list = s.get('track', [])
        if any(t in track_list for t in relevant_tracks) and len(matched) < 2:
            matched.append(s)
    if not matched:
        return ''
    lines = ['## 同方向资深面试官的高质量问题样例（仅供风格参考，不要直接复述）']
    for s in matched:
        lines.append(f"- 问：{s['question']}")
        pitfall = (s.get('common_pitfalls') or [''])[0]
        if pitfall:
            lines.append(f"  典型踩坑：{pitfall} — 候选人这么答时，追问回到结构 / 痛点。")
    return '\n'.join(lines)


def build_interview_system_prompt(
    target_job: str,
    db: Optional[Session] = None,
    jd_content: Optional[str] = None,
) -> str:
    skeleton_recipe = '\n'.join(
        f"{i + 1}. **{label}**" for i, label in enumerate(SKELETON_TOPIC_LABELS)
    )
    base = f"""你是一位专业的校招面试官，对一名应届生进行一对一面试。
目标岗位：{target_job}

## 面试流程（共 6 个主题点位，每个点位 1-3 轮深挖）
{skeleton_recipe}

## 面试规则
1. 按上面 6 个主题点位顺序推进；每个点位讲清楚再切下一个。
2. 主题 1-2 是行为类（让候选人讲项目，按 客户痛点→目标→方法→交付 框架）；
   主题 3-4 偏取舍 / 决策；主题 5 是动机；主题 6 是反问。
3. 每次只问一个问题；语气专业但不刻板；**不要提前评价候选人表现**。
4. 累计对话达到 {_TURN_LIMIT} 轮后给一句简短收尾，并在消息末尾追加 {INTERVIEW_END_MARKER}。
5. 如候选人主动说"结束面试"，立即收尾并追加 {INTERVIEW_END_MARKER}。

## 开场
第一条消息：用一句话介绍自己的面试官身份，然后直接提出第 1 个主题（自我介绍）。
"""

    blocks: list[str] = [base, _build_jerry_style_block()]

    track_block = _build_track_qa_block(target_job)
    if track_block:
        blocks.append(track_block)

    if jd_content and jd_content.strip():
        blocks.append(_build_jd_focus_block(jd_content))

    if db is not None:
        intel = intel_provider.get_intel_for_target_job(db, target_job)
        if intel is not None and intel.summary_md.strip():
            blocks.append(
                '## 最近公开面经的高频考察方向（仅作出题灵感，不要直接复述原题）\n'
                + intel.summary_md.strip()
                + f"\n\n（参考 {intel.source_count} 条牛客网公开面经）"
            )

        # Pluggable knowledge sources (podcast / future memory / future tencent…).
        # Strangler-fig: lives alongside the hardcoded blocks above, doesn't
        # replace them. New sources register via app.services.llm_context.bootstrap.
        try:
            from app.services.llm_context import ContextRequest, fetch_blocks
            from app.services.llm_context.base import PURPOSE_INTERVIEW_QUESTION
            blocks.extend(fetch_blocks(ContextRequest(
                purpose=PURPOSE_INTERVIEW_QUESTION,
                db=db,
                target_job=target_job,
            )))
        except Exception:
            pass  # context layer must never break interview prompt build

    return '\n\n'.join(blocks)


def stream_interview_turn(
    target_job: str,
    messages: list[dict],
    db: Optional[Session] = None,
    jd_content: Optional[str] = None,
) -> Iterator[str]:
    # Phase 2 (2026-05-24): per-turn 流式生成 — flash + reasoning=low (latency
    # 敏感, ≤3s budget)。V4 默认 thinking, reasoning=low 把 thinking 压到 ~40-100
    # tokens 避免 first-byte 延迟。
    client = build_resume_llm_client()
    payload = {
        'model': client.model,
        'stream': True,
        'stream_options': {'include_usage': True},
        'reasoning_effort': 'low',
        'messages': [
            {
                'role': 'system',
                'content': build_interview_system_prompt(
                    target_job, db=db, jd_content=jd_content,
                ),
            },
            *messages,
        ],
    }
    req = urllib_request.Request(
        client.chat_completions_url,
        data=json.dumps(payload).encode('utf-8'),
        headers={
            'Authorization': f'Bearer {client.api_key}',
            'Content-Type': 'application/json',
        },
        method='POST',
    )
    stream_timeout = max(client.timeout_seconds, 120)
    with urllib_request.urlopen(req, timeout=stream_timeout) as response:
        for raw_line in response:
            line = raw_line.decode('utf-8').rstrip('\n')
            if line:
                # 抠 usage 字段 (final chunk),记账后照常 yield
                if line.startswith('data:'):
                    payload_str = line[len('data:'):].strip()
                    if payload_str and payload_str != '[DONE]':
                        try:
                            event = json.loads(payload_str)
                            usage = event.get('usage') if isinstance(event, dict) else None
                            if isinstance(usage, dict):
                                from app.services.llm_quota import record_usage_from_response_for_current
                                record_usage_from_response_for_current('interview_turn', {'usage': usage})
                        except Exception:
                            pass
                yield line + '\n'
