"""Batch image conversion with alpha-safe JPEG compositing."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from threading import Event
from typing import Callable

from PIL import Image, ImageOps

from .image_io import atomic_write_image
from .image_optimizer import encode_image, optimize_to_max_size


CONVERSIONS: dict[str, tuple[set[str], str, str]] = {
    "PNG → JPG": ({".png"}, ".jpg", "JPEG"),
    "JPG → PNG": ({".jpg", ".jpeg"}, ".png", "PNG"),
    "WEBP → PNG": ({".webp"}, ".png", "PNG"),
    "PNG → WEBP": ({".png"}, ".webp", "WEBP"),
    "JPG → WEBP": ({".jpg", ".jpeg"}, ".webp", "WEBP"),
    "WEBP → JPG": ({".webp"}, ".jpg", "JPEG"),
    "BMP → PNG": ({".bmp"}, ".png", "PNG"),
    "TIFF → PNG": ({".tif", ".tiff"}, ".png", "PNG"),
    "PNG → BMP": ({".png"}, ".bmp", "BMP"),
    "PNG → TIFF": ({".png"}, ".tiff", "TIFF"),
    "BMP → JPG": ({".bmp"}, ".jpg", "JPEG"),
    "TIFF → JPG": ({".tif", ".tiff"}, ".jpg", "JPEG"),
}
LogCallback = Callable[[str], None]
ProgressCallback = Callable[[int, int], None]


@dataclass(frozen=True)
class ConvertOptions:
    quality: int = 90
    background_color: str = "#FFFFFF"
    skip_existing: bool = True
    max_bytes: int | None = None
    allow_resolution_reduction: bool = False
    min_quality: int = 60


@dataclass(frozen=True)
class ConvertSummary:
    total: int
    succeeded: int
    failed: int
    cancelled: bool
    skipped: int = 0


def convert_batch(
    input_dir: str | Path,
    output_dir: str | Path,
    conversion: str,
    log: LogCallback,
    progress: ProgressCallback,
    cancel: Event,
    options: ConvertOptions | None = None,
) -> ConvertSummary:
    options = options or ConvertOptions()
    if conversion not in CONVERSIONS:
        raise ValueError("Select a valid conversion direction")
    if not 20 <= options.quality <= 95:
        raise ValueError("Quality must be between 20 and 95")
    source_extensions, target_extension, target_format = CONVERSIONS[conversion]
    directory = Path(input_dir)
    if not directory.is_dir():
        raise ValueError(f"Folder not found: {directory}")
    files = sorted(path for path in directory.iterdir() if path.is_file() and path.suffix.lower() in source_extensions)
    if not files:
        raise ValueError(f"The folder contains no files for {conversion}")
    destination = Path(output_dir)
    destination.mkdir(parents=True, exist_ok=True)
    succeeded = failed = skipped = 0
    progress(0, len(files))

    for index, source in enumerate(files, start=1):
        if cancel.is_set():
            break
        target = destination / f"{source.stem}{target_extension}"
        if target.exists() and options.skip_existing:
            skipped += 1
            log(f"SKIP {source.name} — output already exists")
            progress(index, len(files))
            continue
        if target.exists():
            counter = 2
            while target.exists():
                target = destination / f"{source.stem}_{counter}{target_extension}"
                counter += 1
        log(f"INFO [{index}/{len(files)}] {source.name} → {target.name}")
        try:
            with Image.open(source) as opened:
                image = ImageOps.exif_transpose(opened)
                if options.max_bytes:
                    optimized = optimize_to_max_size(
                        image, target_format, options.max_bytes, options.allow_resolution_reduction,
                        options.min_quality, cancel=cancel, background=options.background_color
                    )
                    if not optimized.target_reached:
                        raise ValueError(optimized.warning)
                    encoded = optimized.image_bytes
                else:
                    encoded = encode_image(image, target_format, options.quality, options.background_color)
            if cancel.is_set():
                break
            atomic_write_image(target, encoded, options.max_bytes)
            succeeded += 1
            log(f"OK {source.name} — saved as {target.name}")
        except (OSError, ValueError, RuntimeError) as exc:
            failed += 1
            log(f"ERROR {source.name} — {exc}")
        progress(index, len(files))
    return ConvertSummary(len(files), succeeded, failed, cancel.is_set(), skipped)
