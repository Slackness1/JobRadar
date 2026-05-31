"""给存量 xhs_insights 回填 source_score + source_platform（纯数值，零 LLM）。幂等。"""
from __future__ import annotations
import app.config  # noqa
from app.database import SessionLocal
from app.models import XhsInsight, XhsNote
from app.services.intel.source_score import compute_source_score, platform_of


def main() -> int:
    db = SessionLocal()
    try:
        notes = {n.note_id: n for n in db.query(XhsNote).all()}
        n = 0
        for ins in db.query(XhsInsight).all():
            note = notes.get(ins.source_note_id)
            ins.source_platform = platform_of(ins.source_note_id)
            ins.source_score = compute_source_score(
                ins.source_note_id,
                liked=getattr(note, "liked_count", 0) or 0,
                comment=getattr(note, "comment_count", 0) or 0,
                signal_score=getattr(note, "signal_score", 0) or 0,
                author_name=getattr(note, "author_name", "") or "",
                marketing_text=(ins.content or "") + " " + (getattr(note, "title", "") or ""),
            )
            n += 1
            if n % 500 == 0:
                db.commit()
        db.commit()
        print(f"backfilled {n} insights")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
