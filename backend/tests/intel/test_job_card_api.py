import sqlite3

from fastapi.testclient import TestClient

from app.main import app


def test_card_endpoint_returns_positioning():
    with sqlite3.connect("data/jobradar.db") as conn:
        row = conn.cursor().execute(
            "SELECT id FROM jobs WHERE sub_category IS NOT NULL LIMIT 1"
        ).fetchone()
    assert row is not None, "No job with sub_category found in DB — seed data needed"
    jid = row[0]

    client = TestClient(app)
    r = client.get(f"/api/job-intel/card?job_id={jid}")
    assert r.status_code == 200
    body = r.json()
    assert body["positioning"]["one_liner"]
    assert set(body["intel"].keys()) == {"threshold", "compensation", "outlook"}
