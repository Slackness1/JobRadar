from typing import Set

from app.models import Keyword, KeywordGroup, Track
from app.schemas import TrackImportIn, TrackImportOut


def _validate_payload(payload: TrackImportIn) -> None:
    if not payload.tracks:
        raise ValueError("tracks cannot be empty")

    seen_track_keys: Set[str] = set()
    for track in payload.tracks:
        key = track.key.strip()
        if not key:
            raise ValueError("track key cannot be empty")
        if key in seen_track_keys:
            raise ValueError(f"duplicate track key: {key}")
        seen_track_keys.add(key)

        seen_group_names: Set[str] = set()
        for group in track.groups:
            group_name = group.group_name.strip()
            if not group_name:
                raise ValueError(f"empty group name in track: {key}")
            if group_name in seen_group_names:
                raise ValueError(f"duplicate group name in track {key}: {group_name}")
            seen_group_names.add(group_name)


def import_tracks_json_full_replace(db, payload: TrackImportIn) -> TrackImportOut:
    _validate_payload(payload)

    try:
        for track in db.query(Track).all():
            db.delete(track)
        db.flush()

        group_count = 0
        keyword_count = 0

        for index, track_in in enumerate(payload.tracks):
            track = Track(
                key=track_in.key.strip(),
                name=track_in.name.strip(),
                weight=track_in.weight,
                min_score=track_in.min_score,
                sort_order=track_in.sort_order if track_in.sort_order is not None else index,
            )
            db.add(track)
            db.flush()

            for group_index, group_in in enumerate(track_in.groups):
                group = KeywordGroup(
                    track_id=track.id,
                    group_name=group_in.group_name.strip(),
                    sort_order=group_in.sort_order if group_in.sort_order is not None else group_index,
                )
                db.add(group)
                db.flush()
                group_count += 1

                for keyword in group_in.keywords:
                    word = keyword.strip()
                    if not word:
                        continue
                    db.add(Keyword(group_id=group.id, word=word))
                    keyword_count += 1

        db.commit()
    except Exception:
        db.rollback()
        raise

    return TrackImportOut(
        replaced=True,
        track_count=len(payload.tracks),
        group_count=group_count,
        keyword_count=keyword_count,
    )
