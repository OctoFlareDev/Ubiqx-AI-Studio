from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def _resolve_data_dir() -> Path:
    override = os.getenv("UBIQX_DATA_DIR")
    if override:
        return Path(override).expanduser().resolve()
    return Path(__file__).resolve().parents[1] / "data"


@dataclass(frozen=True)
class Settings:
    app_name: str = "Ubiqx AI Studio API"
    data_dir: Path = _resolve_data_dir()
    database_url: str = os.getenv("UBIQX_DATABASE_URL", "")
    max_upload_bytes: int = int(os.getenv("UBIQX_MAX_UPLOAD_BYTES", str(50 * 1024 * 1024)))
    allowed_origins: tuple[str, ...] = (
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    )
    api_key_prefix: str = "ubq_"
    rate_limit_per_key: int = int(os.getenv("UBIQX_RATE_LIMIT", "1000"))
    rate_limit_window_seconds: float = float(os.getenv("UBIQX_RATE_LIMIT_WINDOW_SECONDS", "60"))
    job_timeout_seconds: float = float(os.getenv("UBIQX_JOB_TIMEOUT_SECONDS", "300"))
    idempotency_retention_seconds: float = float(os.getenv("UBIQX_IDEMPOTENCY_RETENTION_SECONDS", str(24 * 60 * 60)))
    allow_remote_bootstrap: bool = os.getenv("UBIQX_ALLOW_REMOTE_BOOTSTRAP", "0").lower() in {"1", "true", "yes"}

    @property
    def resolved_database_url(self) -> str:
        if self.database_url:
            return self.database_url
        return f"sqlite:///{self.data_dir / 'ubiqx.db'}"

    @property
    def asset_dir(self) -> Path:
        return self.data_dir / "assets"

    @property
    def export_dir(self) -> Path:
        return self.data_dir / "exports"

    @property
    def tmp_dir(self) -> Path:
        return self.data_dir / "tmp"


settings = Settings()
