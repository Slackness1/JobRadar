from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.models import Track, KeywordGroup, Keyword
from app.schemas import (
    TrackOut, TrackIn, TrackUpdate,
    KeywordGroupOut, KeywordGroupIn,
    KeywordOut, KeywordBatchIn,
    TrackImportIn, TrackImportOut,
)
from app.services.track_importer import import_tracks_json_full_replace

router = APIRouter(prefix="/api/tracks", tags=["tracks"])


@router.get("", response_model=list[TrackOut])
@router.get("/", response_model=list[TrackOut])
def list_tracks(db: Session = Depends(get_db)):
    tracks = (
        db.query(Track)
        .options(joinedload(Track.groups).joinedload(KeywordGroup.keywords))
        .order_by(Track.sort_order)
        .all()
    )
    return tracks


@router.post("", response_model=TrackOut)
@router.post("/", response_model=TrackOut)
def create_track(data: TrackIn, db: Session = Depends(get_db)):
    if db.query(Track).filter(Track.key == data.key).first():
        raise HTTPException(400, "Track key already exists")
    track = Track(**data.model_dump())
    db.add(track)
    db.commit()
    db.refresh(track)
    return track


@router.put("/{track_id}", response_model=TrackOut)
def update_track(track_id: int, data: TrackUpdate, db: Session = Depends(get_db)):
    track = db.get(Track, track_id)
    if not track:
        raise HTTPException(404, "Track not found")
    for field, value in data.model_dump(exclude_none=True).items():
        setattr(track, field, value)
    db.commit()
    db.refresh(track)
    return track


@router.delete("/{track_id}")
def delete_track(track_id: int, db: Session = Depends(get_db)):
    track = db.get(Track, track_id)
    if not track:
        raise HTTPException(404, "Track not found")
    db.delete(track)
    db.commit()
    return {"ok": True}


# ---- Keyword Groups ----

@router.post("/{track_id}/groups", response_model=KeywordGroupOut)
def add_group(track_id: int, data: KeywordGroupIn, db: Session = Depends(get_db)):
    track = db.get(Track, track_id)
    if not track:
        raise HTTPException(404, "Track not found")
    group = KeywordGroup(track_id=track_id, **data.model_dump())
    db.add(group)
    db.commit()
    db.refresh(group)
    return group


@router.put("/{track_id}/groups/{group_id}", response_model=KeywordGroupOut)
def update_group(track_id: int, group_id: int, data: KeywordGroupIn, db: Session = Depends(get_db)):
    group = db.get(KeywordGroup, group_id)
    if group is None or int(getattr(group, "track_id", 0) or 0) != track_id:
        raise HTTPException(404, "Group not found")
    setattr(group, "group_name", data.group_name)
    setattr(group, "sort_order", data.sort_order)
    db.commit()
    db.refresh(group)
    return group


@router.delete("/{track_id}/groups/{group_id}")
def delete_group(track_id: int, group_id: int, db: Session = Depends(get_db)):
    group = db.get(KeywordGroup, group_id)
    if group is None or int(getattr(group, "track_id", 0) or 0) != track_id:
        raise HTTPException(404, "Group not found")
    db.delete(group)
    db.commit()
    return {"ok": True}


# ---- Keywords ----

@router.post("/keywords", response_model=list[KeywordOut])
def batch_add_keywords(data: KeywordBatchIn, db: Session = Depends(get_db)):
    group = db.get(KeywordGroup, data.group_id)
    if not group:
        raise HTTPException(404, "Group not found")
    added = []
    for word in data.words:
        kw = Keyword(group_id=data.group_id, word=word)
        db.add(kw)
        added.append(kw)
    db.commit()
    for kw in added:
        db.refresh(kw)
    return added


@router.delete("/keywords/{keyword_id}")
def delete_keyword(keyword_id: int, db: Session = Depends(get_db)):
    kw = db.get(Keyword, keyword_id)
    if not kw:
        raise HTTPException(404, "Keyword not found")
    db.delete(kw)
    db.commit()
    return {"ok": True}


@router.post("/import-json", response_model=TrackImportOut)
def import_tracks_json(payload: TrackImportIn, db: Session = Depends(get_db)):
    try:
        return import_tracks_json_full_replace(db, payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
