"""Framework-independent core for the local JobRadar product."""

from jobradar_core.config import AppConfig, load_config
from jobradar_core.database import LocalDatabase
from jobradar_core.workspace import Workspace

__all__ = ["AppConfig", "LocalDatabase", "Workspace", "load_config"]

__version__ = "0.1.0a1"
