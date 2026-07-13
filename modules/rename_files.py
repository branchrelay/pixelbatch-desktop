"""Preview and execute safe batch file renaming."""

from __future__ import annotations

import re
import shutil
import uuid
from dataclasses import dataclass
from pathlib import Path
from threading import Event
from typing import Callable, Iterable


IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tif", ".tiff", ".gif", ".avif"}
INVALID_NAME_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
WINDOWS_RESERVED_NAMES = {
    "CON", "PRN", "AUX", "NUL",
    *(f"COM{index}" for index in range(1, 10)),
    *(f"LPT{index}" for index in range(1, 10)),
}

LogCallback = Callable[[str], None]
ProgressCallback = Callable[[int, int], None]


@dataclass(frozen=True)
class RenameOptions:
    prefix: str = ""
    suffix: str = ""
    remove_text: str = ""
    remove_case_sensitive: bool = False
    remove_first_only: bool = False
    find_text: str = ""
    replace_text: str = ""
    replace_case_sensitive: bool = False
    replace_all: bool = True
    case_mode: str = "None"
    normalize_separators: bool = False
    extension_lowercase: bool = False
    numbering_enabled: bool = False
    numbering_base: str = "product_"
    start_number: int = 1
    number_step: int = 1
    number_padding: int = 3


@dataclass(frozen=True)
class RenamePreviewItem:
    source_path: Path
    destination_path: Path
    old_name: str
    new_name: str
    selected: bool
    status: str
    error: str | None = None


@dataclass(frozen=True)
class RenameSummary:
    total: int
    succeeded: int
    failed: int
    cancelled: bool
    skipped: int = 0


def _replace_text(value: str, old: str, new: str, *, case_sensitive: bool, replace_all: bool) -> str:
    if not old:
        return value
    count = 0 if replace_all else 1
    if case_sensitive:
        return value.replace(old, new, count)
    return re.sub(re.escape(old), lambda _match: new, value, count=count, flags=re.IGNORECASE)


def _remove_text(value: str, text: str, *, case_sensitive: bool, first_only: bool) -> str:
    return _replace_text(value, text, "", case_sensitive=case_sensitive, replace_all=not first_only)


def normalize_separators(value: str) -> str:
    cleaned = re.sub(r"[\s\-]+", "_", value.strip())
    cleaned = re.sub(r"_+", "_", cleaned)
    return cleaned.strip("_")


def sanitize_filename_part(value: str) -> str:
    cleaned = INVALID_NAME_CHARS.sub("_", value)
    cleaned = cleaned.strip(" .")
    return cleaned


def is_reserved_windows_name(stem: str) -> bool:
    return stem.split(".", 1)[0].upper() in WINDOWS_RESERVED_NAMES


def validate_filename(name: str) -> str | None:
    if not name or name in {".", ".."}:
        return "New filename is empty"
    if INVALID_NAME_CHARS.search(name):
        return "New filename contains invalid characters"
    if name.rstrip(" .") != name:
        return "New filename ends with a space or dot"
    if name.startswith(".") and name.count(".") == 1:
        return "New filename has an empty name"
    stem = Path(name).stem
    if not stem or not stem.strip(". "):
        return "New filename has an empty name"
    if is_reserved_windows_name(stem):
        return "New filename uses a reserved Windows name"
    if len(name) > 240:
        return "New filename is too long"
    return None


def build_new_filename(original_path: Path, options: RenameOptions, index: int) -> str:
    stem = original_path.stem
    suffix = original_path.suffix.lower() if options.extension_lowercase else original_path.suffix

    stem = _remove_text(
        stem,
        options.remove_text,
        case_sensitive=options.remove_case_sensitive,
        first_only=options.remove_first_only,
    )
    stem = _replace_text(
        stem,
        options.find_text,
        options.replace_text,
        case_sensitive=options.replace_case_sensitive,
        replace_all=options.replace_all,
    )

    if options.case_mode == "Lowercase":
        stem = stem.lower()
    elif options.case_mode == "Uppercase":
        stem = stem.upper()
    elif options.case_mode == "Title Case":
        stem = stem.title()

    if options.normalize_separators:
        stem = normalize_separators(stem)

    stem = f"{options.prefix}{stem}{options.suffix}"

    if options.numbering_enabled:
        number = options.start_number + index * options.number_step
        stem = f"{options.numbering_base}{number:0{options.number_padding}d}"

    stem = sanitize_filename_part(stem)
    return f"{stem}{suffix}"


def parse_custom_extensions(value: str) -> set[str]:
    extensions: set[str] = set()
    for raw in re.split(r"[,\s;]+", value):
        item = raw.strip().lower()
        if not item:
            continue
        if not item.startswith("."):
            item = f".{item}"
        extensions.add(item)
    return extensions


