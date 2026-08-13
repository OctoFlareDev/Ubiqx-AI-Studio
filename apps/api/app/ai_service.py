from __future__ import annotations

import io
import time
import uuid
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Protocol

from PIL import Image
from sqlalchemy import select
from sqlalchemy.orm import Session

from .db import SessionLocal
from .models import AiTask, Asset, Project
from .storage import AssetStore


TERMINAL_STATUSES = {"succeeded", "failed", "cancelled"}
MAX_ATTEMPTS = 3
MAX_DIMENSION = 4096
BACKOFF_BASE_SECONDS = 0.05
CANCELLATION_REQUESTS: set[str] = set()


class AiTaskFailure(Exception):
    def __init__(self, code: str, message: str, *, retryable: bool = False) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.retryable = retryable


@dataclass
class AiProviderResult:
    data: bytes
    media_type: str
    width: int
    height: int
    metadata: dict = field(default_factory=dict)


@dataclass
class AiProviderRequest:
    operation: str
    image: Image.Image
    options: dict
    cancel_check: Callable[[], bool]


class AiProvider(Protocol):
    name: str

    def process(self, request: AiProviderRequest) -> AiProviderResult:
        ...


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _safe_error(exc: AiTaskFailure) -> str:
    return exc.code


def _load_image(path: Path) -> Image.Image:
    try:
        with Image.open(path) as image:
            image = image.convert("RGBA")
            image.load()
            if max(image.size) > MAX_DIMENSION:
                ratio = MAX_DIMENSION / max(image.size)
                image = image.resize(
                    (max(1, int(image.width * ratio)), max(1, int(image.height * ratio))),
                    Image.Resampling.LANCZOS,
                )
            return image.copy()
    except Exception as exc:
        raise AiTaskFailure("invalid_ai_input", "invalid_ai_input", retryable=False) from exc


def _save_png(image: Image.Image) -> bytes:
    buffer = io.BytesIO()
    image.save(buffer, format="PNG", optimize=True)
    return buffer.getvalue()


def _output_name(input_asset: Asset, operation: str) -> str:
    stem = Path(input_asset.original_name or "asset").stem[:100] or "asset"
    suffix = "upscaled" if operation == "upscale" else "matte"
    return f"{stem}-{suffix}.png"


def _sample_border_color(image: Image.Image) -> tuple[int, int, int]:
    pixels = image.load()
    width, height = image.size
    samples: list[tuple[int, int, int]] = []
    for x in range(width):
        for y in (0, height - 1):
            pixel = pixels[x, y]
            if pixel[3] >= 128:
                samples.append((pixel[0], pixel[1], pixel[2]))
    for y in range(height):
        for x in (0, width - 1):
            pixel = pixels[x, y]
            if pixel[3] >= 128:
                samples.append((pixel[0], pixel[1], pixel[2]))
    if not samples:
        return (255, 255, 255)
    return (
        sum(item[0] for item in samples) // len(samples),
        sum(item[1] for item in samples) // len(samples),
        sum(item[2] for item in samples) // len(samples),
    )


def _remove_background(
    image: Image.Image,
    tolerance: float,
    cancel_check: Callable[[], bool],
) -> Image.Image:
    width, height = image.size
    pixels = image.load()
    background = _sample_border_color(image)
    tolerance_sq = tolerance * tolerance
    mask = [False] * (width * height)
    queue: deque[int] = deque()

    def matches(pixel: tuple[int, int, int, int]) -> bool:
        if pixel[3] < 128:
            return False
        return (
            (pixel[0] - background[0]) ** 2
            + (pixel[1] - background[1]) ** 2
            + (pixel[2] - background[2]) ** 2
        ) <= tolerance_sq

    def add_if_match(x: int, y: int) -> None:
        if not (0 <= x < width and 0 <= y < height):
            return
        index = y * width + x
        if mask[index] or not matches(pixels[x, y]):
            return
        mask[index] = True
        queue.append(index)

    for x in range(width):
        add_if_match(x, 0)
        add_if_match(x, height - 1)
    for y in range(height):
        add_if_match(0, y)
        add_if_match(width - 1, y)

    checked = 0
    while queue:
        index = queue.popleft()
        x = index % width
        y = index // width
        add_if_match(x - 1, y)
        add_if_match(x + 1, y)
        add_if_match(x, y - 1)
        add_if_match(x, y + 1)
        checked += 1
        if checked % 2048 == 0 and cancel_check():
            raise AiTaskFailure("cancelled", "cancelled", retryable=False)

    output = image.copy()
    output_pixels = output.load()
    for index, selected in enumerate(mask):
        if not selected:
            continue
        x = index % width
        y = index // width
        r, g, b, _alpha = output_pixels[x, y]
        output_pixels[x, y] = (r, g, b, 0)
    return output


