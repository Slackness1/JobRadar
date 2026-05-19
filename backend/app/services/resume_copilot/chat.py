"""
chat.py — Initialize the opening system chat message for a resume copilot session.

After direction analysis + recommendations are ready, this module writes the first
system message into `resume_copilot_messages` so the user sees a contextual greeting
when they open the chat rail.
"""
import json
import re
from typing import TYPE_CHECKING, Any, Protocol
from urllib import request as urllib_request

from sqlalchemy.orm import Session

from app.models import ResumeConfirmedProfile, ResumeCopilotMessage, ResumeCopilotSession
from app.schemas_resume_copilot import (
    ResumeProfilePayload,
    ResumeCopilotMessageOut,
    RewriteOption,
    RewriteV0V2Out,
    RewriteVersionV0,
    RewriteVersionV2,
    RewriteWarning,
    RewriteWarningSuggestion,
)
from app.services.resume_copilot.llm import build_resume_llm_client
from app.services.resume_copilot.plan import Evidence, audit_draft
from app.services.resume_copilot.tag_extractor import extract_tags

if TYPE_CHECKING:
    from app.schemas_resume_copilot import DirectionTierResult, ResumeRecommendationItem


_TIER_LABELS = {1: '强匹配', 2: '可迁移', 3: '有差距'}


def _build_opening_message(
    direction_results: 'list[DirectionTierResult]',
    recommendations: 'list[ResumeRecommendationItem]',
) -> str:
    """Build the opening system message summarising direction analysis."""
    lines: list[str] = ['你好！以下是基于你的简历和偏好生成的方向分析概览：\n']

    if direction_results:
        for r in direction_results[:5]:
            tier_label = r.tier_label or _TIER_LABELS.get(r.tier, '未知')
            strength_text = '、'.join(r.strengths[:2]) if r.strengths else '—'
            lines.append(f'- **{r.direction}**（{tier_label}）：优势 {strength_text}')
    else:
        lines.append('- 暂无方向分析结果')

    if recommendations:
        lines.append(f'\n共为你匹配了 {len(recommendations)} 个岗位，排名第一的是 **{recommendations[0].company}** 的 **{recommendations[0].job_title}**。')
    else:
        lines.append('\n暂无推荐岗位。')

    lines.append('\n如有疑问，欢迎随时向我提问！')
    return '\n'.join(lines)


def initialize_chat(
    session_id: int,
    direction_results: 'list[DirectionTierResult]',
    recommendations: 'list[ResumeRecommendationItem]',
    db: Session,
) -> None:
    """
    Write the initial system message for the chat rail into the DB.

    This is called once per session after direction analysis and recommendations
    are both ready. It is idempotent: if messages already exist for the session,
    it does nothing.
    """
    existing = db.query(ResumeCopilotMessage).filter(
        ResumeCopilotMessage.session_id == session_id
    ).first()
    if existing:
        return

    content = _build_opening_message(direction_results, recommendations)
    msg = ResumeCopilotMessage(
        session_id=session_id,
        role='system',
        content=content,
    )
    db.add(msg)
    db.commit()


# ---------------------------------------------------------------------------
# Chat LLM provider + multi-turn generation
# ---------------------------------------------------------------------------

_MAX_HISTORY = 10

_CHAT_SYSTEM_PROMPT = """\
你是一个严谨的简历优化助手。

工作流程：
1. 先通读用户的整份简历（候选人画像、全部实习、全部项目），挑出**一段**最需要改写的经历——
   优先选与用户目标方向最相关、但描述空洞 / 不够量化 / 缺少结果的那一段。
2. 针对这**同一段经历**生成两个改写方案（方案A、方案B），它们必须：
   - 指向**同一个 field_path**（是对同一处的两种替代写法，不是改两个不同地方）
   - 改写的是**整段经历的全部 bullets**，而不是其中一条
3. 两个方案应该是**不同的优化角度**，例如：
   - 方案A 突出量化结果与业务影响
   - 方案B 突出跨部门协作 / 技术深度 / 方法论
4. 严禁编造候选人没有的具体数字、项目、技术栈、公司。如信息不足以改写，`content` 里追问，并把
   `rewrite_options` 返回空数组 `[]`。
5. **严禁角色升级**:原文写"参与/协助/辅助/配合/支持/跟进",改写也用同档动词;**不允许**
   改成"主导/负责/带领/管理/牵头" — 这等于编造身份。原文里本就有"主导/负责"则可保留。
6. **严禁声明编造**:不允许加"被采纳/获奖/获 leader 表扬/排名前三"这类成果声明,除非原文已写。
7. 改写后的 bullets 行数可比原文 ±1 行，但不要清空。
8. **弱背景诚实反馈** (B8 / 2026-05-19): 当学生背景跟其目标方向有明显差距 (e.g. 普通财经
   院校 + GPA<3.5 + 只有非金融实习/营业部理财顾问/客服类经历, 但选投研 / 顶级 PE 方向),
   *不要*粉饰太平,在 `content` 字段诚实告知:
   - 当前简历相对目标方向的真实差距是什么 (e.g. "缺顶级买卖方实习" / "缺量化项目" / "缺 CFA")
   - 给出**可执行**补救路径 (e.g. "本学期争取一段中型券商行研实习" / "自学 CFA 二级到 8 月")
   - 仍然给 rewrite_options (改写现有经历最大化呈现), 但 `content` 里要说"改写之外, 你
     还需要补 X" — 否则学生只看到改写, 误以为简历"够用了"。
   不要为了避免打击学生回避真实差距 — 那只会让学生在真实投递时被实习招聘官打回来。

field_path 规则（dot-notation）：
- 实习整段：`internships.{i}.bullets`      （i 是数组下标）
- 项目整段：`projects.{i}.bullets`
- 个人简介：`candidate_summary`            （此时 original/improved 各一条字符串即可）

返回严格 JSON：
{
  "content": "面向用户的中文回复。说明你挑的是哪段经历、为什么值得改、两个方案分别走什么角度。",
  "rewrite_options": [
    {
      "option_id": "A",
      "label": "方案A — 突出量化结果",
      "section": "internships",
      "field_path": "internships.0.bullets",
      "target_title": "字节跳动 · 产品实习生",
      "original": ["原 bullet 1", "原 bullet 2", "原 bullet 3"],
      "improved": ["改写 bullet 1", "改写 bullet 2", "改写 bullet 3"],
      "rationale": "这个角度为什么对目标岗位更有说服力"
    },
    {
      "option_id": "B",
      "label": "方案B — 突出跨部门协作",
      "section": "internships",
      "field_path": "internships.0.bullets",
      "target_title": "字节跳动 · 产品实习生",
      "original": ["原 bullet 1", "原 bullet 2", "原 bullet 3"],
      "improved": ["另一种改写 1", "另一种改写 2", "另一种改写 3"],
      "rationale": "..."
    }
  ]
}

硬约束：如果输出 rewrite_options，长度必须是 2，且两个选项的 field_path、target_title、original 完全一致。
"""


