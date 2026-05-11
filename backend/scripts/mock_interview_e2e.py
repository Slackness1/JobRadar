"""End-to-end mock interview against the real DeepSeek LLM.

Runs a 6-turn mock using:
- 真实候选人背景 (作者周传博 — 帝国理工 DS / 剑桥 Econ / 中科创达虚拟电厂)
- 真实 JD-equivalent context (字节跳动 金融数据分析师, 量化方向)
- 真实候选人答案 (摘自 Obsidian 笔记 — 自我介绍/项目深挖等真实写过的内容)
- 真实 LLM (DeepSeek V4-flash)

重点观察：
- 项目深挖 (turn 1) 时 LLM 是否真的按 客户痛点→目标→方法→交付物 追问
- 后续 turn 是否能根据答案触发 follow-up (when score < 60 or misses present)
- 最后生成的 Jerry-flavored 反馈报告 6 维评分是否站得住

Run: PYTHONPATH=. .venv/bin/python scripts/mock_interview_e2e.py
"""
from __future__ import annotations

import json
import logging
import sys
import textwrap
import uuid
from typing import Any

logging.basicConfig(level=logging.WARNING, format='[%(levelname)s] %(message)s')


# ---------------------------------------------------------------------------
# Test fixtures — 真实素材
# ---------------------------------------------------------------------------

TARGET_JOB = '数据分析师 · 字节跳动金融业务数据中台'
JD_CONTENT = textwrap.dedent("""
方向：金融科技 / 数据分析
赛道：互联网大厂金融业务
地点：上海
岗位概述：负责字节金融业务（支付、信贷、理财）的数据中台建设与业务诊断，
重点覆盖用户行为分析、转化漏斗优化、风险识别与因果实验设计。要求扎实的
SQL/Python 能力，熟悉 A/B 测试与因果推断（DID/PSM），有金融场景或量化
建模背景者优先。
公开情报：字节金融业务正从合规收敛期转向精细化运营期，对'分析→业务动作'
的能力要求很高，特别是把模型结论翻译成准入/调额/触达策略。
所在部门：金融业务数据中台 / 商业分析
推荐理由：候选人有英国电力市场小时级电价预测项目（树模型 + 滚动回测 +
时序特征工程），可迁移到金融时序场景；有银行财富管理项目（漏斗诊断、
高潜识别、DID 评估）契合金融业务运营。
你的优势：完整建模链路 + 业务策略转化 + 复杂场景闭环推进
风险点：纯互联网大厂数据分析的 A/B 实验经验偏理论；需要展示业务 sense
""").strip()

# 6 轮候选人答案 — 每条都从 Obsidian 笔记里摘了真实写过的话
# 故意混合"答得好的"和"答得有缺陷的"，看 LLM 能不能正确识别并追问
CANDIDATE_ANSWERS = {
    0: textwrap.dedent("""
    面试官您好，我叫周传博，非常感谢有这次交流的机会。我的学术背景围绕
    '经济理论'和'量化分析'两条线展开 —— 本科金融数学，剑桥经济学硕士，
    去年12月拿到帝国理工数据科学硕士。

    简历里我重点放了两段经历。第一段是中科创达，这家公司软件起家但希望
    在新能源寻找增长点，我在战略投资组直接服务老板，目标是通过收购英国
    实体电厂布局虚拟电厂资产。我搭建了英国小时级电价预测和负价风险识别
    框架，最终 MAE 比 ARIMA 基线降低了 12%，帮助团队评估资产收益和风险。

    第二段是普华永道保险集团的财富管理增长项目，我做了客户分层和经营漏斗
    诊断。还有一个我自己做的 JobCopilot 项目，从 0 到 1 搭了一个 Agent
    驱动的求职推荐系统。

    从契合度来说，我有完整的建模链路 + 业务策略转化经验 + 独立闭环推进
    能力，我觉得是非常适合字节金融数据分析这个岗位的。
    """).strip(),

    # 故意混入 Jerry 标注的常见踩坑：直接进入第三层细节（模块名/库名）
    1: textwrap.dedent("""
    电价预测项目我用的是 LightGBM + CatBoost 主模型，ARIMA 做基线。
    数据源主要是英国电力市场数据加多城市天气数据，我做了时间戳 UTC
    对齐、去重、补齐小时索引、异常值检测。特征工程做了 lag 1/24/168
    和 rolling 24/168，还有 residual_load_mw、renewables_share、
    perceived_temp、minutes_from_sunset 这些。最后用滚动回测做了
    模型选择，LightGBM 表现最稳。
    """).strip(),

    # 第三轮：关键取舍 — 这次答得相对完整，承认了局限
    2: textwrap.dedent("""
    最关键的取舍是 **要不要把 ANN 也作为主模型**。当时考虑过深度学习，
    但我评估下来，电价这个任务本质是表格型 + 强特征工程，样本量也只有
    几万级，所以最后决定用 GBDT 系列做主模型，ANN 只做对照。代价是放弃
    了一些极端非线性的捕捉能力，但好处是训练快、可解释、对极端样本不会
    过度记忆。这个决策的依据是滚动回测里 LightGBM 的 MAE 比 ANN 低且
    更稳定。
    """).strip(),

    # 第四轮：在不确定下决策 — 这次答得偏空，没有具体场景
    3: textwrap.dedent("""
    我做项目时经常遇到信息不完整的情况，比如不知道客户具体要什么。
    一般我会先快速搭一个最小框架，然后跟相关人对齐，再迭代。
    """).strip(),

    # 第五轮：为什么是字节金融 — 用了 Jerry 推荐的"收窄子赛道"框架
    4: textwrap.dedent("""
    我选字节金融业务数据中台，不是因为字节大厂光环，而是这个岗位刚好
    在'技术深度'和'业务深度'的交界线。我关注到字节金融最近从合规收敛
    转向精细化运营期，需要的是能把数据真正翻译成准入/调额/触达策略的
    人，这跟我做电价预测时把模型结论翻译成投资建议、做银行项目时把客户
    分层翻译成触达优先级是一脉相承的。
    """).strip(),

    # 第六轮：反问 — 用了真实想问的问题
    5: textwrap.dedent("""
    我想问两个问题。第一，团队目前在因果推断上更多用 PSM/DID 还是
    在尝试 CausalImpact 这种贝叶斯时序方法？第二，对刚入职的应届分析师
    来说，前 6 个月最希望我们能 contribute 的是什么 —— 是更快产出
    标准分析，还是参与某个具体的业务议题深耕？
    """).strip(),
}


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

