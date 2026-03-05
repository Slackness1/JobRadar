from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models import Keyword, KeywordGroup, Track
from app.schemas import TrackImportGroupIn, TrackImportIn, TrackImportTrackIn
from app.services.track_importer import import_tracks_json_full_replace


def _new_db_session():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    TestingSessionLocal = sessionmaker(bind=engine)
    Base.metadata.create_all(bind=engine)
    return TestingSessionLocal()


def test_import_tracks_full_replace():
    db = _new_db_session()
    try:
        old_track = Track(key="old_track", name="Old", weight=1.0, min_score=10, sort_order=0)
        db.add(old_track)
        db.flush()
        old_group = KeywordGroup(track_id=old_track.id, group_name="Old Group", sort_order=0)
        db.add(old_group)
        db.flush()
        db.add(Keyword(group_id=old_group.id, word="legacy"))
        db.commit()

        payload = TrackImportIn(
            tracks=[
                TrackImportTrackIn(
                    key="data_analysis",
                    name="数据分析",
                    weight=1.2,
                    min_score=12,
                    sort_order=0,
                    groups=[
                        TrackImportGroupIn(
                            group_name="核心技能",
                            sort_order=0,
                            keywords=["Python", "SQL"],
                        )
                    ],
                )
            ]
        )

        result = import_tracks_json_full_replace(db, payload)

        assert result.replaced is True
        assert result.track_count == 1
        assert db.query(Track).count() == 1
        assert db.query(Track).first().key == "data_analysis"
        assert db.query(Keyword).count() == 2
    finally:
        db.close()
