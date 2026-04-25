"""
Shared read-only demo session.

Seeded once at startup and never deleted by guest cleanup. The HiFi-style
"看示例推荐" / "使用示例简历" entry points all redirect users to
/resume-copilot?sessionId=1, where this fully-prepared session lives.

Write-side endpoints (`PUT confirmed-profile`, `POST chat`, `POST generate`,
`POST chat/apply-rewrite`, `PATCH /sessions/{id}`, `DELETE /sessions/{id}`)
must reject this id via `_assert_not_demo` in the router.
"""
from __future__ import annotations

import json

from sqlalchemy.orm import Session

from app.models import (
    ResumeConfirmedProfile,
    ResumeCopilotMessage,
    ResumeCopilotSession,
    ResumeDirectionAnalysisRun,
    ResumeParsedProfile,
    ResumePreferenceProfile,
    ResumeRecommendationRun,
)
from app.schemas_resume_copilot import (
    DirectionTierResult,
    ResumePreferencePayload,
    ResumeProfilePayload,
)
from app.services.resume_copilot.recommendation import recommend_jobs_for_profile

DEMO_SESSION_ID = 1

DEMO_PROFILE_DICT: dict[str, object] = {
    "basic_info": {
        "name": "张三",
        "email": "zhangsan@sjtu.edu.cn",
        "phone": "",
        "city": "上海",
        "gender": "男",
    },
    "education": [
        {
            "school": "上海交通大学",
            "degree": "本科",
            "major": "计算机科学与技术",
            "start_date": "2022.09",
            "end_date": "2026.06",
            "highlights": ["GPA 3.7/4.0", "ACM 校赛铜奖"],
        }
    ],
    "internships": [
        {
            "company": "字节跳动",
            "role": "数据分析实习生",
            "start_date": "2025.06",
            "end_date": "2025.10",
            "bullets": [
                "负责抖音电商主站新用户增长分析，搭建 GMV 与留存归因看板",
                "用 SQL+Python 做 A/B 实验显著性诊断，参与 5 次活动复盘",
                "输出运营策略建议被采纳 2 项，推动周 GMV +3.4%",
            ],
        },
        {
            "company": "美团",
            "role": "增长数据实习生",
            "start_date": "2024.12",
            "end_date": "2025.04",
            "bullets": [
                "外卖业务券面策略实验，搭建券效益模型支撑 4 场大促",
                "Tableau 看板服务于 12 人运营组，实现每周复盘自动化",
            ],
        },
    ],
    "projects": [
        {
            "name": "校园二手书匹配平台",
            "role": "主程",
            "tech_stack": ["Next.js", "FastAPI", "Postgres"],
            "bullets": [
                "全栈实现，DAU 800+",
                "实现协同过滤推荐 + 关键词搜索 + 私聊撮合",
            ],
        },
        {
            "name": "金融舆情情绪分析",
            "role": "个人项目",
            "tech_stack": ["BERT", "PyTorch"],
            "bullets": [
                "BERT 微调对 12 万条研报进行情绪三分类，F1 0.83",
                "对比 LSTM/TextCNN 基线，沉淀分析报告并开源",
            ],
        },
    ],
    "skills": {
        "technical": ["Python", "SQL", "Pandas", "NumPy"],
        "tools": ["Tableau", "PyTorch", "Excel", "Git"],
        "languages": ["English"],
    },
    "languages": ["英语六级"],
    "awards": ["ACM 校赛铜奖", "Kaggle Top 10%"],
    "candidate_summary": (
        "上海交大计算机本科应届生，目标互联网/数据分析方向，"
        "有字节、美团两段数据实习。"
    ),
    "inferred_roles": ["数据分析师", "数据科学家"],
    "inferred_tracks": ["互联网", "数据分析"],
}

DEMO_PREFERENCES_DICT: dict[str, object] = {
    "preferred_tracks": ["互联网"],
    "preferred_locations": ["上海", "杭州", "北京"],
    "preferred_roles": ["数据分析师"],
    "preferred_company_types": ["互联网"],
    "accept_relocation": True,
    "accept_internship": False,
    "campus_only": True,
    "social_ok": False,
    "preference_notes": "",
    "all_skipped": False,
}