class ChatLLMProvider(Protocol):
    def generate_turn(self, messages_payload: list[dict]) -> dict[str, Any]: ...


_JSON_FENCE_RE = re.compile(r"```(?:json)?\s*\n(.*?)\n```", re.DOTALL | re.IGNORECASE)


def _strip_fence(content: str) -> str:
    """LLM 有时把 JSON 包在 ```json ... ``` fence 里, 剥掉后再解析。"""
    m = _JSON_FENCE_RE.search(content)
    if m:
        return m.group(1).strip()
    return content.strip()


def _try_parse_chat_json(content: str) -> dict | None:
    """容错解析: 1. 直接 json.loads;  2. 剥 markdown fence 后 retry;
       3. 取第一个 { 到最后一个 } 间的 substring 试。失败返 None。"""
    # 1. 直接试
    try:
        return json.loads(content)
    except (json.JSONDecodeError, TypeError):
        pass
    # 2. 剥 fence
    stripped = _strip_fence(content)
    if stripped != content:
        try:
            return json.loads(stripped)
        except (json.JSONDecodeError, TypeError):
            pass
    # 3. 找 { ... } 大括号 substring (LLM 偶发前后包说明文)
    if '{' in stripped and '}' in stripped:
        start = stripped.find('{')
        end = stripped.rfind('}')
        if start < end:
            try:
                return json.loads(stripped[start:end + 1])
            except (json.JSONDecodeError, TypeError):
                pass
    return None


class OpenAICompatibleChatLLMProvider:
    def __init__(self, client=None) -> None:
        self.client = client or build_resume_llm_client()

    def _raw_call(self, messages_payload: list[dict]) -> str:
        payload = {
            'model': self.client.model,
            'response_format': {'type': 'json_object'},
            'messages': messages_payload,
        }
        req = urllib_request.Request(
            self.client.chat_completions_url,
            data=json.dumps(payload).encode('utf-8'),
            headers={
                'Authorization': f'Bearer {self.client.api_key}',
                'Content-Type': 'application/json',
            },
            method='POST',
        )
        with urllib_request.urlopen(req, timeout=self.client.timeout_seconds) as response:
            body = json.loads(response.read().decode('utf-8'))
        return body['choices'][0]['message']['content']

    def generate_turn(self, messages_payload: list[dict]) -> dict[str, Any]:
        """带 1 次 JSON-format 重试 + 文本 fallback。

        Production 触发: LLM 拒绝 fabrication 时直接输出 markdown 解释而非 JSON
        包装, JSONDecodeError 让 chat turn 整段废掉。新逻辑:
          1. 第一次调 LLM, 用容错解析
          2. 失败 → 重试一次, system 强调 "返 JSON, 不要 markdown"
          3. 仍失败 → 把 content 当作 assistant text 包装回 {content, rewrite_options:[]}
        """
        # 1. First try
        content = self._raw_call(messages_payload)
        parsed = _try_parse_chat_json(content)
        if parsed is not None:
            return parsed

        # 2. Retry 一次, system 加强 JSON 约束
        retry_payload = list(messages_payload)
        retry_payload.insert(-1, {
            'role': 'system',
            'content': (
                '⚠️ 上一次输出无法解析为 JSON。**严格要求**:\n'
                '- 整段输出必须是合法 JSON 对象 (单层 {})\n'
                '- 不要用 ```json 代码块包裹\n'
                '- 不要写"我无法..."这种纯文本回复;如果不能改写, 也要返 JSON: '
                '{"content": "(简短回复)", "rewrite_options": []}'
            ),
        })
        content2 = self._raw_call(retry_payload)
        parsed2 = _try_parse_chat_json(content2)
        if parsed2 is not None:
            return parsed2

        # 3. Fallback: 把 LLM 的 text content 当作 user-facing 回复, 空 options
        text_fallback = _strip_fence(content2 or content or '抱歉,这条暂时改不了')
        return {
            'content': text_fallback[:800],  # 避免太长污染 UI
            'rewrite_options': [],
        }