class LocalImageProvider:
    name = "local"

    def process(self, request: AiProviderRequest) -> AiProviderResult:
        if request.cancel_check():
            raise AiTaskFailure("cancelled", "cancelled", retryable=False)
        if request.operation == "upscale":
            return self._upscale(request)
        if request.operation == "remove_background":
            return self._remove_background(request)
        raise AiTaskFailure("unsupported_operation", "unsupported_operation", retryable=False)

    def _upscale(self, request: AiProviderRequest) -> AiProviderResult:
        try:
            scale = float(request.options.get("scale", 2))
        except (TypeError, ValueError):
            raise AiTaskFailure("invalid_options", "invalid_options", retryable=False) from None
        if not 1 <= scale <= 8:
            raise AiTaskFailure("invalid_options", "invalid_options", retryable=False)

        input_width, input_height = request.image.size
        max_allowed_scale = min(scale, MAX_DIMENSION / input_width, MAX_DIMENSION / input_height)
        output_width = max(1, round(input_width * max_allowed_scale))
        output_height = max(1, round(input_height * max_allowed_scale))
        if request.cancel_check():
            raise AiTaskFailure("cancelled", "cancelled", retryable=False)
        output = request.image.resize((output_width, output_height), Image.Resampling.LANCZOS)
        return AiProviderResult(
            data=_save_png(output),
            media_type="image/png",
            width=output_width,
            height=output_height,
            metadata={
                "resize_method": "lanczos",
                "requested_scale": scale,
                "applied_scale": max_allowed_scale,
            },
        )

    def _remove_background(self, request: AiProviderRequest) -> AiProviderResult:
        try:
            tolerance = float(request.options.get("tolerance", 32))
        except (TypeError, ValueError):
            raise AiTaskFailure("invalid_options", "invalid_options", retryable=False) from None
        if not 0 <= tolerance <= 255:
            raise AiTaskFailure("invalid_options", "invalid_options", retryable=False)
        output = _remove_background(request.image, tolerance, request.cancel_check)
        return AiProviderResult(
            data=_save_png(output),
            media_type="image/png",
            width=output.width,
            height=output.height,
            metadata={"algorithm": "border_flood_fill", "tolerance": tolerance},
        )


class AiProviderRegistry:
    def __init__(self) -> None:
        self._providers = {
            "local": LocalImageProvider(),
        }

    def get(self, name: str) -> AiProvider | None:
        return self._providers.get(name)


def _build_usage(
    task: AiTask,
    input_asset: Asset,
    attempts: int,
    output_asset: Asset | None,
    started_at: datetime,
) -> dict:
    return {
        "provider": task.provider,
        "operation": task.operation,
        "attempts": attempts,
        "input_asset_id": input_asset.id,
        "output_asset_id": output_asset.id if output_asset else None,
        "input_pixels": (input_asset.width or 0) * (input_asset.height or 0),
        "output_pixels": (output_asset.width or 0) * (output_asset.height or 0) if output_asset else 0,
        "estimated_cost": 0,
        "duration_ms": int((_now() - started_at).total_seconds() * 1000),
    }


def _get_or_create_ai_asset(
    db: Session,
    project_id: str,
    input_asset: Asset,
    task: AiTask,
    result: AiProviderResult,
) -> Asset:
    stored = AssetStore().save_bytes(
        result.data,
        original_name=_output_name(input_asset, task.operation),
        media_type=result.media_type,
    )
    existing = db.scalar(
        select(Asset).where(
            Asset.project_id == project_id,
            Asset.content_hash == stored["content_hash"],
        )
    )
    if existing is not None:
        return existing
    asset = Asset(
        id=str(uuid.uuid4()),
        project_id=project_id,
        content_hash=stored["content_hash"],
        media_type=result.media_type,
        original_name=stored["original_name"],
        width=result.width,
        height=result.height,
        byte_size=stored["byte_size"],
        storage_path=stored["storage_path"],
        source="ai_processed",
        metadata={
            "operation": task.operation,
            "provider": task.provider,
            "input_asset_id": input_asset.id,
            "algorithm": result.metadata.get("algorithm"),
        },
    )
    db.add(asset)
    db.flush()
    return asset


