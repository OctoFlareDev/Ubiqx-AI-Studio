from __future__ import annotations

import hashlib
import hmac
import secrets
import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from .config import settings
from .models import ApiKey, LocalUser


def _hash_key(user_id: str, raw_key: str) -> str:
    return hashlib.sha256(f"{user_id}:{raw_key}".encode("utf-8")).hexdigest()


def create_api_key(db: Session, user: LocalUser, name: str = "Local Studio") -> tuple[ApiKey, str]:
    raw_key = f"{settings.api_key_prefix}{secrets.token_urlsafe(32)}"
    key = ApiKey(
        id=str(uuid.uuid4()),
        user_id=user.id,
        key_hash=_hash_key(user.id, raw_key),
        name=name,
        scopes=["*"],
    )
    db.add(key)
    db.commit()
    db.refresh(key)
    return key, raw_key


def verify_api_key(db: Session, raw_key: str) -> LocalUser | None:
    if not raw_key or not raw_key.startswith(settings.api_key_prefix):
        return None
    user = db.scalar(select(LocalUser).order_by(LocalUser.created_at.asc()).limit(1))
    if user is None:
        return None
    expected_hash = _hash_key(user.id, raw_key)
    key = db.scalar(select(ApiKey).where(ApiKey.key_hash == expected_hash))
    if key is None:
        return None
    now = datetime.now(timezone.utc)
    if key.revoked_at is not None or (key.expires_at is not None and key.expires_at <= now):
        return None
    key.last_used_at = now
    db.commit()
    return user


def get_or_create_local_user(db: Session) -> LocalUser:
    user = db.scalar(select(LocalUser).order_by(LocalUser.created_at.asc()).limit(1))
    if user is not None:
        return user
    user = LocalUser(id=str(uuid.uuid4()), display_name="Local Designer")
    db.add(user)
    db.commit()
    db.refresh(user)
    return user

