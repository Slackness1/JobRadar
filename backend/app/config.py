import os
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)


def _load_local_env_file(path: Path) -> None:
    if not path.exists():
        return
    for raw_line in path.read_text(encoding='utf-8').splitlines():
        line = raw_line.strip()
        if not line or line.startswith('#') or '=' not in line:
            continue
        key, value = line.split('=', 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


if 'PYTEST_CURRENT_TEST' not in os.environ and 'pytest' not in sys.modules:
    _load_local_env_file(BASE_DIR.parent / '.env.local')
    _load_local_env_file(BASE_DIR / '.env.local')

DATABASE_URL = f"sqlite:///{DATA_DIR / 'jobradar.db'}"

# Crawl settings (from env vars)
TATA_USERNAME = os.environ.get("TATA_USERNAME", "")
TATA_PASSWORD = os.environ.get("TATA_PASSWORD", "")


def _split_csv(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def _split_int_csv(value: str) -> list[int]:
    result: list[int] = []
    for item in _split_csv(value):
        try:
            result.append(int(item))
        except ValueError:
            continue
    return result


_raw_multi_ids = os.environ.get("TATA_EXPORT_CONFIG_IDS", "")
_raw_single_id = os.environ.get("TATA_EXPORT_CONFIG_ID", "")

TATA_CONFIG_IDS = (
    _split_csv(_raw_multi_ids)
    if _raw_multi_ids
    else _split_csv(_raw_single_id) if _raw_single_id else ["687d079c70ccc5e36315f4ba"]
)

TATA_INTERNSHIP_CONFIG_IDS = set(_split_csv(os.environ.get("TATA_INTERNSHIP_CONFIG_IDS", "")))

_raw_sheet_indexes = os.environ.get("TATA_EXPORT_SHEET_INDEXES", "")
TATA_SHEET_INDEXES = _split_int_csv(_raw_sheet_indexes) if _raw_sheet_indexes else [0]

TATA_INTERNSHIP_SHEET_INDEXES = set(_split_int_csv(os.environ.get("TATA_INTERNSHIP_SHEET_INDEXES", "")))


def _get_int_env(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, str(default)))
    except ValueError:
        return default

HAITOU_MAX_PAGES = _get_int_env("HAITOU_MAX_PAGES", 16)
ALERT_STALE_DAYS = _get_int_env("ALERT_STALE_DAYS", 3)

RESUME_COPILOT_MAX_UPLOAD_MB = _get_int_env("RESUME_COPILOT_MAX_UPLOAD_MB", 10)
RESUME_COPILOT_LLM_BASE_URL = os.environ.get(
    "RESUME_COPILOT_LLM_BASE_URL",
    "https://api.deepseek.com/v1" if os.environ.get("DEEPSEEK_API_KEY") else "https://open.bigmodel.cn/api/paas/v4",
)
RESUME_COPILOT_LLM_API_KEY = os.environ.get("RESUME_COPILOT_LLM_API_KEY") or os.environ.get("DEEPSEEK_API_KEY", "")
RESUME_COPILOT_LLM_MODEL = os.environ.get(
    "RESUME_COPILOT_LLM_MODEL",
    "deepseek-v4-flash" if os.environ.get("DEEPSEEK_API_KEY") else "glm-5.0",
)
# Per-scenario model overrides — 2026-05-24 Phase 2:
#   - Interview 终评报告 / Intel 卡片 / Recommend rerank / Parser / Direction /
#     Knowledge pack / Memory extractor / Teacher entry / Plan agent: pro + reasoning high
#   - Resume rewrite chat: 回 flash + reasoning low (latency 敏感,学生改一次等 60s
#     体验崩,见 user feedback 2026-05-24)
#   - Interview orchestrator (per-turn 三路并行 fan-out): flash + low (3s budget)
RESUME_COPILOT_REWRITE_MODEL = os.environ.get(
    "RESUME_COPILOT_REWRITE_MODEL",
    RESUME_COPILOT_LLM_MODEL,  # flash (latency-critical, see 2026-05-24 plan)
)
INTERVIEW_REPORT_MODEL = os.environ.get(
    "INTERVIEW_REPORT_MODEL",
    "deepseek-v4-pro" if os.environ.get("DEEPSEEK_API_KEY") else RESUME_COPILOT_LLM_MODEL,
)
INTEL_MODEL_NAME = os.environ.get(
    "INTEL_MODEL_NAME",
    "deepseek-v4-pro" if os.environ.get("DEEPSEEK_API_KEY") else RESUME_COPILOT_LLM_MODEL,
)
# Recommendation rerank: SAIF 学生看到的 top-10 由这个调用决定,升 pro + thinking high
# (Phase 2 2026-05-24). 单次 ~$0.01 (10-20 items, output ~3-5k tokens after thinking),
# 校招期每人 ~3 次重排 ~ $0.03 / 学生,完全可接受。
RECOMMEND_RERANK_MODEL = os.environ.get(
    "RECOMMEND_RERANK_MODEL",
    "deepseek-v4-pro" if os.environ.get("DEEPSEEK_API_KEY") else RESUME_COPILOT_LLM_MODEL,
)
# Phase 2 (2026-05-24) — 时间不敏感场景统一升 pro + reasoning_effort=high。
# 这些都是 one-shot 调用(简历上传 / 方向分析 / 知识包 ingest / 学生记忆抽取 /
# 老师端解析 / PlanMode agent),学生等几十秒到一分钟换 SAIF 老师看得见的质量。
RESUME_PARSER_MODEL = os.environ.get(
    "RESUME_PARSER_MODEL",
    "deepseek-v4-pro" if os.environ.get("DEEPSEEK_API_KEY") else RESUME_COPILOT_LLM_MODEL,
)
DIRECTION_ANALYSIS_MODEL = os.environ.get(
    "DIRECTION_ANALYSIS_MODEL",
    "deepseek-v4-pro" if os.environ.get("DEEPSEEK_API_KEY") else RESUME_COPILOT_LLM_MODEL,
)
KNOWLEDGE_PACK_MODEL = os.environ.get(
    "KNOWLEDGE_PACK_MODEL",
    "deepseek-v4-pro" if os.environ.get("DEEPSEEK_API_KEY") else RESUME_COPILOT_LLM_MODEL,
)
MEMORY_EXTRACTOR_MODEL = os.environ.get(
    "MEMORY_EXTRACTOR_MODEL",
    "deepseek-v4-pro" if os.environ.get("DEEPSEEK_API_KEY") else RESUME_COPILOT_LLM_MODEL,
)
TEACHER_ENTRY_MODEL = os.environ.get(
    "TEACHER_ENTRY_MODEL",
    "deepseek-v4-pro" if os.environ.get("DEEPSEEK_API_KEY") else RESUME_COPILOT_LLM_MODEL,
)
RESUME_AGENT_MODEL = os.environ.get(
    "RESUME_AGENT_MODEL",
    "deepseek-v4-pro" if os.environ.get("DEEPSEEK_API_KEY") else RESUME_COPILOT_LLM_MODEL,
)
RESUME_COPILOT_LLM_TIMEOUT_SECONDS = _get_int_env("RESUME_COPILOT_LLM_TIMEOUT_SECONDS", 30)
RESUME_COPILOT_RERANK_TOP_N = _get_int_env("RESUME_COPILOT_RERANK_TOP_N", 20)
RESUME_COPILOT_QUICK_ENRICHMENT_ENABLED = os.environ.get("RESUME_COPILOT_QUICK_ENRICHMENT_ENABLED", "1") not in {"0", "false", "False"}
RESUME_COPILOT_QUICK_ENRICHMENT_TOP_N = _get_int_env("RESUME_COPILOT_QUICK_ENRICHMENT_TOP_N", 2)
RESUME_COPILOT_QUICK_ENRICHMENT_TIMEOUT_SECONDS = _get_int_env("RESUME_COPILOT_QUICK_ENRICHMENT_TIMEOUT_SECONDS", 18)
RESUME_COPILOT_QUICK_ENRICHMENT_QUERY_COUNT = _get_int_env("RESUME_COPILOT_QUICK_ENRICHMENT_QUERY_COUNT", 3)
RESUME_COPILOT_ALLOW_PUBLIC_SEARCH_FALLBACK = os.environ.get("RESUME_COPILOT_ALLOW_PUBLIC_SEARCH_FALLBACK", "0") in {"1", "true", "True"}
TAVILY_API_KEY = os.environ.get("TAVILY_API_KEY", "")
EXA_API_KEY = os.environ.get("EXA_API_KEY", "")
BRAVE_SEARCH_API_KEY = os.environ.get("BRAVE_SEARCH_API_KEY", "")
FIRECRAWL_API_KEY = os.environ.get("FIRECRAWL_API_KEY", "")
JINA_API_KEY = os.environ.get("JINA_API_KEY", "")

DASHSCOPE_API_KEY = os.environ.get("DASHSCOPE_API_KEY", "")
DASHSCOPE_TTS_MODEL = os.environ.get("DASHSCOPE_TTS_MODEL", "qwen3-tts-flash")
DASHSCOPE_TTS_VOICE = os.environ.get("DASHSCOPE_TTS_VOICE", "Chelsie")
DASHSCOPE_ASR_MODEL = os.environ.get("DASHSCOPE_ASR_MODEL", "paraformer-realtime-v2")

ALIYUN_ACCESS_KEY_ID = os.environ.get("ALIYUN_ACCESS_KEY_ID", "")
ALIYUN_ACCESS_KEY_SECRET = os.environ.get("ALIYUN_ACCESS_KEY_SECRET", "")
AVATAR_PROJECT_ID = os.environ.get("AVATAR_PROJECT_ID", "")
AVATAR_INSTANCE_ID = os.environ.get("AVATAR_INSTANCE_ID", "")

# Crawler LLM (cheap-and-fast for enrichment, stronger for diagnosis)
CRAWLER_LLM_BASE_URL = os.environ.get("CRAWLER_LLM_BASE_URL", RESUME_COPILOT_LLM_BASE_URL)
CRAWLER_LLM_API_KEY = os.environ.get("CRAWLER_LLM_API_KEY", RESUME_COPILOT_LLM_API_KEY)
CRAWLER_LLM_FLASH_MODEL = os.environ.get("CRAWLER_LLM_FLASH_MODEL", "deepseek-v4-flash")
CRAWLER_LLM_PRO_MODEL = os.environ.get("CRAWLER_LLM_PRO_MODEL", "deepseek-v4-pro")
CRAWLER_LLM_TIMEOUT_SECONDS = _get_int_env("CRAWLER_LLM_TIMEOUT_SECONDS", 30)

# Feature flags — all OFF by default; flip via env
CRAWLER_LLM_ENRICH_ENABLED = os.environ.get("CRAWLER_LLM_ENRICH_ENABLED", "0") in {"1", "true", "True"}
CRAWLER_LLM_DIAGNOSE_ENABLED = os.environ.get("CRAWLER_LLM_DIAGNOSE_ENABLED", "0") in {"1", "true", "True"}
CRAWLER_LLM_DIGEST_ENABLED = os.environ.get("CRAWLER_LLM_DIGEST_ENABLED", "0") in {"1", "true", "True"}

# Student KB (Phase 1: passive extraction from chat rail into long-lived
# per-student knowledge base for cross-session use by interview module).
# ON by default since main-workspace-redesign-2026-05-20 Phase 0 (P0-1) —
# memory was implemented and battle-tested but kept dark; flipping it on is
# the prerequisite for the SAIF闭环 (chat 写 → 档案展示 → 推荐/改写 读回).
STUDENT_KB_ENABLED = os.environ.get("STUDENT_KB_ENABLED", "1") in {"1", "true", "True"}
STUDENT_KB_MAX_CANDIDATES_PER_TURN = _get_int_env("STUDENT_KB_MAX_CANDIDATES_PER_TURN", 3)
STUDENT_KB_AUTO_CONFIRM_THRESHOLD = float(
    os.environ.get("STUDENT_KB_AUTO_CONFIRM_THRESHOLD", "0.92")
)

# Unified account memory (see docs/unified-memory-and-plan-mode-2026-05-13.md).
# Absorbs student_experiences + plan-embedded Evidence into a single
# `account_memory` table with category-discriminated rows. ON by default
# since Phase 0 (P0-1) — same闭环 prerequisite as STUDENT_KB_ENABLED. The two
# flags now dual-write; legacy student_experiences will be retired in a later
# PR once UI consumers fully migrate to account_memory.
UNIFIED_MEMORY_ENABLED = os.environ.get("UNIFIED_MEMORY_ENABLED", "1") in {"1", "true", "True"}

# Backward-compatible single default config id.
TATA_CONFIG_ID = TATA_CONFIG_IDS[0]

# Path to legacy config.yaml for initial import
LEGACY_CONFIG_PATH = BASE_DIR.parent / "config.yaml"

# Teacher-entry admin gate (Phase 3 — pre-launch).
# Default value works for local demo; SAIF prod must override via env.
TEACHER_ENTRY_ADMIN_TOKEN = os.environ.get(
    "TEACHER_ENTRY_ADMIN_TOKEN",
    "jobradar-admin-dev-token-change-me",
)