# --- Fabrication guard --------------------------------------------------------
#
# The system prompt forbids inventing numbers, but DeepSeek does it anyway
# (verified in audit: "F1 0.83" → "回测中相关系数达 0.45", "开源" →
# "GitHub 200+ stars"). The guard extracts every numeric token from the user's
# entire profile and flags any number in the rewrite that has no anchor.
#
# We intentionally do NOT auto-strip — stripping might leave bullets ungrammatical
# and the user could miss the issue silently. Surfacing a warning lets them
# decide whether to apply, edit, or regenerate.

_NUMERIC_PATTERN = re.compile(r'\d+(?:\.\d+)?%?')


def _extract_numbers(text: str) -> set[str]:
    return set(_NUMERIC_PATTERN.findall(text or ''))


def _profile_anchor_numbers(profile_dict: dict) -> set[str]:
    chunks: list[str] = []
    chunks.append(str(profile_dict.get('candidate_summary', '') or ''))
    for ed in profile_dict.get('education', []) or []:
        if not isinstance(ed, dict):
            continue
        chunks.extend(str(ed.get(k, '') or '') for k in ('school', 'degree', 'major', 'start_date', 'end_date'))
        chunks.extend(str(h or '') for h in (ed.get('highlights') or []))
    for it in profile_dict.get('internships', []) or []:
        if not isinstance(it, dict):
            continue
        chunks.extend(str(it.get(k, '') or '') for k in ('company', 'role', 'start_date', 'end_date'))
        chunks.extend(str(b or '') for b in (it.get('bullets') or []))
    for pr in profile_dict.get('projects', []) or []:
        if not isinstance(pr, dict):
            continue
        chunks.extend(str(pr.get(k, '') or '') for k in ('name', 'role'))
        chunks.extend(str(b or '') for b in (pr.get('bullets') or []))
        chunks.extend(str(t or '') for t in (pr.get('tech_stack') or []))
    return _extract_numbers(' '.join(chunks))


def _detect_fabricated_numbers(improved: list[str], anchor: set[str]) -> set[str]:
    found: set[str] = set()
    for bullet in improved or []:
        found.update(_extract_numbers(bullet))
    return found - anchor


def _annotate_fabrications(options: list[RewriteOption], profile_dict: dict) -> None:
    anchor = _profile_anchor_numbers(profile_dict)
    if not anchor:
        return
    for opt in options:
        fabricated = _detect_fabricated_numbers(opt.improved, anchor)
        if not fabricated:
            continue
        nums = '、'.join(sorted(fabricated))
        opt.warning = (
            f'此方案引入了原简历中没有的数字：{nums}。这些可能是 AI 估测的，应用前请核实是否符合你的真实情况。'
        )


def _add_evidence(evidences: list[Evidence], text: str) -> None:
    t = str(text or '').strip()
    if not t:
        return
    evidences.append(Evidence(
        source='parsed_resume',
        text=t,
        tags=extract_tags(t),
    ))


def _add_global_evidence(evidences: list[Evidence], profile_dict: dict) -> None:
    """全局 evidence — 不限于某段:summary / education / skills / awards / languages。

    这些 trace 跨任何段改写都成立, 不算"跨段编造"。
    """
    _add_evidence(evidences, profile_dict.get('candidate_summary', ''))
    for edu in profile_dict.get('education', []) or []:
        if isinstance(edu, dict):
            for k in ('school', 'degree', 'major'):
                _add_evidence(evidences, edu.get(k, ''))
            for h in (edu.get('highlights') or []):
                _add_evidence(evidences, h)
    skills = profile_dict.get('skills', {}) or {}
    if isinstance(skills, dict):
        for k in ('technical', 'tools', 'languages'):
            for s in (skills.get(k) or []):
                _add_evidence(evidences, s)
    for award in (profile_dict.get('awards') or []):
        _add_evidence(evidences, award)
    for lang in (profile_dict.get('languages') or []):
        _add_evidence(evidences, lang)


def _add_internship_evidence(evidences: list[Evidence], intern: dict) -> None:
    if not isinstance(intern, dict):
        return
    for k in ('company', 'role'):
        _add_evidence(evidences, intern.get(k, ''))
    for b in (intern.get('bullets') or []):
        _add_evidence(evidences, b)


def _add_project_evidence(evidences: list[Evidence], proj: dict) -> None:
    if not isinstance(proj, dict):
        return
    for k in ('name', 'role'):
        _add_evidence(evidences, proj.get(k, ''))
    for t in (proj.get('tech_stack') or []):
        _add_evidence(evidences, t)
    for b in (proj.get('bullets') or []):
        _add_evidence(evidences, b)


