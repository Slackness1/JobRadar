"""Phase G — 求职模式判定 (实习 / 全职 / both) + 补短板建议。

判定逻辑:
  推岗逻辑(实习 tab vs 全职 tab)主要由 **学生阶段(时点)** 决定 —— 在读生主战场是实习
  (全职校招还没向他开), 应届生主战场是全职校招, 已毕业走社招。
  **门槛强度(gate)** 决定: 应届生经历有缺口时, 是"全职照投"还是"必须并行补短板"。
  **门槛类型(gate_type)** 只改"补短板"那句话的措辞 (实习型→补对口实习; 作品型→做可量化项目),
  不改推岗逻辑本身。

门槛表来源: backend/data/_phase_g/subcat_internship_gate_v1.json (从 XHS 知识库原话定)。
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, asdict
from datetime import date
from functools import lru_cache
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[4]
GATE_FILE = BACKEND_ROOT / "data" / "_phase_g" / "subcat_internship_gate_v1.json"

# 学生阶段 canonical 值
STAGE_IN_SCHOOL = "in_school"   # 在读 (距毕业 > ~1 年)
STAGE_FRESH_GRAD = "fresh_grad"  # 应届 (今年进秋招找全职)
STAGE_GRADUATED = "graduated"   # 已毕业
STAGE_UNKNOWN = "unknown"

_STAGE_LABELS = {
    STAGE_IN_SCHOOL: "在读",
    STAGE_FRESH_GRAD: "应届",
    STAGE_GRADUATED: "已毕业",
    STAGE_UNKNOWN: "未知",
}
_STAGE_ALIASES = {
    "在读": STAGE_IN_SCHOOL, "在校": STAGE_IN_SCHOOL, "in_school": STAGE_IN_SCHOOL,
    "应届": STAGE_FRESH_GRAD, "应届生": STAGE_FRESH_GRAD, "fresh_grad": STAGE_FRESH_GRAD,
    "已毕业": STAGE_GRADUATED, "毕业": STAGE_GRADUATED, "graduated": STAGE_GRADUATED,
}

# 求职模式
MODE_INTERN_FIRST = "intern_first"
MODE_FULLTIME_FIRST = "fulltime_first"
MODE_BOTH = "both"
_MODE_LABELS = {
    MODE_INTERN_FIRST: "主推实习",
    MODE_FULLTIME_FIRST: "主推全职",
    MODE_BOTH: "实习 + 全职并行",
}
# default_tab 值域对齐前端 LeftRecommendRail 的 viewMode: platform / campus / intern
TAB_INTERN = "intern"
TAB_CAMPUS = "campus"
TAB_PLATFORM = "platform"


@lru_cache(maxsize=1)
def _gate_table() -> dict[str, dict[str, str]]:
    if not GATE_FILE.exists():
        return {}
    data = json.loads(GATE_FILE.read_text(encoding="utf-8"))
    out: dict[str, dict[str, str]] = {}
    for row in data.get("gates", []):
        sc = row.get("sub_cat")
        if sc:
            out[sc] = row
    return out


def get_gate(sub_cat: str) -> tuple[str, str, str]:
    """Return (gate, gate_type, evidence) for a sub_cat.

    未知 sub_cat 兜底为 (中, 实习型, '') —— 偏保守, 提示需要经历但不当强门槛。
    """
    row = _gate_table().get((sub_cat or "").strip())
    if not row:
        return ("中", "实习型", "")
    return (row.get("gate", "中"), row.get("gate_type", "实习型"), row.get("evidence", ""))


def normalize_stage(value: str | None) -> str:
    if not value:
        return STAGE_UNKNOWN
    return _STAGE_ALIASES.get(str(value).strip(), STAGE_UNKNOWN)


def stage_label(stage: str) -> str:
    return _STAGE_LABELS.get(stage, "未知")


def _match_bucket(track_match_kind: str | None) -> str:
    """track_match_kind (hit/null_hit/transferable/ambiguous/mismatch/no_pref) → 三档。"""
    k = (track_match_kind or "").strip()
    if k in ("hit", "null_hit"):
        return "direct"
    if k in ("transferable", "ambiguous"):
        return "transferable"
    return "none"


_YM_RE = re.compile(r"(\d{4})\s*[.\-/年]?\s*(\d{1,2})?")


def _parse_year_month(s: str) -> tuple[int, int] | None:
    """从 '2027.06' / '2026' / '2025-09' / '2027年6月' 抠 (year, month)。抠不出返 None。"""
    if not s:
        return None
    m = _YM_RE.search(s)
    if not m:
        return None
    year = int(m.group(1))
    month = int(m.group(2)) if m.group(2) else 6  # 没月份默认按毕业季 6 月
    if not (1990 <= year <= 2100 and 1 <= month <= 12):
        return None
    return (year, month)


def infer_stage_from_education(
    education: list[dict] | None, *, today: date | None = None
) -> str:
    """从最晚一段学历的毕业时间智能猜阶段。抠不出时间返 unknown (让确认页问)。

    距今 > ~13 个月毕业 → 在读; 未来 0-13 个月内毕业 → 应届; 已过 → 已毕业。
    '至今'/'Present' 且无可解析时间 → unknown。
    """
    today = today or date.today()
    latest: tuple[int, int] | None = None
    saw_ongoing = False
    for edu in education or []:
        end = str((edu or {}).get("end_date", "") or "")
        if re.search(r"至今|present|now|在读|now", end, re.IGNORECASE):
            saw_ongoing = True
            continue
        ym = _parse_year_month(end)
        if ym and (latest is None or ym > latest):
            latest = ym
    if latest is None:
        return STAGE_UNKNOWN if not saw_ongoing else STAGE_UNKNOWN
    grad = date(latest[0], latest[1], 1)
    months_to_grad = (grad.year - today.year) * 12 + (grad.month - today.month)
    if months_to_grad < 0:
        return STAGE_GRADUATED
    if months_to_grad <= 13:
        return STAGE_FRESH_GRAD
    return STAGE_IN_SCHOOL


def effective_job_stage(preferences, profile) -> str:
    """阶段判定优先级:
      1. 偏好里显式选的 job_stage (学生在确认页直接选了在读/应届/已毕业)
      2. 偏好里学生确认的 graduation_date (准确毕业时间 → 算阶段, 比简历可靠)
      3. 简历解析出的 education 毕业时间
      4. unknown (确认页问)
    """
    if preferences is not None:
        st = normalize_stage(getattr(preferences, "job_stage", "") or "")
        if st != STAGE_UNKNOWN:
            return st
        grad = str(getattr(preferences, "graduation_date", "") or "").strip()
        if grad:
            st2 = infer_stage_from_education([{"end_date": grad}])
            if st2 != STAGE_UNKNOWN:
                return st2
    edu_raw = getattr(profile, "education", None) or [] if profile is not None else []
    edu = [e.model_dump() if hasattr(e, "model_dump") else dict(e) for e in edu_raw]
    return infer_stage_from_education(edu)


@dataclass
class JobMode:
    mode: str            # intern_first | fulltime_first | both
    mode_label: str      # 主推实习 / 主推全职 / 实习 + 全职并行
    default_tab: str     # intern | campus
    advice_text: str     # 一句人话补短板/方向建议
    advice_evidence: str # 知识库原话出处 (可空)
    stage: str
    gate: str
    gate_type: str
    match: str           # direct | transferable | none

    def to_dict(self) -> dict:
        return asdict(self)


def _gap_advice(gate_type: str, sub_cat: str) -> str:
    """缺口时"去补什么"的措辞 —— 实习型补实习, 作品型做项目。"""
    if gate_type == "作品型":
        return f"{sub_cat} 看的是可展示的作品而非实习时长，建议边找机会边做一个可量化的项目/竞赛成果挂简历"
    return f"{sub_cat} 是实习强门槛赛道，建议先补一段对口实习（或争取实习转正）再冲全职"


def resolve_job_mode(
    stage: str,
    sub_cat: str,
    track_match_kind: str | None,
    *,
    gate: str | None = None,
    gate_type: str | None = None,
    gate_evidence: str | None = None,
) -> JobMode:
    """核心判定: 时点 × 门槛 × 经历 → 模式 + 默认 tab + 补短板建议。

    gate/gate_type/gate_evidence 不传时从门槛表查 sub_cat。
    """
    stage = normalize_stage(stage)
    if gate is None or gate_type is None:
        g, gt, ev = get_gate(sub_cat)
        gate = gate or g
        gate_type = gate_type or gt
        gate_evidence = gate_evidence if gate_evidence is not None else ev
    gate_evidence = gate_evidence or ""
    match = _match_bucket(track_match_kind)

    # 已毕业: 实习窗口基本关闭, 主攻全职/社招
    if stage == STAGE_GRADUATED:
        advice = "已毕业阶段校招实习窗口基本关闭，主攻全职/社招"
        if match != "direct" and gate in ("强", "中"):
            advice = "已毕业阶段实习窗口基本关闭，主攻全职/社招；经历有缺口，可用项目/作品补强"
        return JobMode(MODE_FULLTIME_FIRST, _MODE_LABELS[MODE_FULLTIME_FIRST], TAB_CAMPUS,
                       advice, gate_evidence, stage, gate, gate_type, match)

    # 在读(runway 足): 全职校招还没向他开, 主战场是实习
    if stage == STAGE_IN_SCHOOL or stage == STAGE_UNKNOWN:
        # unknown 也先按在读保守处理(主推实习), 确认页会让学生纠正
        if match == "direct":
            advice = "你已有对口经历，现阶段锁定头部目标公司的暑期/日常实习，为明年秋招留用打底"
        else:
            advice = _gap_advice(gate_type, sub_cat) + "；现阶段先从实习切入"
        return JobMode(MODE_INTERN_FIRST, _MODE_LABELS[MODE_INTERN_FIRST], TAB_INTERN,
                       advice, gate_evidence, stage, gate, gate_type, match)

    # 应届(秋招季): gate × match 决定 全职 / both
    if match == "direct":
        advice = "经历对口，主攻秋招全职岗"
        return JobMode(MODE_FULLTIME_FIRST, _MODE_LABELS[MODE_FULLTIME_FIRST], TAB_CAMPUS,
                       advice, gate_evidence, stage, gate, gate_type, match)

    # match in (transferable, none)
    if gate == "弱":
        advice = f"{sub_cat} 门槛不高，应届可直接主攻全职岗"
        return JobMode(MODE_FULLTIME_FIRST, _MODE_LABELS[MODE_FULLTIME_FIRST], TAB_CAMPUS,
                       advice, gate_evidence, stage, gate, gate_type, match)

    # gate 强/中 + 缺口 → both, 全职照投但并行补短板
    if match == "transferable":
        base = "你的经历可迁移但缺直接经历"
    else:
        base = "你目前无相关经历，全职偏难"
    if gate_type == "作品型":
        fix = "全职照投，同时做一个可量化的项目/竞赛成果补强"
    else:
        fix = "全职照投，同时并行补一段对口实习 / 争取实习转正"
    advice = f"{sub_cat} 是{gate}门槛赛道，{base}，建议{fix}"
    # both → 默认落"平台"栏: 先看目标公司全景, 校招/实习都在每家卡片下 (秋招前最实用)
    return JobMode(MODE_BOTH, _MODE_LABELS[MODE_BOTH], TAB_PLATFORM,
                   advice, gate_evidence, stage, gate, gate_type, match)
