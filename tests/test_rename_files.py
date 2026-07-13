from __future__ import annotations

from pathlib import Path
from threading import Event

import pytest

from modules.rename_files import (
    RenameOptions,
    build_new_filename,
    build_preview,
    collect_files,
    execute_rename,
)


def touch(path: Path, content: str = "data") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def test_prefix_suffix_remove_replace_and_extension_case() -> None:
    assert build_new_filename(Path("photo.jpg"), RenameOptions(prefix="product_"), 0) == "product_photo.jpg"
    assert build_new_filename(Path("photo.jpg"), RenameOptions(suffix="_ready"), 0) == "photo_ready.jpg"
    assert build_new_filename(Path("photo_old.jpg"), RenameOptions(remove_text="_old"), 0) == "photo.jpg"
    assert build_new_filename(Path("old_photo.jpg"), RenameOptions(find_text="old", replace_text="new"), 0) == "new_photo.jpg"
    assert build_new_filename(Path("photo.JPG"), RenameOptions(prefix="product_"), 0) == "product_photo.JPG"
    assert build_new_filename(Path("photo.JPG"), RenameOptions(extension_lowercase=True), 0) == "photo.jpg"


def test_numbering_and_normalization() -> None:
    options = RenameOptions(numbering_enabled=True, numbering_base="product_", start_number=1, number_padding=3)
    assert build_new_filename(Path("IMG_5821.jpg"), options, 0) == "product_001.jpg"
    assert build_new_filename(Path("IMG_5822.jpg"), options, 1) == "product_002.jpg"
    assert build_new_filename(Path("Product Photo 01.JPG"), RenameOptions(normalize_separators=True, case_mode="Lowercase"), 0) == "product_photo_01.JPG"


def test_invalid_reserved_empty_and_duplicate_preview(tmp_path: Path) -> None:
    first = touch(tmp_path / "one.jpg")
    second = touch(tmp_path / "two.jpg")
    reserved = build_preview([first], RenameOptions(remove_text="one", prefix="CON"))
    assert reserved[0].status == "Error"
    empty = build_preview([first], RenameOptions(remove_text="one"))
    assert empty[0].status == "Error"
    duplicate = build_preview([first, second], RenameOptions(numbering_enabled=True, numbering_base="item", number_padding=0, number_step=0))
    assert [item.status for item in duplicate] == ["Error", "Error"]


def test_existing_destination_conflict(tmp_path: Path) -> None:
    source = touch(tmp_path / "photo.jpg")
    touch(tmp_path / "product_photo.jpg")
    preview = build_preview([source], RenameOptions(prefix="product_"), mode="Rename original files")
    assert preview[0].status == "Error"
    assert preview[0].error == "Destination already exists"


def test_copy_mode_preserves_source_and_metadata_destination(tmp_path: Path) -> None:
    source_dir = tmp_path / "source"
    output_dir = tmp_path / "output"
    source = touch(source_dir / "photo.jpg", "original")
    preview = build_preview([source], RenameOptions(suffix="_ready"), mode="Create renamed copies", output_dir=output_dir, source_root=source_dir)
    log: list[str] = []
    summary = execute_rename(preview, mode="Create renamed copies", log=log.append, progress=lambda *_: None, cancel=Event())
    assert summary.succeeded == 1
    assert source.exists()
    assert source.read_text(encoding="utf-8") == "original"
    assert (output_dir / "photo_ready.jpg").read_text(encoding="utf-8") == "original"


def test_original_rename_mode_uses_preview(tmp_path: Path) -> None:
    source = touch(tmp_path / "фото товара 03.jpg")
    preview = build_preview([source], RenameOptions(prefix="shop_", normalize_separators=True), mode="Rename original files")
    assert preview[0].new_name == "shop_фото_товара_03.jpg"
    summary = execute_rename(preview, mode="Rename original files", log=lambda _msg: None, progress=lambda *_: None, cancel=Event())
    assert summary.succeeded == 1
    assert not source.exists()
    assert (tmp_path / "shop_фото_товара_03.jpg").exists()


def test_collect_files_filters_and_subfolders(tmp_path: Path) -> None:
    root = tmp_path / "root"
    jpg = touch(root / "a.JPG")
    txt = touch(root / "a.txt")
    nested = touch(root / "nested" / "b.png")
    assert collect_files([root], include_subfolders=False, extension_mode="Images") == [jpg]
    assert collect_files([root], include_subfolders=True, extension_mode="Images") == [jpg, nested]
    assert collect_files([root], include_subfolders=True, extension_mode="Custom extensions", custom_extensions=".txt") == [txt]


def test_execution_refuses_preview_conflicts(tmp_path: Path) -> None:
    source = touch(tmp_path / "photo.jpg")
    touch(tmp_path / "product_photo.jpg")
    preview = build_preview([source], RenameOptions(prefix="product_"), mode="Rename original files")
    with pytest.raises(ValueError, match="conflicts"):
        execute_rename(preview, mode="Rename original files", log=lambda _msg: None, progress=lambda *_: None, cancel=Event())
