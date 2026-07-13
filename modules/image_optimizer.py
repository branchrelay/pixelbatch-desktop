"""Encode images and optionally meet a real byte-size limit."""

from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
from threading import Event

from PIL import Image


@dataclass(frozen=True)
class OptimizationResult:
    image_bytes: bytes
    final_size: int
    width: int
    height: int
    quality: int | None
    resized: bool
    output_format: str
    target_reached: bool
    warning: str = ""


def size_to_bytes(value: float, unit: str) -> int:
    if value <= 0:
        raise ValueError("Maximum file size must be greater than zero")
    normalized = unit.upper()
    if normalized not in {"KB", "MB"}:
        raise ValueError("File-size unit must be KB or MB")
    return int(value * (1024 if normalized == "KB" else 1024 * 1024))


def _jpeg_ready(image: Image.Image, background: str = "#FFFFFF") -> Image.Image:
    rgba = image.convert("RGBA")
    base = Image.new("RGBA", rgba.size, background)
    base.alpha_composite(rgba)
    return base.convert("RGB")


def encode_image(image: Image.Image, output_format: str, quality: int = 95, background: str = "#FFFFFF") -> bytes:
    fmt = output_format.upper().replace("JPG", "JPEG")
    buffer = BytesIO()
    if fmt == "JPEG":
        _jpeg_ready(image, background).save(buffer, "JPEG", quality=quality, optimize=True, progressive=True)
    elif fmt == "WEBP":
        image.save(buffer, "WEBP", quality=quality, method=6)
    elif fmt == "PNG":
        image.save(buffer, "PNG", optimize=True)
    elif fmt == "BMP":
        _jpeg_ready(image, background).save(buffer, "BMP")
    elif fmt in {"TIFF", "TIF"}:
        image.save(buffer, "TIFF", compression="tiff_deflate")
    else:
        raise ValueError(f"Unsupported output format: {output_format}")
    return buffer.getvalue()


def _best_lossy(image: Image.Image, fmt: str, max_bytes: int, min_quality: int, background: str) -> tuple[bytes, int]:
    low, high = min_quality, 95
    best = encode_image(image, fmt, min_quality, background)
    best_quality = min_quality
    while low <= high:
        quality = (low + high) // 2
        encoded = encode_image(image, fmt, quality, background)
        if len(encoded) <= max_bytes:
            best, best_quality = encoded, quality
            low = quality + 1
        else:
            high = quality - 1
    return best, best_quality


def optimize_to_max_size(
    image: Image.Image,
    output_format: str,
    max_bytes: int,
    allow_resize: bool,
    min_quality: int = 60,
    min_dimension: int = 128,
    cancel: Event | None = None,
    background: str = "#FFFFFF",
) -> OptimizationResult:
    if max_bytes <= 0:
        raise ValueError("max_bytes must be greater than zero")
    if not 20 <= min_quality <= 95:
        raise ValueError("Minimum quality must be between 20 and 95")
    fmt = output_format.upper().replace("JPG", "JPEG")
    working = image.copy()
    resized = False
    quality: int | None = None
    encoded = b""

    for _iteration in range(24):
        if cancel and cancel.is_set():
            raise RuntimeError("Operation cancelled")
        if fmt in {"JPEG", "WEBP"}:
            encoded, quality = _best_lossy(working, fmt, max_bytes, min_quality, background)
        else:
            encoded = encode_image(working, fmt, 95, background)
            quality = None
        if len(encoded) <= max_bytes:
            return OptimizationResult(
                encoded, len(encoded), working.width, working.height, quality, resized, fmt, True
            )
        if not allow_resize or min(working.size) <= min_dimension:
            break
        scale = 0.9
        width = max(min_dimension, int(working.width * scale))
        height = max(min_dimension, int(working.height * scale))
        if (width, height) == working.size:
            break
        working = working.resize((width, height), Image.Resampling.LANCZOS)
        resized = True

    warning = "Could not reduce the file to the requested size without exceeding the minimum quality or resolution limits"
    return OptimizationResult(encoded, len(encoded), working.width, working.height, quality, resized, fmt, False, warning)