def run_ai_task(task_id: str) -> None:
    db = SessionLocal()
    try:
        task = db.get(AiTask, task_id)
        if task is None or task.status in TERMINAL_STATUSES:
            return
        if task_id in CANCELLATION_REQUESTS:
            _mark_cancelled(db, task)
            return

        project = db.get(Project, task.project_id)
        input_asset = db.get(Asset, task.input_asset_id)
        if project is None:
            raise AiTaskFailure("project_missing", "project_missing", retryable=False)
        if input_asset is None or input_asset.project_id != task.project_id:
            raise AiTaskFailure("input_asset_missing", "input_asset_missing", retryable=False)
        if input_asset.media_type not in {"image/png", "image/jpeg", "image/webp"}:
            raise AiTaskFailure("unsupported_ai_input_type", "unsupported_ai_input_type", retryable=False)

        provider = AiProviderRegistry().get(task.provider)
        if provider is None:
            raise AiTaskFailure("provider_unavailable", "provider_unavailable", retryable=False)

        image = _load_image(Path(input_asset.storage_path))
        task.status = "running"
        task.started_at = _now()
        db.commit()
        started_at = task.started_at
        attempts = 0

        while attempts < MAX_ATTEMPTS:
            if task_id in CANCELLATION_REQUESTS:
                _mark_cancelled(db, task, input_asset=input_asset, attempts=attempts, started_at=started_at)
                return
            attempts += 1
            try:
                result = provider.process(
                    AiProviderRequest(
                        operation=task.operation,
                        image=image,
                        options=task.options if isinstance(task.options, dict) else {},
                        cancel_check=lambda: task_id in CANCELLATION_REQUESTS,
                    )
                )
            except AiTaskFailure as exc:
                _record_failure(db, task, input_asset, attempts, exc)
                if task_id in CANCELLATION_REQUESTS or exc.code == "cancelled":
                    _mark_cancelled(db, task, input_asset=input_asset, attempts=attempts, started_at=started_at)
                    return
                if not exc.retryable or attempts >= MAX_ATTEMPTS:
                    _mark_failed(db, task, input_asset=input_asset, attempts=attempts, started_at=started_at)
                    return
                _sleep_backoff(attempts)
                continue
            except Exception as exc:
                failure = AiTaskFailure("provider_failed", "provider_failed", retryable=True)
                _record_failure(db, task, input_asset, attempts, failure)
                if task_id in CANCELLATION_REQUESTS:
                    _mark_cancelled(db, task, input_asset=input_asset, attempts=attempts, started_at=started_at)
                    return
                if attempts >= MAX_ATTEMPTS:
                    _mark_failed(db, task, input_asset=input_asset, attempts=attempts, started_at=started_at)
                    return
                _sleep_backoff(attempts)
                continue

            if task_id in CANCELLATION_REQUESTS:
                _mark_cancelled(db, task, input_asset=input_asset, attempts=attempts, started_at=started_at)
                return

            output_asset = _get_or_create_ai_asset(db, project.id, input_asset, task, result)
            task.output_asset_id = output_asset.id
            task.status = "succeeded"
            task.progress = 1
            task.last_error = None
            task.usage = _build_usage(task, input_asset, attempts, output_asset, started_at)
            task.finished_at = _now()
            project.last_autosaved_at = _now()
            project.updated_at = _now()
            db.commit()
            return

        _mark_failed(db, task, input_asset=input_asset, attempts=attempts, started_at=started_at)
    except AiTaskFailure as exc:
        db.rollback()
        _mark_failed(db, task_id, exc.code)
    except Exception as exc:
        db.rollback()
        _mark_failed(db, task_id, "ai_task_failed")
    finally:
        CANCELLATION_REQUESTS.discard(task_id)
        db.close()


def _record_failure(
    db: Session,
    task: AiTask,
    input_asset: Asset,
    attempts: int,
    exc: AiTaskFailure,
) -> None:
    task.retry_count = max(0, attempts - 1)
    task.last_error = _safe_error(exc)
    task.progress = min(0.9, attempts / MAX_ATTEMPTS)
    task.usage = _build_usage(task, input_asset, attempts, None, task.started_at or _now())
    db.commit()


def _mark_failed(
    db: Session,
    task_or_id: AiTask | str,
    error: str | None = None,
    *,
    input_asset: Asset | None = None,
    attempts: int = 0,
    started_at: datetime | None = None,
) -> None:
    task = db.get(AiTask, task_or_id) if isinstance(task_or_id, str) else task_or_id
    if task is None:
        return
    task.status = "failed"
    task.last_error = error or task.last_error or "ai_task_failed"
    task.finished_at = _now()
    if input_asset is not None and started_at is not None:
        task.usage = _build_usage(task, input_asset, attempts, None, started_at)
    db.commit()


def _mark_cancelled(
    db: Session,
    task: AiTask,
    *,
    input_asset: Asset | None = None,
    attempts: int = 0,
    started_at: datetime | None = None,
) -> None:
    task.status = "cancelled"
    task.finished_at = _now()
    if input_asset is not None and started_at is not None:
        task.usage = _build_usage(task, input_asset, attempts, None, started_at)
    db.commit()


def _sleep_backoff(attempt: int) -> None:
    time.sleep(BACKOFF_BASE_SECONDS * (2 ** max(0, attempt - 1)))
