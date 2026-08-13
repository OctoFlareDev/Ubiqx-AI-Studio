from __future__ import annotations

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from .db import get_db
from .models import LocalUser, Project
from .security import verify_api_key


def get_current_user(
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> LocalUser:
    raw_key = ""
    if authorization and authorization.startswith("Bearer "):
        raw_key = authorization.removeprefix("Bearer ").strip()
    user = verify_api_key(db, raw_key)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid_or_missing_api_key")
    return user


def get_owned_project(project_id: str, user: LocalUser, db: Session) -> Project:
    project = db.get(Project, project_id)
    if project is None or project.user_id != user.id or project.status == "deleted":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="project_not_found")
    return project

