from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.schemas import SpringDisplayConfigIn
from app.services.system_config import get_spring_display_config, set_spring_display_config


def _new_db_session():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    TestingSessionLocal = sessionmaker(bind=engine)
    Base.metadata.create_all(bind=engine)
    return TestingSessionLocal()


def test_default_spring_display_config_is_enabled():
    db = _new_db_session()
    try:
        cfg = get_spring_display_config(db)
        assert cfg.enabled is True
        assert cfg.cutoff_date == "2026-02-01"
    finally:
        db.close()


def test_update_spring_display_config():
    db = _new_db_session()
    try:
        set_spring_display_config(
            db,
            SpringDisplayConfigIn(enabled=False, cutoff_date="2026-02-10"),
        )
        cfg = get_spring_display_config(db)
        assert cfg.enabled is False
        assert cfg.cutoff_date == "2026-02-10"
    finally:
        db.close()