def _parse_field_scope(field_path: str) -> tuple[str | None, int | None]:
    """field_path → (section, index) — 决定 audit 用哪一段 evidence。

    例:
      - 'internships.0.bullets' → ('internships', 0)
      - 'projects.2.bullets'   → ('projects', 2)
      - 'candidate_summary'    → (None, None)   全局, 没 sub-section
      - 'education.1.highlights' → ('education', 1)
    """
    if not field_path:
        return (None, None)
    parts = field_path.split('.')
    if len(parts) < 2:
        return (None, None)
    section = parts[0]
    if section not in ('internships', 'projects', 'education'):
        return (None, None)
    try:
        index = int(parts[1])
    except (ValueError, IndexError):
        return (None, None)
    return (section, index)


def _profile_to_evidence_list(profile_dict: dict, field_path: str = '') -> list[Evidence]:
    """profile → Evidence 列表, 可选按 field_path 做 per-section 隔离。

    B6 (2026-05-19) per-internship 隔离:
      - 给定 field_path='internships.0.bullets', 只取 internships[0] + 全局 evidence
        (candidate_summary / education / skills / awards),其它 internships 跟 projects
        bullet 不算入,防止 LLM 把 BCG 段的"客户访谈" 错挂到 McKinsey 段。
      - field_path 空或解析不到 section → 取整份 evidence (向后兼容)。
    """
    evidences: list[Evidence] = []
    section, index = _parse_field_scope(field_path)

    # 全局 evidence (始终包含)
    _add_global_evidence(evidences, profile_dict)

    if section is None:
        # 没 field_path scope, 全份 (旧行为)
        for intern in profile_dict.get('internships', []) or []:
            _add_internship_evidence(evidences, intern)
        for proj in profile_dict.get('projects', []) or []:
            _add_project_evidence(evidences, proj)
    elif section == 'internships':
        # 只取该段 internship; projects 完全不算
        interns = profile_dict.get('internships', []) or []
        if 0 <= index < len(interns):
            _add_internship_evidence(evidences, interns[index])
    elif section == 'projects':
        # 只取该段 project; internships 完全不算
        projs = profile_dict.get('projects', []) or []
        if 0 <= index < len(projs):
            _add_project_evidence(evidences, projs[index])
    # section='education' 走全局分支已涵盖 (education 已在 _add_global_evidence)

    return evidences


_SEVERE_RISK_KINDS = {
    'overclaim',
    'leadership_unverified',
    'tech_unverified',
    'vague_quantification',         # B5 (2026-05-19): "千万级"/"日均约" 看似量化实未验证
    'evidence_scope_unverified',    # B5: "引用 N 次专家访谈纪要" 调研规模虚构
}
_WARN_RISK_KINDS = {'missing_metric', 'vague_verb'}


_LEADERSHIP_DRAFT_TOKEN_RE = re.compile(r"draft uses '(.+?)'")
_TECH_DRAFT_TOKEN_RE = re.compile(r"draft mentions '(.+?)'")


def _filter_audit_risks_against_original(risk_flags, original_text: str):
    """chat.py 场景:对比 improved vs original,过滤掉 original 已含的 token。

    plan-mode 假设用户从空白构建 bullet,所有 leadership/tech token 都要 evidence 支持;
    chat.py 是 rewrite **已经存在**的 bullet,如果 original 里就有 "主导/负责",改写保留
    它不算新夸大。这层过滤只对 leadership_unverified / tech_unverified 生效,其它维度
    (overclaim 数字 / missing_metric / vague_verb) 仍走原 audit_draft。
    """
    if not original_text:
        return risk_flags
    out = []
    for f in risk_flags:
        if f.kind == 'leadership_unverified':
            m = _LEADERSHIP_DRAFT_TOKEN_RE.search(f.detail)
            if m and m.group(1) in original_text:
                continue
        elif f.kind == 'tech_unverified':
            m = _TECH_DRAFT_TOKEN_RE.search(f.detail)
            if m and m.group(1) in original_text:
                continue
        out.append(f)
    return out


