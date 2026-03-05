"""Import legacy config.yaml into database on first run."""
import json
import yaml
from sqlalchemy.orm import Session

from app.models import Track, KeywordGroup, Keyword, ScoringConfig, ExcludeRule
from app.config import LEGACY_CONFIG_PATH


def seed_from_yaml(db: Session) -> bool:
    """Import config.yaml into DB. Returns True if seeded, False if already populated."""
    if db.query(Track).first():
        return False

    config_path = LEGACY_CONFIG_PATH
    if not config_path.exists():
        return False

    with open(config_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    # 1. Tracks + keyword groups + keywords
    tracks_cfg = config.get("tracks", {})
    for sort_idx, (track_key, track_data) in enumerate(tracks_cfg.items()):
        track = Track(
            key=track_key,
            name=track_data.get("name", track_key),
            weight=track_data.get("weight", 1.0),
            min_score=track_data.get("min_score", 10),
            sort_order=sort_idx,
        )
        db.add(track)
        db.flush()

        keywords_cfg = track_data.get("keywords", {})
        for g_idx, (group_name, words) in enumerate(keywords_cfg.items()):
            group = KeywordGroup(
                track_id=track.id,
                group_name=group_name,
                sort_order=g_idx,
            )
            db.add(group)
            db.flush()

            for word in words:
                db.add(Keyword(group_id=group.id, word=word))

    # 2. Scoring config
    scoring_data = {
        "scoring": config.get("scoring", {}),
        "thresholds": config.get("thresholds", {}),
        "skill_synonyms": config.get("skill_synonyms", {}),
        "hard_filters": config.get("hard_filters", {}),
    }
    db.add(ScoringConfig(config_json=json.dumps(scoring_data, ensure_ascii=False)))

    # 3. Exclude rules
    exclude_kws = config.get("hard_filters", {}).get("exclude_keywords", {})
    for category, keywords in exclude_kws.items():
        for kw in keywords:
            db.add(ExcludeRule(category=category, keyword=kw))

    db.commit()
    return True
