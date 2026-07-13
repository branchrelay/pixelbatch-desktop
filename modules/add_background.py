"""Batch creation of e-commerce canvases and backgrounds."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from threading import Event
from typing import Callable

from PIL import Image

from .canvas_processor import CanvasOptions, process_canvas
from .image_io import atomic_write_image
from .image_optimizer import encode_image, optimize_to_max_size


INPUT_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp"}
FORMAT_SUFFIX = {"PNG": ".png", "JPG": ".jpg", "JPEG": ".jpg", "WEBP": ".webp"}
INVALID_SUFFIX_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
LogCallback = Callable[[str], None]
ProgressCallback = Callable[[int, int], None]


@dataclass(frozen=True)
class AddBackgroundOptions:
    canvas: CanvasOptions
    output_format: str = "PNG"
    filename_suffix: str = "_background"
    skip_existing: bool = True
    max_bytes: int | None = None
    allow_resolution_reduction: bool = False
    min_quality: int = 60


@dataclass(frozen=True)
class AddBackgroundSummary:
    total: int
    succeeded: int
    skipped: int
    failed: int
    cancelled: bool


def normalized_suffix(value: str) -> str:
    cleaned = INVALID_SUFFIX_CHARS.sub("_", value.strip()).strip(" .")
    return cleaned or "_background"


def output_name(source: Path, suffix: str, output_format: str) -> str:
    normalized = normalized_suffix(suffix)
    stem = source.stem
    if not stem.casefold().endswith(normalized.casefold()):
        stem += normalized
    return f"{stem}{FORMAT_SUFFIX[output_format.upper()]}"


def _encode_result(result: Image.Image, options: AddBackgroundOptions, cancel: Event) -> bytes:
    fmt = options.output_format.upper()
    if options.canvas.transparent and fmt in {"JPG", "JPEG"}:
        raise ValueError("JPG/JPEG cannot store a transparent background; choose PNG or WEBP")
    if options.max_bytes:
        optimized = optimize_to_max_size(
            result,
            fmt,
            options.max_bytes,
            options.allow_resolution_reduction,
            options.min_quality,
            cancel=cancel,
            background=options.canvas.background_color,
        )
        if not optimized.target_reached:
            raise ValueError(optimized.warning)
        return optimized.image_bytes
    return encode_image(result, fmt, 95, options.canvas.background_color)


def add_background_batch(
    input_dir: str | Path,
    output_dir: str | Path,
    options: AddBackgroundOptions,
    log: LogCallback,
    progress: ProgressCallback,
    cancel: Event,
) -> AddBackgroundSummary:
    source_dir = Path(input_dir)
    if not source_dir.is_dir():
        raise ValueError(f"Input folder not found: {source_dir}")
    files = sorted(path for path in source_dir.iterdir() if path.is_file() and path.suffix.lower() in INPUT_EXTENSIONS)
    if not files:
        raise ValueError("The input folder contains no PNG, JPG or WEBP images")
    destination = Path(output_dir)
    destination.mkdir(parents=True, exist_ok=True)
    succeeded = skipped = failed = 0
    progress(0, len(files))

    for index, source in enumerate(files, start=1):
        if cancel.is_set():
            break
        target = destination / output_name(source, options.filename_suffix, options.output_format)
        if target.exists() and options.skip_existing:
            skipped += 1
            log(f"SKIP {source.name} — output already exists")
            progress(index, len(files))
            continue
        if target.exists():
            counter = 2
            while target.exists():
                target = target.with_name(f"{target.stem}_{counter}{target.suffix}")
                counter += 1
        log(f"INFO [{index}/{len(files)}] {source.name} — canvas processing started")
        try:
            with Image.open(source) as image:
                result = process_canvas(image, options.canvas)
                encoded = _encode_result(result, options, cancel)
            if cancel.is_set():
                break
            atomic_write_image(target, encoded, options.max_bytes)
            succeeded += 1
            log(f"OK {source.name} — saved as {target.name}")
        except (OSError, ValueError, RuntimeError) as exc:
            failed += 1
            log(f"ERROR {source.name} — {exc}")
        progress(index, len(files))
    return AddBackgroundSummary(len(files), succeeded, skipped, failed, cancel.is_set())

