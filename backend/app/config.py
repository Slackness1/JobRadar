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
    "deepseek-chat" if os.environ.get("DEEPSEEK_API_KEY") else "glm-5.0",
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
CRAWLER_LLM_FLASH_MODEL = os.environ.get("CRAWLER_LLM_FLASH_MODEL", "deepseek-chat")
CRAWLER_LLM_PRO_MODEL = os.environ.get("CRAWLER_LLM_PRO_MODEL", "deepseek-chat")
CRAWLER_LLM_TIMEOUT_SECONDS = _get_int_env("CRAWLER_LLM_TIMEOUT_SECONDS", 30)

# Feature flags — all OFF by default; flip via env
CRAWLER_LLM_ENRICH_ENABLED = os.environ.get("CRAWLER_LLM_ENRICH_ENABLED", "0") in {"1", "true", "True"}
CRAWLER_LLM_DIAGNOSE_ENABLED = os.environ.get("CRAWLER_LLM_DIAGNOSE_ENABLED", "0") in {"1", "true", "True"}
CRAWLER_LLM_DIGEST_ENABLED = os.environ.get("CRAWLER_LLM_DIGEST_ENABLED", "0") in {"1", "true", "True"}

# Backward-compatible single default config id.
TATA_CONFIG_ID = TATA_CONFIG_IDS[0]

# Path to legacy config.yaml for initial import
LEGACY_CONFIG_PATH = BASE_DIR.parent / "config.yaml"
