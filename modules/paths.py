"""Central paths for source and frozen application modes."""

from __future__ import annotations

import os
import sys
from pathlib import Path

from platformdirs import user_config_dir


APP_NAME = "PixelBatch"


def user_data_dir() -> Path:
    appdata = os.getenv("APPDATA")
    if appdata:
        return Path(appdata) / APP_NAME
    return Path(user_config_dir(APP_NAME, appauthor=False, roaming=True))


def settings_path() -> Path:
    return user_data_dir() / "settings.json"


def display_settings_path() -> str:
    return rf"%APPDATA%\{APP_NAME}\settings.json"


def logs_dir() -> Path:
    return user_data_dir() / "logs"


def cache_dir() -> Path:
    return user_data_dir() / "cache"


def temp_dir() -> Path:
    return user_data_dir() / "temp"


def resource_path(relative: str | Path) -> Path:
    """Resolve a bundled resource without using the bundle for mutable data."""
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[1]))
    return base / relative


def ensure_user_dirs() -> None:
    for path in (user_data_dir(), logs_dir(), cache_dir(), temp_dir()):
        path.mkdir(parents=True, exist_ok=True)
