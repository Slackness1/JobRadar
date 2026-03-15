"""平台登录态持久化存储"""
from typing import Dict, Optional
from pathlib import Path


STORAGE_DIR = Path("/home/ubuntu/.openclaw/workspace-projecta/JobRadar/backend/data/browser_sessions")
STORAGE_DIR.mkdir(parents=True, exist_ok=True)


def get_storage_path(platform: str) -> Path:
    """获取指定平台的 storage 文件路径"""
    return STORAGE_DIR / f"{platform}.json"


def save_storage_state(platform: str, state: Dict) -> None:
    """保存平台的登录态"""
    path = get_storage_path(platform)
    import json
    with path.open("w") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def load_storage_state(platform: str) -> Optional[Dict]:
    """加载平台的登录态"""
    path = get_storage_path(platform)
    if not path.exists():
        return None
    import json
    with path.open("r") as f:
        return json.load(f)
    return None
