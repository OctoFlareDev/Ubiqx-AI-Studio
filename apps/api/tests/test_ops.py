from __future__ import annotations

import io
import sqlite3
import tarfile
import tempfile
from pathlib import Path

import pytest

from app.ops import backup, restore


def test_backup_and_restore_round_trip() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        data_dir = Path(tmp) / "data"
        assets_dir = data_dir / "assets" / "ab"
        assets_dir.mkdir(parents=True)

        db_path = data_dir / "ubiqx.db"
        connection = sqlite3.connect(str(db_path))
        connection.execute("CREATE TABLE t (id INTEGER PRIMARY KEY, value TEXT)")
        connection.execute("INSERT INTO t (value) VALUES (?)", ("hello",))
        connection.commit()
        connection.close()
        asset_file = assets_dir / "file.bin"
        asset_file.write_bytes(b"asset-bytes")

        archive = Path(tmp) / "backup.tar.gz"
        result = backup(data_dir, archive)
        assert archive.exists()
        assert result["file_count"] >= 2

        # Simulate data loss, then restore.
        (data_dir / "ubiqx.db").unlink()
        asset_file.unlink()
        restore(archive, data_dir)

        connection = sqlite3.connect(str(data_dir / "ubiqx.db"))
        row = connection.execute("SELECT value FROM t").fetchone()
        connection.close()
        assert row == ("hello",)
        assert (assets_dir / "file.bin").read_bytes() == b"asset-bytes"


def test_restore_rejects_path_traversal() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        data_dir = Path(tmp) / "data"
        data_dir.mkdir(parents=True)
        malicious = Path(tmp) / "evil.tar.gz"
        with tarfile.open(malicious, "w:gz") as tar:
            info = tarfile.TarInfo("../../evil.txt")
            payload = b"pwn"
            info.size = len(payload)
            tar.addfile(info, io.BytesIO(payload))

        with pytest.raises(ValueError, match="unsafe_archive_entry"):
            restore(malicious, data_dir)
