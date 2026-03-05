from sqlalchemy import create_engine, text

from app.database import Base
from app import models  # noqa: F401
from app.services.schema_patch import ensure_compatible_schema


def test_schema_patch_adds_company_recrawl_queue_table():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)

    ensure_compatible_schema(engine)

    with engine.connect() as conn:
        table_row = conn.execute(
            text("SELECT name FROM sqlite_master WHERE type='table' AND name='company_recrawl_queue'")
        ).fetchone()
        assert table_row is not None

        columns = {
            row[1]
            for row in conn.execute(text("PRAGMA table_info(company_recrawl_queue)")).fetchall()
        }

    expected = {
        "company",
        "department",
        "career_url",
        "status",
        "attempt_count",
    }
    assert expected.issubset(columns)
