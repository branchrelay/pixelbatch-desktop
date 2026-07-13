from pathlib import Path

import pytest

from modules.csv_processor import CsvSelection, CsvValidationError, load_csv, preview_csv


def write_csv(tmp_path: Path, rows: int = 12, bom: bool = False) -> Path:
    path = tmp_path / "images.csv"
    text = "filename,prompt\n" + "".join(f"image_{i}.png,Prompt {i}\n" for i in range(1, rows + 1))
    path.write_text(text, encoding="utf-8-sig" if bom else "utf-8")
    return path


@pytest.mark.parametrize("bom", [False, True])
def test_utf8_and_bom(tmp_path: Path, bom: bool) -> None:
    assert len(load_csv(write_csv(tmp_path, bom=bom))) == 12


def test_first_n_and_header_numbering(tmp_path: Path) -> None:
    preview = preview_csv(write_csv(tmp_path), CsvSelection("First N rows", first_n=5))
    assert [row.row_number for row in preview.selected_rows] == [1, 2, 3, 4, 5]


def test_inclusive_range_and_skip(tmp_path: Path) -> None:
    preview = preview_csv(
        write_csv(tmp_path), CsvSelection("Row range", from_row=5, to_row=10, skip_first_rows=6)
    )
    assert [row.row_number for row in preview.selected_rows] == [7, 8, 9, 10]


@pytest.mark.parametrize(
    "selection",
    [CsvSelection("Row range", from_row=0, to_row=2), CsvSelection("Row range", from_row=5, to_row=4)],
)
def test_invalid_range(tmp_path: Path, selection: CsvSelection) -> None:
    with pytest.raises(CsvValidationError):
        preview_csv(write_csv(tmp_path), selection)


def test_range_past_end_is_not_silent(tmp_path: Path) -> None:
    with pytest.raises(CsvValidationError, match="Last available row: 12"):
        preview_csv(write_csv(tmp_path), CsvSelection("Row range", from_row=5, to_row=20))


def test_missing_columns(tmp_path: Path) -> None:
    path = tmp_path / "bad.csv"
    path.write_text("name,text\na,b\n", encoding="utf-8")
    with pytest.raises(CsvValidationError, match="filename"):
        load_csv(path)


def test_empty_duplicate_and_safe_filename(tmp_path: Path) -> None:
    path = tmp_path / "mixed.csv"
    path.write_text(
        'filename,prompt\n../item:1.png,Good\nitem_1.png,Duplicate\nmissing.png,""\n,No name\n', encoding="utf-8"
    )
    preview = preview_csv(path, CsvSelection())
    assert preview.selected_rows[0].filename == "item_1.png"
    assert len(preview.invalid_rows) == 3
    assert "duplicate" in preview.invalid_rows[0].error.lower()


def test_custom_prompt_column_and_template(tmp_path: Path) -> None:
    path = tmp_path / "custom.csv"
    path.write_text("filename,description,brand\nitem.png,Red cup,Acme\n", encoding="utf-8")
    preview = preview_csv(path, CsvSelection(), "description", "{brand}: {description}")
    assert preview.valid_rows[0].prompt == "Acme: Red cup"