DEMO_DIRECTIONS: list[dict[str, object]] = [
    {
        "direction": "数据分析",
        "tier": 1,
        "tier_label": "强匹配",
        "strengths": [
            "字节、美团两段对口数据分析实习，覆盖电商 + 增长两个场景",
            "SQL / Python / A/B 实验闭环具备，输出过被采纳的运营建议",
            "Tableau 看板搭建经验贴近企业实际工作流",
        ],
        "gaps": [
            "缺少更长周期（≥6 个月）实习，对长尾业务理解略浅",
        ],
        "transferable_from": [],
    },
    {
        "direction": "数据科学家",
        "tier": 2,
        "tier_label": "可迁移",
        "strengths": [
            "金融舆情 BERT 项目体现一定建模实战经验",
            "因果推断 / 实验设计基础具备，可向因果建模方向延伸",
        ],
        "gaps": [
            "无系统的机器学习实习经验，工程化建模链路较弱",
            "推荐 / 排序 / 增长建模等典型 DS 课题缺乏深度项目",
        ],
        "transferable_from": ["数据分析"],
    },
    {
        "direction": "互联网产品（数据型）",
        "tier": 2,
        "tier_label": "可迁移",
        "strengths": [
            "数据驱动决策意识较强，能从数据反推策略",
            "校园二手书项目有完整产品体感",
        ],
        "gaps": [
            "无产品实习背景，需要补充用户访谈 / 产品需求文档案例",
        ],
        "transferable_from": ["数据分析"],
    },
]

DEMO_INITIAL_CHAT_MESSAGES: list[dict[str, str]] = [
    {
        "role": "system",
        "content": (
            "你好，我是 JobRadar 的简历助手。\n\n"
            "我已经看完张三的简历，给出 8 条推荐岗位，并对前 3 条做了情报增强解读。"
            "你可以从右侧推荐卡进入任意岗位，或者继续在这里跟我对话。"
        ),
    },
    {
        "role": "assistant",
        "content": (
            "想了解某条推荐为什么排在前面？或者想试试针对某个具体岗位重写简历项目经历？"
            "直接告诉我目标公司或岗位编号即可。"
        ),
    },
    {
        "role": "assistant",
        "content": (
            "💡 **小提示**：这是一份示例会话（只读），用来展示完整能力。"
            "要体验上传简历 → 解析 → 推荐 → 改写 → 模拟面试的完整流程，请回到首页上传你自己的简历。"
        ),
    },
]


