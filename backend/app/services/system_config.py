import json
from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

from app.models import SystemConfig
from app.schemas import SpringDisplayConfigIn, SpringDisplayConfigOut


SPRING_DISPLAY_CONFIG_KEY = "spring_display_filter"
DEFAULT_SPRING_DISPLAY_CONFIG = SpringDisplayConfigOut(enabled=True, cutoff_date="2026-02-01")


def _normalize_spring_config(payload: dict) -> SpringDisplayConfigOut:
    enabled = bool(payload.get("enabled", DEFAULT_SPRING_DISPLAY_CONFIG.enabled))
    cutoff_date = str(payload.get("cutoff_date", DEFAULT_SPRING_DISPLAY_CONFIG.cutoff_date)).strip()
    if not cutoff_date:
        cutoff_date = DEFAULT_SPRING_DISPLAY_CONFIG.cutoff_date
    return SpringDisplayConfigOut(enabled=enabled, cutoff_date=cutoff_date)


def spring_cutoff_datetime(cutoff_date: str) -> datetime:
    try:
        return datetime.strptime(cutoff_date, "%Y-%m-%d")
    except ValueError:
        return datetime.strptime(DEFAULT_SPRING_DISPLAY_CONFIG.cutoff_date, "%Y-%m-%d")


def get_spring_display_cutoff(db: Session) -> Optional[datetime]:
    cfg = get_spring_display_config(db)
    if not cfg.enabled:
        return None
    return spring_cutoff_datetime(cfg.cutoff_date)


def get_spring_display_config(db: Session) -> SpringDisplayConfigOut:
    row = db.query(SystemConfig).filter(SystemConfig.key == SPRING_DISPLAY_CONFIG_KEY).first()
    if row is None:
        row = SystemConfig(
            key=SPRING_DISPLAY_CONFIG_KEY,
            value=DEFAULT_SPRING_DISPLAY_CONFIG.model_dump_json(),
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        return DEFAULT_SPRING_DISPLAY_CONFIG

    try:
        payload = json.loads(getattr(row, "value", "") or "{}")
    except json.JSONDecodeError:
        payload = {}
    cfg = _normalize_spring_config(payload)

    if payload != cfg.model_dump():
        row.value = cfg.model_dump_json()
        row.updated_at = datetime.utcnow()
        db.commit()

    return cfg


def set_spring_display_config(db: Session, data: SpringDisplayConfigIn) -> SpringDisplayConfigOut:
    row = db.query(SystemConfig).filter(SystemConfig.key == SPRING_DISPLAY_CONFIG_KEY).first()
    cfg = _normalize_spring_config(data.model_dump())

    if row is None:
        row = SystemConfig(key=SPRING_DISPLAY_CONFIG_KEY, value=cfg.model_dump_json())
        db.add(row)
    else:
        row.value = cfg.model_dump_json()
        row.updated_at = datetime.utcnow()

    db.commit()
    return cfg
