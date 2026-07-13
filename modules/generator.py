"""Provider-independent CSV image generation pipeline."""

from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from threading import Event
from typing import Any, Callable, Iterable

from PIL import Image, ImageOps

from .csv_processor import CsvRow, CsvValidationError, load_csv, normalize_filename
from .image_io import atomic_write_image
from .image_optimizer import encode_image, optimize_to_max_size
from .providers import GenerationOptions, ProviderFactory
from .providers.openrouter_provider import OpenRouterProvider


LogCallback = Callable[[str], None]
ProgressCallback = Callable[[int, int], None]
FORMAT_SUFFIX = {"PNG": ".png", "JPG": ".jpg", "JPEG": ".jpg", "WEBP": ".webp"}


class GenerationError(RuntimeError):
    """A generation pipeline error safe to present to the user."""


@dataclass(frozen=True)
class PromptRow:
    filename: str
    prompt: str
    row_number: int = 0


@dataclass(frozen=True)
class GenerationBatchOptions:
    output_format: str = "PNG"
    skip_existing: bool = True
    max_bytes: int | None = None
    allow_resolution_reduction: bool = False
    min_quality: int = 60


@dataclass(frozen=True)
class GenerationSummary:
    total: int
    succeeded: int
    skipped: int
    failed: int
    cancelled: bool


def read_prompt_csv(path: str | Path) -> list[PromptRow]:
    """Compatibility API: strictly load every row from filename/prompt CSV."""
    try:
        rows = load_csv(path)
    except CsvValidationError as exc:
        raise GenerationError(str(exc)) from exc
    invalid = [row.error for row in rows if not row.valid]
    if invalid:
        raise GenerationError(invalid[0])
    result: list[PromptRow] = []
    for row in rows:
        filename = row.filename if Path(row.filename).suffix else f"{row.filename}.png"
        result.append(PromptRow(filename, row.prompt, row.row_number))
    return result


def _target_for(row: CsvRow | PromptRow, destination: Path, output_format: str) -> Path:
    safe = normalize_filename(row.filename, row.row_number or 1)
    return destination / f"{Path(safe).stem}{FORMAT_SUFFIX[output_format.upper()]}"


def _decode_provider_image(data: bytes) -> Image.Image:
    try:
        with Image.open(BytesIO(data)) as opened:
            opened.load()
            return ImageOps.exif_transpose(opened).copy()
    except (OSError, ValueError) as exc:
        raise GenerationError("Provider returned data that Pillow cannot open as an image") from exc


class ImageGenerationService:
    def __init__(self, settings: Any) -> None:
        self.settings = settings

    def generate_batch(
        self,
        rows: Iterable[CsvRow],
        output_dir: str | Path,
        options: GenerationBatchOptions,
        log: LogCallback,
        progress: ProgressCallback,
        cancel: Event,
    ) -> GenerationSummary:
        tasks = list(rows)
        if not tasks:
            raise GenerationError("The selected CSV range has no valid rows")
        fmt = options.output_format.upper()
        if fmt not in FORMAT_SUFFIX:
            raise GenerationError(f"Unsupported output format: {fmt}")
        provider_id = self.settings.active_provider_id()
        config = self.settings.provider_config(provider_id)
        provider = ProviderFactory.create(provider_id, self.settings, cancel=cancel)
        provider.validate_config()
        destination = Path(output_dir)
        destination.mkdir(parents=True, exist_ok=True)
        succeeded = skipped = failed = 0
        progress(0, len(tasks))

        for index, row in enumerate(tasks, start=1):
            if cancel.is_set():
                break
            target = _target_for(row, destination, fmt)
            if target.exists() and options.skip_existing:
                skipped += 1
                log(f"SKIP CSV row {row.row_number} — {target.name} — output already exists")
                progress(index, len(tasks))
                continue
            log(f"INFO CSV row {row.row_number} — {target.name} — generation started")
            try:
                generated = provider.generate_image(
                    row.prompt,
                    config["model"],
                    GenerationOptions(output_format=fmt.lower().replace("jpg", "jpeg")),
                )
                if cancel.is_set():
                    break
                image = _decode_provider_image(generated.image_bytes)
                if options.max_bytes:
                    optimized = optimize_to_max_size(
                        image,
                        fmt,
                        options.max_bytes,
                        options.allow_resolution_reduction,
                        options.min_quality,
                        cancel=cancel,
                    )
                    if not optimized.target_reached:
                        raise GenerationError(optimized.warning)
                    encoded = optimized.image_bytes
                    log(
                        f"INFO {target.name} — optimized to {optimized.final_size} bytes, "
                        f"{optimized.width}×{optimized.height}, quality={optimized.quality or 'lossless'}"
                    )
                else:
                    encoded = encode_image(image, fmt)
                if cancel.is_set():
                    break
                atomic_write_image(target, encoded, options.max_bytes)
                succeeded += 1
                log(f"OK CSV row {row.row_number} — {target.name} — saved through {provider_id}")
            except Exception as exc:
                if cancel.is_set():
                    break
                failed += 1
                error = provider.normalize_error(exc)
                log(f"ERROR CSV row {row.row_number} — {target.name} — {error}")
            progress(index, len(tasks))
        return GenerationSummary(len(tasks), succeeded, skipped, failed, cancel.is_set())


class OpenRouterImageGenerator:
    """Backward-compatible wrapper retained for the original prototype API."""

    def __init__(self, api_key: str, model: str, timeout: int = 360) -> None:
        self.provider = OpenRouterProvider(
            {"model": model, "base_url": "https://openrouter.ai/api/v1", "timeout": timeout, "retries": 3}, api_key
        )

    def generate_batch(
        self,
        rows: Iterable[PromptRow],
        output_dir: str | Path,
        log: LogCallback,
        progress: ProgressCallback,
        cancel: Event,
        skip_existing: bool = True,
    ) -> GenerationSummary:
        tasks = list(rows)
        destination = Path(output_dir)
        destination.mkdir(parents=True, exist_ok=True)
        succeeded = skipped = failed = 0
        progress(0, len(tasks))
        for index, row in enumerate(tasks, start=1):
            if cancel.is_set():
                break
            fmt = Path(row.filename).suffix.lstrip(".").upper() or "PNG"
            fmt = "JPG" if fmt == "JPEG" else fmt
            target = destination / row.filename
            if target.exists() and skip_existing:
                skipped += 1
                progress(index, len(tasks))
                continue
            try:
                result = self.provider.generate_image(
                    row.prompt, self.provider.model, GenerationOptions(output_format=fmt.lower().replace("jpg", "jpeg"))
                )
                image = _decode_provider_image(result.image_bytes)
                atomic_write_image(target, encode_image(image, fmt))
                succeeded += 1
                log(f"Saved: {target}")
            except Exception as exc:
                failed += 1
                log(f"Error {row.filename}: {self.provider.normalize_error(exc)}")
            progress(index, len(tasks))
        return GenerationSummary(len(tasks), succeeded, skipped, failed, cancel.is_set())


__all__ = [
    "CsvValidationError",
    "GenerationBatchOptions",
    "GenerationError",
    "GenerationSummary",
    "ImageGenerationService",
    "OpenRouterImageGenerator",
    "PromptRow",
    "read_prompt_csv",
]