def _audit_rewrite_options(options: list[RewriteOption], profile_dict: dict) -> None:
    """对每个 RewriteOption 跑 5-维 audit_draft + 填 audit_risks + warning_severity。

    选项 B (半硬警告): severe risk 红底警示,但 apply 按钮仍可点。

    chat.py 场景特化:
      - audit_draft 是 plan-mode 设计的"从空白起"严格模式
      - 对 rewrite 场景,只 flag improved 引入但 original 没有的 leadership/tech token
        (差量检查),否则只是把已有 token 保留也会被误判
      - B6 (2026-05-19): per-section 隔离 — audit 该 option 的 field_path 对应段
        evidence + 全局; 防止跨段编造 (e.g. McKinsey 段的"客户访谈"挂到 BCG 段)
    """
    for opt in options:
        # B6: 按 option 的 field_path 取 scoped evidence
        evidence = _profile_to_evidence_list(profile_dict, opt.field_path or '')
        if not evidence:
            continue

        draft_text = '\n'.join(opt.improved or [])
        if not draft_text.strip():
            continue
        risk_flags = audit_draft(draft_text, evidence)
        original_text = '\n'.join(opt.original or [])
        risk_flags = _filter_audit_risks_against_original(risk_flags, original_text)
        if not risk_flags:
            continue

        opt.audit_risks = [
            {'kind': f.kind, 'detail': f.detail, 'blocking': f.blocking}
            for f in risk_flags
        ]
        # severity: 任一 severe kind → severe;任一 warn kind 且无 severe → warn
        kinds = {f.kind for f in risk_flags}
        if kinds & _SEVERE_RISK_KINDS:
            opt.warning_severity = 'severe'
        elif kinds & _WARN_RISK_KINDS:
            opt.warning_severity = 'warn'

        # 把 audit detail 汇成人话 warning (跟数字 fabrication 的 warning 合并 / 覆盖)
        human = _format_audit_risks(risk_flags)
        if human:
            # 不覆盖已有数字 fabrication warning,但前缀加上
            opt.warning = (opt.warning + ' ' + human).strip() if opt.warning else human


_HUMAN_KIND_LABEL = {
    'overclaim': '夸大或编造数字',
    'leadership_unverified': '声称的领导/主导角色无证据',
    'tech_unverified': '提及的技术栈/工具简历里没有',
    'missing_metric': '缺量化数据,建议补一个数字',
    'vague_verb': '动词太虚 (e.g. "参与/负责"),建议改具体动作',
    'vague_quantification': '模糊量级词 (e.g. "千万级 / 日均约"),看似量化实则没法验证',
    'evidence_scope_unverified': '虚构调研规模 (e.g. "引用 N 次专家访谈纪要"),原经历无证据',
}


def _format_audit_risks(risk_flags) -> str:
    if not risk_flags:
        return ''
    severe_msgs = [
        f"⚠️ {_HUMAN_KIND_LABEL.get(f.kind, f.kind)}:{f.detail}"
        for f in risk_flags if f.blocking
    ]
    warn_msgs = [
        f"💡 {_HUMAN_KIND_LABEL.get(f.kind, f.kind)}"
        for f in risk_flags if not f.blocking
    ]
    return ' / '.join(severe_msgs + warn_msgs)


def _load_profile_dict(session_id: int, db: Session) -> dict:
    confirmed = (
        db.query(ResumeConfirmedProfile)
        .filter(ResumeConfirmedProfile.session_id == session_id)
        .first()
    )
    if not confirmed:
        return {}
    return json.loads(str(confirmed.profile_json or '{}'))


def generate_chat_turn(
    session_id: int,
    user_content: str,
    db: Session,
    provider: 'ChatLLMProvider | None' = None,
) -> ResumeCopilotMessageOut:
    _provider = provider or OpenAICompatibleChatLLMProvider()

    history = (
        db.query(ResumeCopilotMessage)
        .filter(ResumeCopilotMessage.session_id == session_id)
        .order_by(ResumeCopilotMessage.created_at)
        .limit(_MAX_HISTORY)
        .all()
    )

    profile_dict = _load_profile_dict(session_id, db)

    # Pull preferences once — providers receive them via ContextRequest.preferences.
    pref_dict: dict = {}
    try:
        from app.models import ResumePreferenceProfile
        pref_row = (
            db.query(ResumePreferenceProfile)
            .filter(ResumePreferenceProfile.session_id == session_id)
            .first()
        )
        if pref_row:
            pref_dict = json.loads(str(pref_row.preferences_json or '{}'))
    except Exception:
        pref_dict = {}

    system_content = _CHAT_SYSTEM_PROMPT + '\n\n候选人简历摘要：\n' + json.dumps(
        {
            'internships': profile_dict.get('internships', []),
            'projects': profile_dict.get('projects', []),
            'candidate_summary': profile_dict.get('candidate_summary', ''),
        },
        ensure_ascii=False,
    )

    # Pluggable knowledge sources (podcast / future memory / future tencent…).
    try:
        from app.services.llm_context import ContextRequest, fetch_blocks
        from app.services.llm_context.base import PURPOSE_CHAT
        extras = fetch_blocks(ContextRequest(
            purpose=PURPOSE_CHAT,
            db=db,
            user_question=user_content,
            profile=profile_dict,
            preferences=pref_dict,
        ))
        if extras:
            system_content += '\n\n' + '\n\n'.join(extras)
    except Exception:
        pass

    messages_payload: list[dict] = [{'role': 'system', 'content': system_content}]
    for msg in history:
        messages_payload.append({
            'role': 'user' if msg.role == 'user' else 'assistant',
            'content': msg.content,
        })
    messages_payload.append({'role': 'user', 'content': user_content})

    user_msg = ResumeCopilotMessage(
        session_id=session_id,
        role='user',
        content=user_content,
        rewrite_options_json=None,
        applied_option_id=None,
    )
    db.add(user_msg)
    db.commit()

    raw: Any = _provider.generate_turn(messages_payload)
    if not isinstance(raw, dict):
        # Defensive: LLM contract is JSON object, but a malformed response
        # must not crash the chat turn. Fall back to a generic apology.
        raw = {'content': '抱歉，我刚刚没能理解，请再说一次？', 'rewrite_options': []}
    content = str(raw.get('content', ''))
    raw_options = raw.get('rewrite_options') or []
    options: list[RewriteOption] = []
    for item in raw_options:
        try:
            options.append(RewriteOption.model_validate(item))
        except Exception:
            pass

    if options:
        _annotate_fabrications(options, profile_dict)
        _audit_rewrite_options(options, profile_dict)

    assistant_msg = ResumeCopilotMessage(
        session_id=session_id,
        role='assistant',
        content=content,
        rewrite_options_json=json.dumps([o.model_dump() for o in options]) if options else None,
        applied_option_id=None,
    )
    db.add(assistant_msg)
    db.commit()
    db.refresh(assistant_msg)

    return ResumeCopilotMessageOut(
        id=int(assistant_msg.id),
        role='assistant',
        content=content,
        rewrite_options=options or None,
        applied_option_id=None,
        created_at=assistant_msg.created_at,
    )


