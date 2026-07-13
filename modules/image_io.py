"""Validated atomic image writes."""

from __future__ import annotations

import os
from io import BytesIO
from pathlib import Path
from tempfile import NamedTemporaryFile

from PIL import Image


class ImageWriteError(OSError):
    """An encoded image could not be validated or atomically written."""


def verify_image_bytes(data: bytes) -> None:
    if not data:
        raise ImageWriteError("Image data is empty")
    try:
        with Image.open(BytesIO(data)) as image:
            image.verify()
    except (OSError, ValueError) as exc:
        raise ImageWriteError("Image data is invalid or damaged") from exc


def atomic_write_image(path: str | Path, data: bytes, max_bytes: int | None = None) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    if max_bytes is not None and len(data) > max_bytes:
        raise ImageWriteError(f"Encoded image exceeds the maximum size ({len(data)} > {max_bytes} bytes)")
    verify_image_bytes(data)
    temp_path: Path | None = None
    try:
        with NamedTemporaryFile(
            mode="wb", dir=target.parent, prefix=f".{target.stem}-", suffix=f"{target.suffix}.tmp", delete=False
        ) as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
            temp_path = Path(handle.name)
        verify_image_bytes(temp_path.read_bytes())
        if temp_path.stat().st_size <= 0:
            raise ImageWriteError("Temporary image is empty")
        os.replace(temp_path, target)
        temp_path = None
    finally:
        if temp_path:
            temp_path.unlink(missing_ok=True)
