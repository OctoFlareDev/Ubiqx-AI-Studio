from __future__ import annotations

import hashlib
import shutil
from pathlib import Path

from fastapi import UploadFile

from .config import settings


ALLOWED_EXTENSIONS = {
    ".psd": "image/vnd.adobe.photoshop",
    ".psb": "image/vnd.adobe.photoshop",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
    ".svg": "image/svg+xml",
}


def _detect_kind(head: bytes) -> str | None:
    if head.startswith(b"\x89PNG\r\n\x1a\n"):
        return ".png"
    if head.startswith(b"\xff\xd8\xff"):
        return ".jpg"
    if head.startswith(b"8BPS"):
        return ".psd"
    if head.startswith(b"RIFF") and head[8:12] == b"WEBP":
        return ".webp"
    stripped = head.lstrip()
    if stripped.startswith(b"<svg") or stripped.startswith(b"<?xml") and b"<svg" in stripped[:1024]:
        return ".svg"
    return None


def _safe_original_name(name: str) -> str:
    return Path(name or "asset").name[:255] or "asset"


def _persist(data_dir: Path, content_hash: str, source: Path) -> Path:
    destination = data_dir / content_hash[:2] / content_hash
    destination.parent.mkdir(parents=True, exist_ok=True)
    if not destination.exists():
        shutil.move(str(source), destination)
    return destination


class AssetStore:
    def __init__(self, root: Path | None = None) -> None:
        self.root = root or settings.asset_dir
        self.tmp_dir = settings.tmp_dir
        self.root.mkdir(parents=True, exist_ok=True)
        self.tmp_dir.mkdir(parents=True, exist_ok=True)

    async def save(self, upload: UploadFile) -> dict:
        original_name = _safe_original_name(upload.filename or "asset")
        extension = Path(original_name).suffix.lower()
        if extension not in ALLOWED_EXTENSIONS:
            raise ValueError("unsupported_file_type")

        tmp_path = self.tmp_dir / f"{hashlib.sha256(original_name.encode()).hexdigest()}-{id(upload)}"
        digest = hashlib.sha256()
        size = 0
        head = b""
        with tmp_path.open("wb") as out:
            while chunk := await upload.read(1024 * 1024):
                size += len(chunk)
                if size > settings.max_upload_bytes:
                    out.close()
                    tmp_path.unlink(missing_ok=True)
                    raise ValueError("file_too_large")
                digest.update(chunk)
                if len(head) < 16:
                    head += chunk[: 16 - len(head)]
                out.write(chunk)

        detected_extension = _detect_kind(head)
        if detected_extension is None:
            tmp_path.unlink(missing_ok=True)
            raise ValueError("unknown_file_type")
        compatible_extension = (
            (extension == ".jpg" and detected_extension == ".jpeg")
            or (extension == ".psb" and detected_extension == ".psd")
        )
        if detected_extension != extension and not compatible_extension:
            tmp_path.unlink(missing_ok=True)
            raise ValueError("file_extension_mismatch")

        declared_type = upload.content_type or ""
        expected_type = ALLOWED_EXTENSIONS[extension]
        if declared_type and not declared_type.startswith("image/") and declared_type not in expected_type:
            tmp_path.unlink(missing_ok=True)
            raise ValueError("invalid_media_type")

        content_hash = digest.hexdigest()
        storage_path = _persist(self.root, content_hash, tmp_path)
        return {
            "content_hash": content_hash,
            "media_type": expected_type,
            "original_name": original_name,
            "byte_size": size,
            "storage_path": str(storage_path),
        }

    def save_bytes(self, data: bytes, original_name: str, media_type: str) -> dict:
        safe_name = _safe_original_name(original_name)
        content_hash = hashlib.sha256(data).hexdigest()
        destination = self.root / content_hash[:2] / content_hash
        destination.parent.mkdir(parents=True, exist_ok=True)
        if not destination.exists():
            destination.write_bytes(data)
        return {
            "content_hash": content_hash,
            "media_type": media_type,
            "original_name": safe_name,
            "byte_size": len(data),
            "storage_path": str(destination),
        }