def _coerce_value_to_target_type(current_value: Any, new_value: Any) -> Any:
    """如果目标位置当前是 str 而新值是 list (或反之), 做安全 coerce。

    Production 触发: LLM 改写 candidate_summary 字段 (str 类型) 时 improved 永远返
    list[str], _traverse_and_set 不做 coerce 直接灌 list → schema 后 validate 崩。
    """
    # 现位置是 str, 新值是 list → join 成 str
    if isinstance(current_value, str) and isinstance(new_value, list):
        cleaned = [str(v).strip() for v in new_value if v and str(v).strip()]
        if not cleaned:
            return ''
        # 单元素直接用; 多元素用句号连接
        if len(cleaned) == 1:
            return cleaned[0]
        joined = '。'.join(cleaned).strip()
        if joined and not joined.endswith(('。', '.', '！', '?', '？', '!')):
            joined += '。'
        return joined
    # 现位置是 list, 新值是 str → 包装成 single-element list
    if isinstance(current_value, list) and isinstance(new_value, str):
        return [new_value] if new_value.strip() else []
    return new_value


def _traverse_and_set(data: dict, path: str, value: Any) -> None:
    parts = path.split('.')
    current: Any = data
    for part in parts[:-1]:
        try:
            if isinstance(current, list):
                current = current[int(part)]
            else:
                current = current[part]
        except (KeyError, IndexError, ValueError) as exc:
            raise ValueError(f'field_path traversal failed at "{part}": {exc}') from exc
    last = parts[-1]
    try:
        if isinstance(current, list):
            idx = int(last)
            value = _coerce_value_to_target_type(current[idx], value)
            current[idx] = value
        else:
            # dict 路径: 看 last key 是否存在 + 当前类型, 做 type-aware coerce
            existing = current.get(last) if isinstance(current, dict) else None
            value = _coerce_value_to_target_type(existing, value)
            current[last] = value
    except (IndexError, ValueError, KeyError) as exc:
        raise ValueError(f'field_path assignment failed at "{last}": {exc}') from exc


def apply_rewrite(
    session_id: int,
    message_id: int,
    option_id: str,
    db: Session,
) -> ResumeProfilePayload:
    msg = (
        db.query(ResumeCopilotMessage)
        .filter(
            ResumeCopilotMessage.id == message_id,
            ResumeCopilotMessage.session_id == session_id,
        )
        .first()
    )
    if not msg:
        raise ValueError(f'Message {message_id} not found for session {session_id}')

    options_raw = json.loads(str(msg.rewrite_options_json or '[]'))
    option = next((o for o in options_raw if o.get('option_id') == option_id), None)
    if not option:
        raise ValueError(f'Option {option_id} not found in message {message_id}')

    confirmed = (
        db.query(ResumeConfirmedProfile)
        .filter(ResumeConfirmedProfile.session_id == session_id)
        .first()
    )
    if not confirmed:
        raise ValueError(f'Confirmed profile for session {session_id} not found')

    profile_dict = json.loads(str(confirmed.profile_json or '{}'))
    _traverse_and_set(profile_dict, option['field_path'], option['improved'])

    confirmed.profile_json = json.dumps(profile_dict)
    msg.applied_option_id = option_id
    db.commit()

    return ResumeProfilePayload.model_validate(profile_dict)


# ─── Rewrite v0/v2 — thesis-aware (Phase 1 BE-2, C-1 简 + C-5) ────────────────
#
# 新 rewrite pipeline (砍 v1 STAR — 见 docs/main-workspace-redesign-2026-05-20.md
# §0.6):
#
#   bullet_text + JD + account_memory(experience + skill_claim, top-3)
#       → LLM thesis-aware rewrite
#       → v2.text
#       → _detect_fabricated_numbers → warnings (3 suggestion_options)
#       → RewriteV0V2Out
#
# v0 = echo 原文 (无改写)
# v2 = LLM 改, 必须用 memory_blocks 里的细节 + 注入学生独立判断 / 非共识 view
#
# memory 为空时不调 LLM —— 直接返 needs_plan_mode=True, 引导学生先去 plan-mode
# 跟 AI 加厚这段经历再回来。


