from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from .db import get_db
from .models import ApiKey, LocalUser, Project
from .security import verify_api_key


@dataclass
class AuthContext:
    user: LocalUser
    key: ApiKey


def get_auth_context(
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> AuthContext:
    raw_key = ""
    if authorization and authorization.startswith("Bearer "):
        raw_key = authorization.removeprefix("Bearer ").strip()
    result = verify_api_key(db, raw_key)
    if result is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid_or_missing_api_key")
    key, user = result
    return AuthContext(user=user, key=key)


def get_current_user(auth: AuthContext = Depends(get_auth_context)) -> LocalUser:
    return auth.user


def _scope_check(auth: AuthContext, scopes: tuple[str, ...]) -> LocalUser:
    granted = set(auth.key.scopes or [])
    if "*" in granted:
        return auth.user
    if not any(scope in granted for scope in scopes):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="insufficient_scope")
    return auth.user


def require_scope(*scopes: str) -> Callable[..., LocalUser]:
    """Build a dependency that authenticates the caller and requires a scope."""

    def _dependency(auth: AuthContext = Depends(get_auth_context)) -> LocalUser:
        return _scope_check(auth, scopes)

    return _dependency


def get_owned_project(project_id: str, user: LocalUser, db: Session) -> Project:
    project = db.get(Project, project_id)
    if project is None or project.user_id != user.id or project.status == "deleted":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="project_not_found")
    return project
