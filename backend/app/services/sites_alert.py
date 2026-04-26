from datetime import datetime, timedelta
from typing import Literal

from app.config import ALERT_STALE_DAYS

AlertLevel = Literal["green", "yellow", "red", "unknown"]


def alert_level(runs: list, now: datetime) -> AlertLevel:
    """Compute alert level from runs sorted by started_at DESC.

    runs: objects with .started_at, .status, .new_count attributes.
    """
    if not runs:
        return "unknown"

    last = runs[0]
    if last.status == "failed":
        if len(runs) >= 2 and runs[1].status == "failed":
            return "red"
        return "yellow"

    # last is 'success'
    new_run_dates = [r.started_at for r in runs if r.new_count > 0]
    if not new_run_dates:
        last_new = now - timedelta(days=999)
    else:
        last_new = max(new_run_dates)

    if (now - last_new).days >= ALERT_STALE_DAYS:
        return "yellow"
    return "green"