_REWRITE_V2_SYSTEM_PROMPT = """\
你是一位资深的金融行业简历改写顾问 (服务 SAIF 高金 MF / MBA 学生)。

任务: 接收一条学生简历 bullet + 目标岗位 JD + 学生自己讲过的真实经历细节
(`student_memory`), 输出一版 **thesis-aware** 改写。

什么叫 thesis-aware:
1. **基于 student_memory 注入真实细节** — 不能只是把原 bullet 词换一下,要把
   memory 里的具体动作 / 数据 / 结果 / 方法编入改写。
2. **加学生独立判断 / 非共识 view** — 不要写"按要求完成 X","参与了 Y" 这种
   被动陈述。要呈现 "我看到了什么 / 我是怎么判断的 / 我得出的非共识结论"。
   例:
     - 烂版: "参与了行研项目, 跟踪 5 只半导体股票"
     - thesis 版: "跟踪 5 只半导体股票时, 发现头部 IDM 在车规 MCU 切换上的
       lead time 被市场低估, 据此给 leader 提出反共识 buy 建议"
3. **行业洞察** — 体现学生对所投赛道有深度理解 (e.g. 知道买方研究跟卖方研究
   的差别 / 知道一级和二级的视角差 / 知道公募研究员的报告流程)。

硬约束 (违反即作废):
- **绝不编造原 bullet + student_memory 都没有的具体数字 / 公司 / 工具**。
  系统会再跑一遍数字检测; 你输出的数字必须能在 anchor 里找得到。
- **绝不角色升级** — 原文用"参与/协助/配合" 改写也用同档动词, 不允许变成
  "主导/负责/带领"。
- **绝不声明编造** — 不允许加"被采纳/获奖/leader 表扬"这类成果, 除非原文已写。
- 字数控制在原 bullet ± 30%。

输出严格 JSON:
{
  "text": "thesis-aware 改写后的 bullet (一行)",
  "rationale": "为什么这样改 (1-2 句, 解释你用了 memory 哪条细节 + 注入了什么 view)"
}
"""


_REWRITE_V2_NO_MEMORY_MESSAGE = (
    "需要更多经历细节,建议用 plan-mode 跟 AI 聊聊这段经历"
)


def _detect_fabricated_numbers_in_text(text: str, anchor: set[str]) -> set[str]:
    """Single-string variant of ``_detect_fabricated_numbers`` (which takes a
    list[str]). Used by the v0/v2 path where the v2 output is one bullet."""
    return _extract_numbers(text or '') - anchor


_FABRICATED_NUMBER_SUGGESTIONS: list[dict[str, str]] = [
    {"action": "fill_real", "label": "填实数"},
    {"action": "delete_number", "label": "删数"},
    {"action": "vague", "label": "接受模糊版本"},
]


def _build_fabrication_warnings(text: str, profile_dict: dict) -> list[RewriteWarning]:
    """Run the v0/v2 v2-text through fabrication detector and return a structured
    RewriteWarning list. Empty list = no fabrications detected.

    Each fabricated number becomes ONE warning with the canonical 3-option
    suggestion set (填实数 / 删数 / 接受模糊版本). The set is fixed by C-5
    spec — don't trim it; the UI renders the buttons directly from it."""
    anchor = _profile_anchor_numbers(profile_dict)
    if not anchor:
        # No anchor numbers anywhere in the profile — can't decide if v2 numbers
        # are fabricated. Skip the warning (false-positive risk too high).
        return []
    fabricated = _detect_fabricated_numbers_in_text(text, anchor)
    if not fabricated:
        return []
    warnings: list[RewriteWarning] = []
    for num in sorted(fabricated):
        warnings.append(RewriteWarning(
            type='fabricated_number',
            number=num,
            suggestion_options=[
                RewriteWarningSuggestion(action=s['action'], label=s['label'])
                for s in _FABRICATED_NUMBER_SUGGESTIONS
            ],
            detail=f"改写引入了原简历里没有的数字 {num},请核实或选择处理方式。",
        ))
    return warnings


def _format_memory_block(memory_entries: list[dict]) -> str:
    """Render the top-k memory entries as a system-prompt block.

    Style matches StudentMemoryProvider so the LLM sees a familiar layout.
    Each entry: ``- [category] summary (raw_excerpt 摘要)``.
    """
    if not memory_entries:
        return ''
    lines: list[str] = [
        '[student_memory · 学生自己讲过的经历细节 — 你必须基于这些事实改写, 不要凭空发挥]',
    ]
    for entry in memory_entries:
        cat = str(entry.get('category', '') or '')
        summary = str(entry.get('summary', '') or '').strip()
        excerpt = str(entry.get('raw_excerpt', '') or '').strip()
        line = f"  - [{cat}] {summary}"
        if excerpt and excerpt != summary:
            # Trim excerpt so prompt stays compact.
            line += f"\n      原话: {excerpt[:200]}"
        lines.append(line)
    return '\n'.join(lines)


def _load_user_key_for_session(session_id: int, db: Session) -> str:
    row = (
        db.query(ResumeCopilotSession)
        .filter(ResumeCopilotSession.id == session_id)
        .first()
    )
    return str(getattr(row, 'user_key', '') or '') if row else ''


