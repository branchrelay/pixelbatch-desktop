"""Validated UTF-8 CSV loading and unambiguous data-row selection."""

from __future__ import annotations

import csv
import re
from dataclasses import dataclass, replace
from pathlib import Path


INVALID_FILENAME_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
SUPPORTED_SOURCE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp"}


class CsvValidationError(ValueError):
    """CSV structure, content, or selection validation failed."""


@dataclass(frozen=True)
class CsvRow:
    row_number: int
    filename: str
    prompt: str
    valid: bool = True
    error: str = ""


@dataclass(frozen=True)
class CsvSelection:
    mode: str = "All rows"
    first_n: int = 5
    from_row: int = 1
    to_row: int = 10
    skip_first_rows: int = 0


@dataclass(frozen=True)
class CsvPreview:
    total_rows: int
    selected_rows: tuple[CsvRow, ...]
    valid_rows: tuple[CsvRow, ...]
    invalid_rows: tuple[CsvRow, ...]
    row_display: str


def normalize_filename(value: str, row_number: int) -> str:
    """Return a Windows-safe basename and block traversal/absolute paths."""
    raw = value.strip()
    if not raw:
        raise CsvValidationError(f"CSV row {row_number} — empty filename")
    name = Path(raw).name
    name = INVALID_FILENAME_CHARS.sub("_", name).strip(" .")
    if not name or name in {".", ".."}:
        raise CsvValidationError(f"CSV row {row_number} — invalid filename")
    suffix = Path(name).suffix.lower()
    if suffix and suffix not in SUPPORTED_SOURCE_SUFFIXES:
        raise CsvValidationError(f"CSV row {row_number} — unsupported filename extension: {suffix}")
    return name


def load_csv(path: str | Path, prompt_column: str = "prompt", prompt_template: str = "{prompt}") -> list[CsvRow]:
    csv_path = Path(path)
    if not csv_path.is_file():
        raise CsvValidationError(f"CSV file not found: {csv_path}")
    try:
        text = csv_path.read_text(encoding="utf-8-sig")
    except UnicodeDecodeError as exc:
        raise CsvValidationError("CSV must use UTF-8 or UTF-8 BOM encoding") from exc
    try:
        dialect = csv.Sniffer().sniff(text[:4096], delimiters=",;\t")
    except csv.Error:
        dialect = csv.excel
    reader = csv.DictReader(text.splitlines(), dialect=dialect)
    if not reader.fieldnames:
        raise CsvValidationError("CSV does not contain a header")
    fields = {field.strip().lower(): field for field in reader.fieldnames if field}
    prompt_key = prompt_column.strip().lower() or "prompt"
    missing = [name for name in ("filename", prompt_key) if name not in fields]
    if missing:
        raise CsvValidationError(f"Missing required CSV columns: {', '.join(missing)}")

    rows: list[CsvRow] = []
    for row_number, raw in enumerate(reader, start=1):
        source_filename = (raw.get(fields["filename"]) or "").strip()
        values = {name: (raw.get(original) or "").strip() for name, original in fields.items()}
        try:
            prompt = prompt_template.format_map(values).strip()
        except (KeyError, ValueError) as exc:
            prompt = ""
            template_error = f"CSV row {row_number} — invalid prompt template: {exc}"
        else:
            template_error = ""
        errors: list[str] = []
        if template_error:
            errors.append(template_error)
        try:
            filename = normalize_filename(source_filename, row_number)
        except CsvValidationError as exc:
            filename = Path(source_filename).name if source_filename else ""
            errors.append(str(exc))
        if not prompt:
            errors.append(f"CSV row {row_number} — empty prompt")
        rows.append(CsvRow(row_number, filename, prompt, not errors, "; ".join(errors)))
    if not rows:
        raise CsvValidationError("CSV does not contain data rows")
    return rows


def _validate_selection(selection: CsvSelection, total: int) -> None:
    if selection.skip_first_rows < 0:
        raise CsvValidationError("Skip first rows must be zero or greater")
    if selection.mode == "First N rows" and selection.first_n < 1:
        raise CsvValidationError("Number of images must be greater than zero")
    if selection.mode == "Row range":
        if selection.from_row < 1:
            raise CsvValidationError("From row must be at least 1")
        if selection.to_row < selection.from_row:
            raise CsvValidationError("To row must be greater than or equal to From row")
        if selection.to_row > total:
            raise CsvValidationError(
                f"The selected end row is greater than the number of CSV data rows. Last available row: {total}"
            )
    if selection.mode not in {"All rows", "First N rows", "Row range"}:
        raise CsvValidationError(f"Unknown CSV processing mode: {selection.mode}")


def _format_row_numbers(numbers: list[int]) -> str:
    if not numbers:
        return "none"
    groups: list[str] = []
    start = previous = numbers[0]
    for number in numbers[1:]:
        if number == previous + 1:
            previous = number
            continue
        groups.append(str(start) if start == previous else f"{start}–{previous}")
        start = previous = number
    groups.append(str(start) if start == previous else f"{start}–{previous}")
    return ", ".join(groups)


def preview_csv(
    path: str | Path,
    selection: CsvSelection,
    prompt_column: str = "prompt",
    prompt_template: str = "{prompt}",
) -> CsvPreview:
    rows = load_csv(path, prompt_column, prompt_template)
    _validate_selection(selection, len(rows))
    candidates = [row for row in rows if row.row_number > selection.skip_first_rows]
    if selection.mode == "First N rows":
        candidates = candidates[: selection.first_n]
    elif selection.mode == "Row range":
        candidates = [row for row in candidates if selection.from_row <= row.row_number <= selection.to_row]
    if not candidates:
        raise CsvValidationError("The selected CSV range contains no rows after Skip first rows")

    seen: dict[str, int] = {}
    checked: list[CsvRow] = []
    for row in candidates:
        key = row.filename.casefold()
        if row.filename and key in seen:
            message = f"CSV row {row.row_number} — duplicate filename (first used in row {seen[key]})"
            row = replace(row, valid=False, error=f"{row.error}; {message}".strip("; "))
        elif row.filename:
            seen[key] = row.row_number
        checked.append(row)
    valid = tuple(row for row in checked if row.valid)
    invalid = tuple(row for row in checked if not row.valid)
    return CsvPreview(
        total_rows=len(rows),
        selected_rows=tuple(checked),
        valid_rows=valid,
        invalid_rows=invalid,
        row_display=_format_row_numbers([row.row_number for row in checked]),
    )
