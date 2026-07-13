"""Batch background removal powered by rembg."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from threading import Event
from typing import Callable

from io import BytesIO
from PIL import Image

from .image_io import atomic_write_image
from .image_optimizer import encode_image, optimize_to_max_size


IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tif", ".tiff"}
LogCallback = Callable[[str], None]
ProgressCallback = Callable[[int, int], None]


@dataclass(frozen=True)
class ModelInfo:
    model_id: str
    use_case: str
    speed: str
    hint: str


MODEL_INFO: dict[str, ModelInfo] = {
    "BiRefNet Portrait": ModelInfo("birefnet-portrait", "Portraits", "Medium", "High-quality hair and human contours."),
    "BiRefNet General": ModelInfo("birefnet-general", "Objects", "Medium", "Accurate general model for products and complex objects."),
    "BiRefNet General Lite": ModelInfo("birefnet-general-lite", "Objects", "Fast", "Lightweight BiRefNet for batch processing."),
    "U2Net": ModelInfo("u2net", "Objects", "Medium", "Reliable general model and a good default choice."),
    "U2Net Human Seg": ModelInfo("u2net_human_seg", "People", "Medium", "Full-body human segmentation."),
    "U2Net Cloth Seg": ModelInfo("u2net_cloth_seg", "Clothing", "Medium", "Clothing segmentation in photos of people."),
    "U2NetP": ModelInfo("u2netp", "Objects", "Very fast", "Compact model: faster but less precise on details."),
    "Silueta": ModelInfo("silueta", "Objects", "Fast", "Compact general model with small weights."),
    "ISNet General": ModelInfo("isnet-general-use", "Objects", "Medium", "General model with clean edges."),
    "ISNet Anime": ModelInfo("isnet-anime", "Illustrations", "Medium", "Optimized for anime and illustrated characters."),
    "BRIA RMBG": ModelInfo("bria-rmbg", "Objects", "Medium", "Modern general model for objects and people."),
    "BiRefNet DIS": ModelInfo("birefnet-dis", "Precise masks", "Medium", "Detailed object segmentation with precise boundaries."),
    "BiRefNet HRSOD": ModelInfo("birefnet-hrsod", "Large images", "Slow", "Salient object detection for high-resolution images."),
    "BiRefNet COD": ModelInfo("birefnet-cod", "Hidden objects", "Slow", "Model for objects that blend into the background."),
    "BiRefNet Massive": ModelInfo("birefnet-massive", "Objects", "Slow", "Heavy general model trained on a large dataset."),
    "SAM": ModelInfo("sam", "Experimental", "Slow", "Heavy general model; results depend on the scene."),
}


@dataclass(frozen=True)
class RemoveBackgroundSummary:
    total: int
    succeeded: int
    failed: int
    cancelled: bool
    skipped: int = 0


@dataclass(frozen=True)
class RemoveBackgroundOptions:
    output_format: str = "PNG"
    skip_existing: bool = True
    max_bytes: int | None = None
    allow_resolution_reduction: bool = False
    min_quality: int = 60


def list_images(folder: str | Path) -> list[Path]:
    directory = Path(folder)
    if not directory.is_dir():
        raise ValueError(f"Folder not found: {directory}")
    return sorted(
        path for path in directory.iterdir() if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS
    )


def remove_background_batch(
    input_dir: str | Path,
    output_dir: str | Path,
    model_name: str,
    log: LogCallback,
    progress: ProgressCallback,
    cancel: Event,
    options: RemoveBackgroundOptions | None = None,
) -> RemoveBackgroundSummary:
    options = options or RemoveBackgroundOptions()
    fmt = options.output_format.upper()
    if fmt not in {"PNG", "WEBP"}:
        raise ValueError("Background removal output must be PNG or WEBP to preserve transparency")
    if model_name not in MODEL_INFO:
        raise ValueError(f"Unknown rembg model: {model_name}")
    files = list_images(input_dir)
    if not files:
        raise ValueError("The selected folder contains no supported images")
    destination = Path(output_dir)
    destination.mkdir(parents=True, exist_ok=True)

    # Lazy import keeps resize/convert usable even if rembg is not installed yet.
    try:
        from rembg import new_session, remove
    except ImportError as exc:
        raise RuntimeError('rembg is not installed. Run: pip install "rembg[cpu]"') from exc

    info = MODEL_INFO[model_name]
    log(f"Loading model {model_name}. On first use, rembg may download its files…")
    session = new_session(info.model_id)
    succeeded = failed = skipped = 0
    progress(0, len(files))

    for index, source in enumerate(files, start=1):
        if cancel.is_set():
            break
        target = destination / f"{source.stem}{'.png' if fmt == 'PNG' else '.webp'}"
        if target.exists() and options.skip_existing:
            skipped += 1
            log(f"SKIP {source.name} — output already exists")
            progress(index, len(files))
            continue
            log(f"INFO [{index}/{len(files)}] Processing: {source.name}")
        try:
            result = remove(source.read_bytes(), session=session)
            with Image.open(BytesIO(result)) as opened:
                opened.load()
                image = opened.convert("RGBA")
                if options.max_bytes:
                    optimized = optimize_to_max_size(
                        image, fmt, options.max_bytes, options.allow_resolution_reduction,
                        options.min_quality, cancel=cancel
                    )
                    if not optimized.target_reached:
                        raise ValueError(optimized.warning)
                    encoded = optimized.image_bytes
                else:
                    encoded = encode_image(image, fmt)
            if cancel.is_set():
                break
            atomic_write_image(target, encoded, options.max_bytes)
            succeeded += 1
        except Exception as exc:  # rembg/onnxruntime expose several backend exceptions
            failed += 1
            log(f"ERROR {source.name}: {exc}")
        progress(index, len(files))

    return RemoveBackgroundSummary(len(files), succeeded, failed, cancel.is_set(), skipped)