def ensure_demo_session(db: Session) -> None:
    """Idempotent: create / refresh the demo session if missing.

    Creates only the missing pieces — manual edits to existing demo rows are
    preserved. The recommendation pass uses ai_top_n=0 to skip any LLM call.
    """
    profile = ResumeProfilePayload.model_validate(DEMO_PROFILE_DICT)
    preferences = ResumePreferencePayload.model_validate(DEMO_PREFERENCES_DICT)

    session = db.query(ResumeCopilotSession).filter(
        ResumeCopilotSession.id == DEMO_SESSION_ID
    ).first()
    if not session:
        session = ResumeCopilotSession(
            id=DEMO_SESSION_ID,
            file_name="demo_resume_zhangsan.pdf",
            name="示例简历 · 张三",
            user_key="__demo__",
            status="completed",
            extracted_text=_render_extracted_text(profile),
            recommendation_status="completed",
            feedback_status="completed",
            is_guest=0,
        )
        db.add(session)
        db.flush()
    else:
        # Force the demo marker on every startup. Without this, a pre-existing
        # row at id=1 (from a deploy before this feature) would not be guarded
        # by `_assert_not_demo`.
        session.user_key = "__demo__"
        session.is_guest = 0
        if not (session.name or "").strip():
            session.name = "示例简历 · 张三"

    if not db.query(ResumeParsedProfile).filter(
        ResumeParsedProfile.session_id == DEMO_SESSION_ID
    ).first():
        db.add(ResumeParsedProfile(
            session_id=DEMO_SESSION_ID,
            profile_json=json.dumps(profile.model_dump(), ensure_ascii=False),
        ))

    if not db.query(ResumeConfirmedProfile).filter(
        ResumeConfirmedProfile.session_id == DEMO_SESSION_ID
    ).first():
        db.add(ResumeConfirmedProfile(
            session_id=DEMO_SESSION_ID,
            profile_json=json.dumps(profile.model_dump(), ensure_ascii=False),
        ))

    if not db.query(ResumePreferenceProfile).filter(
        ResumePreferenceProfile.session_id == DEMO_SESSION_ID
    ).first():
        db.add(ResumePreferenceProfile(
            session_id=DEMO_SESSION_ID,
            preferences_json=json.dumps(preferences.model_dump(), ensure_ascii=False),
            all_skipped=0,
        ))

    rec_run = db.query(ResumeRecommendationRun).filter(
        ResumeRecommendationRun.session_id == DEMO_SESSION_ID
    ).first()
    if not rec_run or not (rec_run.recommendations_json or "").strip("[]"):
        items, _used_ai, _fallback = recommend_jobs_for_profile(
            db, profile, preferences, limit=8, ai_top_n=0
        )
        recs_json = json.dumps(
            [item.model_dump() for item in items], ensure_ascii=False
        )
        if not rec_run:
            rec_run = ResumeRecommendationRun(session_id=DEMO_SESSION_ID)
            db.add(rec_run)
        rec_run.status = "completed"
        rec_run.error_message = ""
        rec_run.used_ai = 0
        rec_run.fallback_reason = ""
        rec_run.agent_trace_json = "[]"
        rec_run.recommendations_json = recs_json

    dir_run = db.query(ResumeDirectionAnalysisRun).filter(
        ResumeDirectionAnalysisRun.session_id == DEMO_SESSION_ID
    ).first()
    if not dir_run or not (dir_run.directions_json or "").strip("[]"):
        directions = [DirectionTierResult.model_validate(d) for d in DEMO_DIRECTIONS]
        if not dir_run:
            dir_run = ResumeDirectionAnalysisRun(session_id=DEMO_SESSION_ID)
            db.add(dir_run)
        dir_run.status = "completed"
        dir_run.error_message = ""
        dir_run.directions_json = json.dumps(
            [d.model_dump() for d in directions], ensure_ascii=False
        )

    has_msgs = db.query(ResumeCopilotMessage).filter(
        ResumeCopilotMessage.session_id == DEMO_SESSION_ID
    ).first()
    if not has_msgs:
        for entry in DEMO_INITIAL_CHAT_MESSAGES:
            db.add(ResumeCopilotMessage(
                session_id=DEMO_SESSION_ID,
                role=entry["role"],
                content=entry["content"],
            ))

    db.commit()


def _render_extracted_text(profile: ResumeProfilePayload) -> str:
    """A plain-text rendering of the profile, used as a placeholder for
    `extracted_text` (since the demo session has no real PDF)."""
    lines: list[str] = []
    bi = profile.basic_info or {}
    lines.append(f"姓名：{bi.get('name', '')}")
    if bi.get('city'):
        lines.append(f"所在地：{bi['city']}")
    if bi.get('email'):
        lines.append(f"邮箱：{bi['email']}")
    lines.append("")
    if profile.education:
        lines.append("【教育】")
        for e in profile.education:
            lines.append(f"  {e.school} · {e.major} · {e.degree} · {e.start_date}—{e.end_date}")
    if profile.internships:
        lines.append("")
        lines.append("【实习】")
        for i in profile.internships:
            lines.append(f"  {i.company} · {i.role} · {i.start_date}—{i.end_date}")
            for b in i.bullets:
                lines.append(f"    - {b}")
    if profile.projects:
        lines.append("")
        lines.append("【项目】")
        for p in profile.projects:
            lines.append(f"  {p.name} · {p.role}")
            if p.tech_stack:
                lines.append(f"    技术：{', '.join(p.tech_stack)}")
            for b in p.bullets:
                lines.append(f"    - {b}")
    return "\n".join(lines)
