from __future__ import annotations

import sys
from io import BytesIO
from pathlib import Path
from threading import Event
from types import SimpleNamespace

import pytest
import customtkinter as ctk
from PIL import Image

import app
from modules.add_background import AddBackgroundOptions, add_background_batch
from modules.canvas_processor import CanvasOptions
from modules.convert import ConvertOptions, convert_batch
from modules.remove_bg import RemoveBackgroundOptions, remove_background_batch
from modules.resize import ResizeOptions, resize_batch


EXPECTED_PAGES = {"generate", "remove", "background", "resize", "convert", "rename", "help", "settings"}


def test_sidebar_callbacks_switch_hosts_and_preserve_state(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APPDATA", str(tmp_path / "appdata"))
    window = app.ToolkitApp()
    window.withdraw()
    window.update_idletasks()
    try:
        assert set(window.pages) == EXPECTED_PAGES
        assert set(window._nav_buttons) == EXPECTED_PAGES
        assert set(window._page_hosts) == EXPECTED_PAGES
        assert window.settings.path.exists()
        assert str(window.settings.path).startswith(str(tmp_path / "appdata"))
        assert window.pages["settings"].settings_path_label.cget("text") == r"%APPDATA%\PixelBatch\settings.json"
        assert "appdata" not in window.pages["settings"].settings_path_label.cget("text")
        window.pages["generate"].csv_path.set("state-must-survive.csv")
        sequence = ["generate", "remove", "background", "resize", "convert", "rename", "help", "settings", "generate", "settings", "remove"]
        for name in sequence:
            window._nav_buttons[name].invoke()
            window.update_idletasks()
            assert window.current_page == name
            assert window.content.winfo_children()[-1] == window._page_hosts[name]
            selected = {
                key for key, button in window._nav_buttons.items() if button.cget("fg_color") != "transparent"
            }
            assert selected == {name}
        assert window.pages["generate"].csv_path.get() == "state-must-survive.csv"
        page_ids = {name: id(page) for name, page in window.pages.items()}
        window.change_language("en")
        window.update_idletasks()
        assert window.settings.get("language") == "en"
        assert window._nav_buttons["rename"].cget("text") == "Rename Files"
        assert window._nav_buttons["help"].cget("text") == "How to Use"
        assert page_ids == {name: id(page) for name, page in window.pages.items()}
        window.change_language("ru")
        window.update_idletasks()
        assert window._nav_buttons["rename"].cget("text") == "Переименование файлов"
        assert window._nav_buttons["help"].cget("text") == "Как пользоваться"
        assert window.pages["generate"].csv_path.get() == "state-must-survive.csv"
        with pytest.raises(KeyError, match="Unknown page"):
            window.navigate_to("missing")

        csv_path = tmp_path / "generation.csv"
        csv_path.write_text("filename,prompt\nitem.png,Test prompt\n", encoding="utf-8")
        generate = window.pages["generate"]
        generate.csv_path.set(str(csv_path))
        generate.output_path.set(str(tmp_path / "generated"))
        monkeypatch.setattr(window.settings.credentials, "get", lambda _provider: "")
        dialog_messages: list[str] = []
        monkeypatch.setattr(
            window,
            "show_api_key_required_dialog",
            lambda detail="": dialog_messages.append(detail) or True,
        )
        generate.start()
        window.update_idletasks()
        assert dialog_messages and "API-ключ" in dialog_messages[0]
        assert window.current_page == "settings"
        assert window._worker is None
        for appearance in ("Light", "Dark", "System"):
            ctk.set_appearance_mode(appearance)
            window._nav_buttons["remove"].invoke()
            window.update_idletasks()
            assert window.current_page == "remove"
            assert window.content.winfo_children()[-1] == window._page_hosts["remove"]
    finally:
        window.destroy()


def _png(path: Path, mode: str = "RGBA") -> None:
    color = (255, 0, 0, 180) if mode == "RGBA" else (255, 0, 0)
    Image.new(mode, (40, 20), color).save(path)


def test_local_tools_do_not_require_provider_credentials(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    source = tmp_path / "source"
    source.mkdir()
    _png(source / "item.png")
    log: list[str] = []
    progress = lambda *_args: None

    added = add_background_batch(
        source,
        tmp_path / "background",
        AddBackgroundOptions(CanvasOptions(canvas_mode="Square canvas", square_side=100)),
        log.append,
        progress,
        Event(),
    )
    assert added.succeeded == 1

    resized = resize_batch(
        source, tmp_path / "resize", 25, 25, "Fill", log.append, progress, Event(),
        ResizeOptions(allow_upscaling=True),
    )
    assert resized.succeeded == 1

    converted = convert_batch(
        source, tmp_path / "convert", "PNG → WEBP", log.append, progress, Event(), ConvertOptions()
    )
    assert converted.succeeded == 1

    buffer = BytesIO()
    Image.new("RGBA", (40, 20), (255, 0, 0, 0)).save(buffer, "PNG")
    fake_rembg = SimpleNamespace(new_session=lambda _name: object(), remove=lambda _data, session: buffer.getvalue())
    monkeypatch.setitem(sys.modules, "rembg", fake_rembg)
    removed = remove_background_batch(
        source, tmp_path / "remove", "U2Net", log.append, progress, Event(), RemoveBackgroundOptions()
    )
    assert removed.succeeded == 1