class V2RewriteLLMProvider(Protocol):
    def generate_v2(self, messages_payload: list[dict]) -> dict[str, Any]: ...


class OpenAICompatibleV2RewriteLLMProvider:
    """Single-call LLM provider for the v0/v2 thesis rewrite path.

    Distinct from ``OpenAICompatibleChatLLMProvider`` because the v2 rewrite
    output schema is much smaller (``{text, rationale}``) and we don't need
    the multi-turn / rewrite_options pipeline.
    """

    def __init__(self, client=None) -> None:
        self.client = client or build_resume_llm_client()

    def generate_v2(self, messages_payload: list[dict]) -> dict[str, Any]:
        payload = {
            'model': self.client.model,
            'response_format': {'type': 'json_object'},
            'messages': messages_payload,
        }
        req = urllib_request.Request(
            self.client.chat_completions_url,
            data=json.dumps(payload).encode('utf-8'),
            headers={
                'Authorization': f'Bearer {self.client.api_key}',
                'Content-Type': 'application/json',
            },
            method='POST',
        )
        with urllib_request.urlopen(req, timeout=self.client.timeout_seconds) as response:
            body = json.loads(response.read().decode('utf-8'))
        content = body['choices'][0]['message']['content']
        parsed = _try_parse_chat_json(content)
        if parsed is None:
            # Defensive fallback: keep the original LLM text so the caller at
            # least has something to show — don't drop the whole turn.
            return {'text': _strip_fence(content)[:800], 'rationale': ''}
        return parsed


def propose_rewrite_v0_v2(
    session_id: int,
    bullet_text: str,
    field_path: str,
    db: Session,
    *,
    target_job_description: str = '',
    target_title: str = '',
    section: str = '',
    provider: 'V2RewriteLLMProvider | None' = None,
    user_key_override: str | None = None,
) -> RewriteV0V2Out:
    """Generate the v0/v2 rewrite for one resume bullet.

    Pipeline:
      1. Echo the bullet → ``v0``.
      2. Look up the session's ``user_key``; fetch top-3 relevant ``experience``
         + ``skill_claim`` rows from ``account_memory`` via
         ``relevant_memory_for_bullet``.
      3. **Empty memory → short-circuit**: return ``v2.needs_plan_mode=True``
         with the canonical guidance message. The LLM is NOT called.
      4. Otherwise call the v2 LLM with: JD + bullet + memory block.
      5. Run ``_build_fabrication_warnings`` against ``v2.text``; attach warnings
         (with the 3 canonical suggestion_options) but DO NOT strip the number.

    The fabrication warning is a CLAUDE.md red line — callers must not suppress
    it. Apply path lives in FE / future endpoint.
    """
    cleaned_bullet = (bullet_text or '').strip()
    v0 = RewriteVersionV0(text=cleaned_bullet)

    user_key = (
        user_key_override
        if user_key_override is not None
        else _load_user_key_for_session(session_id, db)
    )
    profile_dict = _load_profile_dict(session_id, db)

    # Step 2: fetch relevant memory
    from app.services.memory.api_helpers import relevant_memory_for_bullet
    memory_entries = relevant_memory_for_bullet(
        db, user_key=user_key, bullet_text=cleaned_bullet, k=3,
    )

    # Step 3: empty memory → guide to plan-mode, don't burn LLM tokens.
    if not memory_entries:
        return RewriteV0V2Out(
            field_path=field_path,
            section=section,
            target_title=target_title,
            v0=v0,
            v2=RewriteVersionV2(
                text=_REWRITE_V2_NO_MEMORY_MESSAGE,
                needs_plan_mode=True,
                warnings=[],
            ),
            rationale='',
            memory_refs=[],
        )

    # Step 4: call LLM
    _provider = provider or OpenAICompatibleV2RewriteLLMProvider()
    memory_block = _format_memory_block(memory_entries)

    user_payload = {
        'target_job_description': target_job_description or '',
        'original_bullet': cleaned_bullet,
        'field_path': field_path,
    }

    system_content = _REWRITE_V2_SYSTEM_PROMPT + '\n\n' + memory_block
    messages_payload: list[dict] = [
        {'role': 'system', 'content': system_content},
        {'role': 'user', 'content': json.dumps(user_payload, ensure_ascii=False)},
    ]

    raw: Any = _provider.generate_v2(messages_payload)
    if not isinstance(raw, dict):
        raw = {'text': cleaned_bullet, 'rationale': ''}
    v2_text = str(raw.get('text', '') or '').strip() or cleaned_bullet
    rationale = str(raw.get('rationale', '') or '').strip()

    # Step 5: fabrication warnings — DO NOT strip, surface them.
    warnings = _build_fabrication_warnings(v2_text, profile_dict)

    return RewriteV0V2Out(
        field_path=field_path,
        section=section,
        target_title=target_title,
        v0=v0,
        v2=RewriteVersionV2(
            text=v2_text,
            needs_plan_mode=False,
            warnings=warnings,
        ),
        rationale=rationale,
        memory_refs=[int(e.get('id', 0)) for e in memory_entries if e.get('id')],
    )