def collect_files(
    paths: Iterable[str | Path],
    *,
    include_subfolders: bool = False,
    extension_mode: str = "Images",
    custom_extensions: str = "",
) -> list[Path]:
    if extension_mode == "All files":
        allowed: set[str] | None = None
    elif extension_mode == "Custom extensions":
        allowed = parse_custom_extensions(custom_extensions)
    else:
        allowed = IMAGE_EXTENSIONS

    collected: list[Path] = []
    seen: set[Path] = set()
    for raw in paths:
        path = Path(raw)
        candidates: Iterable[Path]
        if path.is_dir():
            candidates = path.rglob("*") if include_subfolders else path.iterdir()
        elif path.is_file():
            candidates = [path]
        else:
            continue
        for candidate in candidates:
            if not candidate.is_file():
                continue
            if allowed is not None and candidate.suffix.lower() not in allowed:
                continue
            resolved = candidate.resolve()
            if resolved not in seen:
                seen.add(resolved)
                collected.append(candidate)
    return sorted(collected, key=lambda item: str(item).casefold())


def _copy_destination(source: Path, output_dir: Path, new_name: str, source_root: Path | None) -> Path:
    if source_root:
        try:
            relative_parent = source.parent.relative_to(source_root).parent if source.parent == source_root else source.parent.relative_to(source_root)
        except ValueError:
            relative_parent = Path()
        return output_dir / relative_parent / new_name
    return output_dir / new_name


def build_preview(
    files: Iterable[Path],
    options: RenameOptions,
    *,
    mode: str = "Create renamed copies",
    output_dir: str | Path | None = None,
    source_root: str | Path | None = None,
) -> list[RenamePreviewItem]:
    file_list = list(files)
    root = Path(source_root) if source_root else None
    output = Path(output_dir) if output_dir else None
    items: list[RenamePreviewItem] = []

    for index, source in enumerate(file_list):
        new_name = build_new_filename(source, options, index)
        if mode == "Create renamed copies":
            destination = _copy_destination(source, output or source.parent, new_name, root)
        else:
            destination = source.with_name(new_name)
        error = validate_filename(new_name)
        status = "OK"
        if error:
            status = "Error"
        elif destination == source:
            status = "Skipped"
            error = "Filename is unchanged"
        elif destination.exists() and destination.resolve() != source.resolve():
            status = "Error"
            error = "Destination already exists"
        items.append(
            RenamePreviewItem(
                source_path=source,
                destination_path=destination,
                old_name=source.name,
                new_name=new_name,
                selected=True,
                status=status,
                error=error,
            )
        )

    destinations: dict[Path, int] = {}
    for item in items:
        destinations[item.destination_path.resolve()] = destinations.get(item.destination_path.resolve(), 0) + 1
    fixed: list[RenamePreviewItem] = []
    for item in items:
        if destinations[item.destination_path.resolve()] > 1 and item.status != "Skipped":
            fixed.append(
                RenamePreviewItem(
                    item.source_path, item.destination_path, item.old_name, item.new_name,
                    item.selected, "Error", "Duplicate destination name",
                )
            )
        else:
            fixed.append(item)
    return fixed


def _validate_preview(items: list[RenamePreviewItem]) -> None:
    errors = [item for item in items if item.status == "Error"]
    if errors:
        first = errors[0]
        raise ValueError(f"Rename preview has conflicts: {first.old_name} -> {first.error}")


def execute_rename(
    preview_items: Iterable[RenamePreviewItem],
    *,
    mode: str,
    log: LogCallback,
    progress: ProgressCallback,
    cancel: Event,
) -> RenameSummary:
    items = [item for item in preview_items if item.selected]
    _validate_preview(items)
    total = len(items)
    progress(0, total)
    succeeded = failed = skipped = 0

    if mode == "Create renamed copies":
        for index, item in enumerate(items, start=1):
            if cancel.is_set():
                break
            if item.status == "Skipped":
                skipped += 1
                log(f"SKIP {item.old_name} — filename is unchanged")
                progress(index, total)
                continue
            try:
                item.destination_path.parent.mkdir(parents=True, exist_ok=True)
                if item.destination_path.exists():
                    raise FileExistsError("Destination already exists")
                shutil.copy2(item.source_path, item.destination_path)
                succeeded += 1
                log(f"OK {item.old_name} — copied as {item.new_name}")
            except OSError as exc:
                failed += 1
                log(f"ERROR {item.old_name} — {exc}")
            progress(index, total)
        return RenameSummary(total, succeeded, failed, cancel.is_set(), skipped)

    rename_items = [item for item in items if item.status != "Skipped"]
    temp_pairs: list[tuple[Path, Path, RenamePreviewItem]] = []
    try:
        for item in rename_items:
            temp_path = item.source_path.with_name(f".rename_tmp_{uuid.uuid4().hex}{item.source_path.suffix}")
            item.source_path.rename(temp_path)
            temp_pairs.append((temp_path, item.destination_path, item))
        for index, (temp_path, destination, item) in enumerate(temp_pairs, start=1):
            if cancel.is_set():
                break
            destination.parent.mkdir(parents=True, exist_ok=True)
            temp_path.rename(destination)
            succeeded += 1
            log(f"OK {item.old_name} — renamed to {item.new_name}")
            progress(index, total)
        skipped = total - len(rename_items)
        if skipped:
            progress(succeeded + skipped, total)
    except OSError as exc:
        failed += 1
        log(f"ERROR rename failed — {exc}")
        for temp_path, _destination, item in reversed(temp_pairs):
            if temp_path.exists() and not item.source_path.exists():
                try:
                    temp_path.rename(item.source_path)
                except OSError:
                    pass
    return RenameSummary(total, succeeded, failed, cancel.is_set(), skipped)
