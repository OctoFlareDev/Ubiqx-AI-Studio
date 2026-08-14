from __future__ import annotations

import sqlite3
import tarfile
import uuid
from datetime import datetime, timezone
from pathlib import Path


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def backup(data_dir: Path, target: Path) -> dict:
    """Snapshot the SQLite database and asset store into a gzip tar archive.

    The database is copied with SQLite's online backup API so the snapshot is
    consistent even while the service is running. Assets are copied as-is.
    """
    data_dir = Path(data_dir)
    target = Path(target)
    target.parent.mkdir(parents=True, exist_ok=True)

    db_path = data_dir / "ubiqx.db"
    assets_dir = data_dir / "assets"

    file_count = 0
    with tarfile.open(target, "w:gz") as archive:
        if db_path.exists():
            snapshot = data_dir / f".backup-{uuid.uuid4().hex}.db"
            source = sqlite3.connect(str(db_path))
            destination = sqlite3.connect(str(snapshot))
            try:
                source.backup(destination)
            finally:
                destination.close()
                source.close()
            archive.add(snapshot, arcname="ubiqx.db")
            snapshot.unlink(missing_ok=True)
            file_count += 1

        if assets_dir.exists():
            for path in sorted(assets_dir.rglob("*")):
                if path.is_file():
                    archive.add(path, arcname=path.relative_to(data_dir).as_posix())
                    file_count += 1

    return {"created_at": _now(), "archive": str(target), "file_count": file_count}


def _safe_extract(archive: tarfile.TarFile, destination: Path) -> None:
    destination = destination.resolve()
    for member in archive.getmembers():
        member_path = Path(member.name)
        if member_path.is_absolute() or ".." in member_path.parts:
            raise ValueError("unsafe_archive_entry")
        target = (destination / member_path).resolve()
        if target != destination and destination not in target.parents:
            raise ValueError("unsafe_archive_entry")


def restore(archive: Path, data_dir: Path) -> None:
    """Restore a backup archive into the data directory (service should be stopped)."""
    data_dir = Path(data_dir)
    data_dir.mkdir(parents=True, exist_ok=True)
    with tarfile.open(archive, "r:gz") as tar:
        _safe_extract(tar, data_dir)
        tar.extractall(data_dir, filter="data")
