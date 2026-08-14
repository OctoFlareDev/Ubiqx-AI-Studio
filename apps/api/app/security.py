from __future__ import annotations

import hashlib
import secrets
import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from .config import settings
from .models import ApiKey, LocalUser


WILDCARD_SCOPE = "*"

KNOWN_SCOPES: frozenset[str] = frozenset({
    "projects:read",
    "projects:write",
    "assets:read",
    "assets:write",
    "scenes:read",
    "scenes:write",
    "imports:read",
    "imports:write",
    "exports:read",
    "exports:write",
    "ai:read",
    "ai:write",
    "api_keys:read",
    "api_keys:write",
})


class UnknownScopeError(ValueError):
    def __init__(self, scope: str) -> None:
        super().__init__(f"unknown_scope:{scope}")
        self.scope = scope


def normalize_scopes(scopes: list[str] | None) -> list[str]:
    """Validate and deduplicate a requested scope list, preserving order."""
    result: list[str] = []
    seen: set[str] = set()
    for raw in scopes or []:
        scope = raw.strip()
        if not scope:
            continue
        if scope != WILDCARD_SCOPE and scope not in KNOWN_SCOPES:
            raise UnknownScopeError(scope)
        if scope not in seen:
            seen.add(scope)
            result.append(scope)
    if not result:
        raise ValueError("at_least_one_scope_required")
    return result


def _hash_key(user_id: str, raw_key: str) -> str:
    return hashlib.sha256(f"{user_id}:{raw_key}".encode("utf-8")).hexdigest()


def create_api_key(
    db: Session,
    user: LocalUser,
    name: str = "Local Studio",
    scopes: list[str] | None = None,
    expires_at: datetime | None = None,
) -> tuple[ApiKey, str]:
    raw_key = f"{settings.api_key_prefix}{secrets.token_urlsafe(32)}"
    key = ApiKey(
        id=str(uuid.uuid4()),
        user_id=user.id,
        key_hash=_hash_key(user.id, raw_key),
        name=name,
        scopes=scopes or [WILDCARD_SCOPE],
        expires_at=expires_at,
    )
    db.add(key)
    db.commit()
    db.refresh(key)
    return key, raw_key


def list_api_keys(db: Session, user: LocalUser) -> list[ApiKey]:
    return list(
        db.scalars(
            select(ApiKey).where(ApiKey.user_id == user.id).order_by(ApiKey.created_at.desc())
        ).all()
    )


def revoke_api_key(db: Session, key: ApiKey) -> ApiKey:
    if key.revoked_at is None:
        key.revoked_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(key)
    return key


def verify_api_key(db: Session, raw_key: str) -> tuple[ApiKey, LocalUser] | None:
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
    return key, user


def get_or_create_local_user(db: Session) -> LocalUser:
    user = db.scalar(select(LocalUser).order_by(LocalUser.created_at.asc()).limit(1))
    if user is not None:
        return user
    user = LocalUser(id=str(uuid.uuid4()), display_name="Local Designer")
    db.add(user)
    db.commit()
    db.refresh(user)
    return user
