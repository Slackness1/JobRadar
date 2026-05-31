import sqlite3


def test_backfill_writes_scores():
    db = "data/jobradar.db"
    c = sqlite3.connect(db).cursor()
    total = c.execute("SELECT COUNT(*) FROM xhs_insights").fetchone()[0]
    scored = c.execute("SELECT COUNT(*) FROM xhs_insights WHERE source_score IS NOT NULL").fetchone()[0]
    assert total > 0
    assert scored >= total * 0.9, f"only {scored}/{total} scored — 先跑 scripts/intel_backfill_source_score.py"