def run_mock_interview() -> dict:
    from app.services.interview.adaptive import (
        SKELETON_QUESTIONS,
        SKELETON_TOPIC_LABELS,
        generate_followup_question,
        pick_next_question,
    )
    from app.services.interview.llm_helpers import build_interview_llm_client
    from app.services.interview.report import generate_interview_report
    from app.services.interview.scoring import score_answer
    from app.services.interview.weakness_profile import WeaknessProfile, compute_weakness

    chip = '数据分析师'
    skeleton = SKELETON_QUESTIONS[chip]
    llm = build_interview_llm_client()

    print('=' * 78)
    print(f'  Mock Interview · {TARGET_JOB}')
    print(f'  Chip: {chip}  ·  Skeleton labels: {SKELETON_TOPIC_LABELS}')
    print('=' * 78)

    # Storage for transcript + scores per turn
    messages: list[dict] = []
    score_jsons: list[str] = []
    asked_questions: list[str] = []
    followup_count = 0

    for turn_idx in range(len(skeleton)):
        print(f'\n──── Turn {turn_idx} · {SKELETON_TOPIC_LABELS[turn_idx]} ' + '─' * 30)
        # Decide question — for the first 6 turns we use the skeleton verbatim,
        # but if a follow-up was triggered we'd interleave one before advancing.
        weakness = compute_weakness(score_jsons)
        question = skeleton[turn_idx]
        asked_questions.append(question)
        print('面试官 (skeleton):', question)
        messages.append({'role': 'assistant', 'content': question})

        # Candidate answer (from Obsidian)
        answer = CANDIDATE_ANSWERS[turn_idx]
        print(f'\n候选人 (从 Obsidian):\n  {answer[:180]}...' if len(answer) > 180 else f'\n候选人:\n  {answer}')
        messages.append({'role': 'user', 'content': answer})

        # Score this turn (real LLM call) — this is where Jerry rubric is used
        try:
            score = score_answer(
                target_job=TARGET_JOB,
                question=question,
                user_answer=answer,
                chip_summary='',
                llm=llm,
            )
            score_dict = {
                'overall': score.overall,
                'hits': score.hits,
                'misses': score.misses,
                'bonuses': score.bonuses,
            }
            print(f'\n评分: overall={score.overall}  hits={score.hits}  misses={score.misses}')
            score_jsons.append(json.dumps(score_dict, ensure_ascii=False))
        except Exception as e:
            print(f'  [score failed: {e}]')
            score_jsons.append('{}')
            continue

        # Drill-down decision: same logic as orchestrator
        miss_count = len(score_dict.get('misses') or [])
        should_drill = (
            followup_count < 2  # cap follow-ups
            and turn_idx == 1  # 项目深挖 — always try to drill here for demo focus
            and ((score.overall is not None and score.overall < 70) or miss_count >= 1)
        )

        if should_drill:
            print('\n  → 触发 follow-up（项目深挖追问）')
            followup_count += 1
            weakness = compute_weakness(score_jsons)
            try:
                fq = generate_followup_question(
                    target_job=TARGET_JOB,
                    chip_summary='',
                    weakness=weakness,
                    asked_questions=asked_questions,
                    llm=llm,
                    jd_content=JD_CONTENT,
                    current_main_question=question,
                    current_main_answer=answer,
                )
                print(f'  面试官 (follow-up · {fq.source}): {fq.question}')
                asked_questions.append(fq.question)
                messages.append({'role': 'assistant', 'content': fq.question})

                # Synthesize a "second-pass" candidate answer that addresses痛点
                second_pass_answer = textwrap.dedent("""
                客户痛点是字节金融需要小时级粒度的预测来支持自动化决策，原本
                的日级预测在波动大的时段（极端天气、负价时段）误差太大，会让
                自动调价失效。我的目标就是在保持小时级精度的同时控制 MAE，
                让模型输出能直接被业务策略消费。最后我们交付了三件事：小时级
                价格预测、负电价风险识别清单、关键驱动因素归因报告。MAE 降
                12% 这个数字在高波动日下降得更明显，业务侧基于这个上线了一
                个套利交易策略原型。
                """).strip()
                print(f'\n  候选人 (二次回答):\n  {second_pass_answer[:150]}...')
                messages.append({'role': 'user', 'content': second_pass_answer})

                fq_score = score_answer(
                    target_job=TARGET_JOB, question=fq.question,
                    user_answer=second_pass_answer, chip_summary='', llm=llm,
                )
                print(f'\n  follow-up 评分: overall={fq_score.overall}  hits={fq_score.hits}  misses={fq_score.misses}')
                score_jsons.append(json.dumps({
                    'overall': fq_score.overall,
                    'hits': fq_score.hits,
                    'misses': fq_score.misses,
                    'bonuses': fq_score.bonuses,
                }, ensure_ascii=False))
            except Exception as e:
                print(f'  [follow-up failed: {e}]')

    # Final report — Jerry-flavored 6-dim
    print('\n' + '=' * 78)
    print('  生成最终报告 (Jerry-flavored 6 维 rubric)')
    print('=' * 78)
    # Debug: print prompt size + raw LLM response before parse
    from app.services.interview.report import _build_report_system_prompt, parse_report_json
    from app.services.resume_copilot.llm import build_resume_llm_client
    from urllib import request as urllib_request

    sys_prompt = _build_report_system_prompt(track='金融科技')
    print(f'\n[debug] system prompt chars: {len(sys_prompt)}')
    transcript = '\n'.join(
        f"{'面试官' if m['role'] == 'assistant' else '候选人'}：{m['content']}"
        for m in messages
    )
    print(f'[debug] transcript chars: {len(transcript)}')
    client = build_resume_llm_client()
    payload = {
        'model': client.model,
        'response_format': {'type': 'json_object'},
        'messages': [
            {'role': 'system', 'content': sys_prompt},
            {'role': 'user', 'content': f'目标岗位：{TARGET_JOB}\n\n面试记录：\n{transcript}'},
        ],
    }
    req = urllib_request.Request(
        client.chat_completions_url,
        data=json.dumps(payload).encode('utf-8'),
        headers={'Authorization': f'Bearer {client.api_key}', 'Content-Type': 'application/json'},
        method='POST',
    )
    try:
        with urllib_request.urlopen(req, timeout=120) as response:
            body_text = response.read().decode('utf-8')
        body = json.loads(body_text)
        raw = body['choices'][0]['message']['content']
        print(f'[debug] raw LLM content (first 500 chars):\n{raw[:500]}')
        print(f'[debug] raw LLM content length: {len(raw)}')
        report = parse_report_json(raw)
    except Exception as e:
        print(f'  [report failed: {type(e).__name__}: {e}]')
        return {'messages': messages, 'score_jsons': score_jsons, 'report': None}

    print(f"\n总分: {report['overall_score']}")
    print('\n各维度:')
    for d in report['dimensions']:
        print(f"  {d['name']:>10s}  {d['score']:3d}  | {d['comment']}")
    print('\nHighlights:')
    for h in report['highlights']:
        print(f'  + {h}')
    print('\nImprovements:')
    for i in report['improvements']:
        print(f'  → {i}')
    print(f"\nOverall: {report['overall_comment']}")

    return {'messages': messages, 'score_jsons': score_jsons, 'report': report}


if __name__ == '__main__':
    try:
        result = run_mock_interview()
    except KeyboardInterrupt:
        print('\nInterrupted', file=sys.stderr)
        sys.exit(130)
    print('\n✓ done')
