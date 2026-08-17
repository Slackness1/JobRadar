"""Derive the caller's identity from the login token, not from a client header.

`X-Resume-User-Key` is written by the browser, and an account key is the guessable
form `u_<id>`. Trusting it means anyone can claim another student's key and read
their interview transcripts, scores or raw answer audio. So:

  * bearer session token present  → identity comes from the token, header ignored
  * bearer token present but dead → 401 (do not silently fall back to the header)
  * no token, header is `u_<id>`  → refuse the claim, return '' so the caller's
                                    owner check answers 401/403
  * no token, header is a random guest UUID → trust it (anonymous, guessing another
                                    guest's UUID is not a realistic escalation)

Guest keys stay header-based on purpose: guests have no credential to present, and
their key is a client-generated UUID rather than an enumerable account id.
"""
from __future__ import annotations

import re
from typing import Optional

from fastapi import Depends, Header, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.services.auth import auth_service

# Account keys are minted by auth_service.user_key_for() as f"u_{user.id}".
_ACCOUNT_USER_KEY_RE = re.compile(r"^u_\d+$")


def extract_bearer(authorization: str | None) -> str | None:
    if not authorization:
        return None
    parts = authorization.split(None, 1)
    if len(parts) != 2 or parts[0].lower() != "bearer":
        return None
    return parts[1].strip() or None


def resolve_user_key(
    authorization: Optional[str] = Header(default=None),
    x_resume_user_key: str = Header(default=""),
    db: Session = Depends(get_db),
) -> str:
    """Return the user_key the caller is actually entitled to."""
    token = extract_bearer(authorization)
    if token:
        user = auth_service.resolve_session(db, token)
        if user is None:
            raise HTTPException(status_code=401, detail="登录态已过期,请重新登录")
        return auth_service.user_key_for(user)

    claimed = (x_resume_user_key or "").strip()
    if _ACCOUNT_USER_KEY_RE.match(claimed):
        return ""
    return claimed
