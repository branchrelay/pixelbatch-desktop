"""High-quality batch resizing with optional output-size optimization."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from threading import Event
from typing import Callable

from PIL import Image, ImageOps

from .image_io import atomic_write_image
from .image_optimizer import encode_image, optimize_to_max_size
from .remove_bg import list_images


RESIZE_MODES = ("Fit", "Fill", "Exact", "Width only", "Height only", "Percentage")
MODE_ALIASES = {
    "Точный размер": "Exact",
    "Вписать с полями": "Fit",
    "Заполнить с обрезкой": "Fit",
}
LogCallback = Callable[[str], None]
ProgressCallback = Callable[[int, int], None]


@dataclass(frozen=True)
class ResizeOptions:
    preserve_aspect: bool = True
    allow_upscaling: bool = False
    skip_existing: bool = True
    percentage: float = 100
    max_bytes: int | None = None
    allow_resolution_reduction: bool = False
    min_quality: int = 60


@dataclass(frozen=True)
class ResizeSummary:
    total: int
    succeeded: int
    failed: int
    cancelled: bool
    skipped: int = 0


def _target_size(image: Image.Image, width: int, height: int, mode: str, options: ResizeOptions) -> tuple[int, int]:
    mode = MODE_ALIASES.get(mode, mode)
    if mode == "Percentage":
        if options.percentage <= 0 or options.percentage > 1000:
            raise ValueError("Percentage must be between 0 and 1000")
        return max(1, round(image.width * options.percentage / 100)), max(1, round(image.height * options.percentage / 100))
    if mode == "Width only":
        if width < 1:
            raise ValueError("Width must be positive")
        return width, max(1, round(image.height * width / image.width))
    if mode == "Height only":
        if height < 1:
            raise ValueError("Height must be positive")
        return max(1, round(image.width * height / image.height)), height
    if not 1 <= width <= 20000 or not 1 <= height <= 20000:
        raise ValueError("Width and height must be from 1 to 20000 pixels")
    if mode in {"Exact", "Fill"}:
        return (width, height)
    if mode == "Fit":
        scale = min(width / image.width, height / image.height)
        return max(1, round(image.width * scale)), max(1, round(image.height * scale))
    raise ValueError(f"Unknown resize mode: {mode}")


def resize_batch(
    input_dir: str | Path,
    output_dir: str | Path,
    width: int,
    height: int,
    mode: str,
    log: LogCallback,
    progress: ProgressCallback,
    cancel: Event,
    options: ResizeOptions | None = None,
) -> ResizeSummary:
    # The prototype's positional API always allowed exact resizing; keep that
    # behaviour when no new options object is supplied.
    options = options or ResizeOptions(allow_upscaling=True)
    files = list_images(input_dir)
    if not files:
        raise ValueError("The selected folder contains no supported images")
    destination = Path(output_dir)
    destination.mkdir(parents=True, exist_ok=True)
    succeeded = failed = skipped = 0
    progress(0, len(files))

    for index, source in enumerate(files, start=1):
        if cancel.is_set():
            break
        target = destination / source.name
        if target.exists() and options.skip_existing:
            skipped += 1
            log(f"SKIP {source.name} — output already exists")
            progress(index, len(files))
            continue
        log(f"INFO [{index}/{len(files)}] {source.name} — resize started")
        try:
            with Image.open(source) as opened:
                image = ImageOps.exif_transpose(opened)
                target_size = _target_size(image, width, height, mode, options)
                if not options.allow_upscaling and (target_size[0] > image.width or target_size[1] > image.height):
                    target_size = image.size
                normalized_mode = MODE_ALIASES.get(mode, mode)
                if normalized_mode == "Fill" and target_size != image.size:
                    result = ImageOps.fit(image, target_size, Image.Resampling.LANCZOS, centering=(0.5, 0.5))
                else:
                    result = image.resize(target_size, Image.Resampling.LANCZOS) if target_size != image.size else image.copy()
                fmt = "JPEG" if source.suffix.lower() in {".jpg", ".jpeg"} else source.suffix.lstrip(".").upper()
                if fmt not in {"PNG", "JPEG", "WEBP"}:
                    fmt = "PNG"
                    target = target.with_suffix(".png")
                if options.max_bytes:
                    optimized = optimize_to_max_size(
                        result, fmt, options.max_bytes, options.allow_resolution_reduction,
                        options.min_quality, cancel=cancel
                    )
                    if not optimized.target_reached:
                        raise ValueError(optimized.warning)
                    encoded = optimized.image_bytes
                else:
                    encoded = encode_image(result, fmt)
            if cancel.is_set():
                break
            atomic_write_image(target, encoded, options.max_bytes)
            succeeded += 1
            log(f"OK {source.name} — saved {target_size[0]}×{target_size[1]}")
        except (OSError, ValueError, RuntimeError) as exc:
            failed += 1
            log(f"ERROR {source.name} — {exc}")
        progress(index, len(files))
    return ResizeSummary(len(files), succeeded, failed, cancel.is_set(), skipped)
