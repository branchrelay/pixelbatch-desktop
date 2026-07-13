"""Versioned local settings and Windows Credential Manager integration."""

from __future__ import annotations

import json
import shutil
from copy import deepcopy
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any

from .logging_service import SANITIZER
from .paths import APP_NAME, settings_path


SCHEMA_VERSION = 3
PROVIDER_NAMES = {
    "openrouter": "OpenRouter",
    "openai": "OpenAI",
    "google": "Google",
    "alibaba": "Alibaba Cloud",
}
DEFAULT_PROVIDERS: dict[str, dict[str, Any]] = {
    "openrouter": {
        "model": "openai/gpt-5-image-mini",
        "base_url": "https://openrouter.ai/api/v1",
        "timeout": 360,
        "retries": 3,
    },
    "openai": {
        "model": "gpt-image-2",
        "base_url": "https://api.openai.com/v1",
        "timeout": 360,
        "retries": 3,
    },
    "google": {
        "model": "gemini-3.1-flash-image",
        "base_url": "https://generativelanguage.googleapis.com/v1",
        "timeout": 360,
        "retries": 3,
    },
    "alibaba": {
        "model": "wan2.6-t2i",
        "base_url": "https://dashscope-us.aliyuncs.com/api/v1",
        "timeout": 360,
        "retries": 3,
    },
}
DEFAULT_SETTINGS: dict[str, Any] = {
    "schema_version": SCHEMA_VERSION,
    "active_provider": "openrouter",
    "providers": DEFAULT_PROVIDERS,
    "appearance_mode": "System",
    "language": "ru",
    "ui": {
        "csv_mode": "All rows",
        "first_n": 5,
        "from_row": 1,
        "to_row": 10,
        "skip_first_rows": 0,
        "output_format": "PNG",
        "background_color": "#FFFFFF",
        "rembg_model": "BiRefNet General",
    },
}


class CredentialStoreError(RuntimeError):
    """A provider key could not be persisted in the OS credential store."""


class CredentialStore:
    """Keep provider secrets in keyring, with explicit session-only fallback."""

    def __init__(self, service_name: str = APP_NAME) -> None:
        self.service_name = service_name
        self._session: dict[str, str] = {}
        self.available = False
        self.error = ""
        try:
            import keyring
            from keyring.errors import KeyringError

            self._keyring = keyring
            self._keyring_error = KeyringError
            backend = keyring.get_keyring()
            self.available = getattr(backend, "priority", 0) > 0
            if not self.available:
                self.error = "Windows Credential Manager backend is unavailable"
        except Exception as exc:
            self._keyring = None
            self._keyring_error = Exception
            self.error = f"keyring is unavailable: {exc}"

    @staticmethod
    def account(provider_id: str) -> str:
        return f"provider_{provider_id}"

    def get(self, provider_id: str) -> str:
        if provider_id in self._session:
            return self._session[provider_id]
        if not self.available or self._keyring is None:
            return ""
        try:
            value = self._keyring.get_password(self.service_name, self.account(provider_id)) or ""
        except self._keyring_error as exc:
            self.error = str(exc)
            return ""
        if value:
            self._session[provider_id] = value
            SANITIZER.register(value)
        return value

    def set(self, provider_id: str, api_key: str, persist: bool = True) -> bool:
        key = api_key.strip()
        if key:
            self._session[provider_id] = key
            SANITIZER.register(key)
        else:
            self._session.pop(provider_id, None)
        if not persist:
            return False
        if not self.available or self._keyring is None:
            raise CredentialStoreError(self.error or "Windows Credential Manager is unavailable")
        try:
            if key:
                self._keyring.set_password(self.service_name, self.account(provider_id), key)
            else:
                self.delete(provider_id)
        except self._keyring_error as exc:
            raise CredentialStoreError(f"Credential Manager error: {exc}") from exc
        return True

    def delete(self, provider_id: str) -> None:
        self._session.pop(provider_id, None)
        if not self.available or self._keyring is None:
            return
        try:
            self._keyring.delete_password(self.service_name, self.account(provider_id))
        except self._keyring_error:
            # Missing credentials are already the desired state.
            return


class SettingsManager:
    """Load, validate, migrate and atomically save non-secret settings."""

    def __init__(self, path: Path | None = None, credentials: CredentialStore | None = None) -> None:
        self.path = path or settings_path()
        self.credentials = credentials or CredentialStore()
        self._values = deepcopy(DEFAULT_SETTINGS)
        self.migration_warning = ""
        existed = self.path.exists()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.load()
        if not existed and not self.path.exists():
            self.save()

    def load(self) -> dict[str, Any]:
        self._values = deepcopy(DEFAULT_SETTINGS)
        if not self.path.exists():
            return deepcopy(self._values)
        try:
            parsed = json.loads(self.path.read_text(encoding="utf-8"))
            if not isinstance(parsed, dict):
                raise ValueError("settings root must be an object")
        except (OSError, json.JSONDecodeError, ValueError):
            backup = self.path.with_name(f"{self.path.stem}.corrupt{self.path.suffix}.bak")
            backup_note = f"backup: {backup}"
            try:
                shutil.copy2(self.path, backup)
            except OSError as exc:
                backup_note = f"backup failed: {exc}"
            self.migration_warning = f"Damaged settings were reset; {backup_note}"
            return deepcopy(self._values)

        self._merge_valid(parsed)
        legacy_key = parsed.get("openrouter_api_key")
        legacy_model = parsed.get("openrouter_model")
        changed = False
        if isinstance(legacy_model, str) and legacy_model.strip():
            self._values["providers"]["openrouter"]["model"] = legacy_model.strip()
            changed = True
        if isinstance(legacy_key, str) and legacy_key.strip():
            try:
                self.credentials.set("openrouter", legacy_key)
            except CredentialStoreError as exc:
                self.credentials.set("openrouter", legacy_key, persist=False)
                self.migration_warning = f"Legacy OpenRouter key is session-only: {exc}"
            changed = True
        if changed or parsed.get("schema_version") != SCHEMA_VERSION:
            try:
                self.save()
            except OSError:
                self.migration_warning = self.migration_warning or "Settings migration could not be saved"
        return deepcopy(self._values)

    def _merge_valid(self, parsed: dict[str, Any]) -> None:
        provider = parsed.get("active_provider")
        if provider in PROVIDER_NAMES:
            self._values["active_provider"] = provider
        appearance = parsed.get("appearance_mode")
        if appearance in {"System", "Light", "Dark"}:
            self._values["appearance_mode"] = appearance
        language = parsed.get("language")
        if language in {"ru", "en"}:
            self._values["language"] = language
        providers = parsed.get("providers")
        if isinstance(providers, dict):
            for provider_id, defaults in DEFAULT_PROVIDERS.items():
                raw = providers.get(provider_id)
                if not isinstance(raw, dict):
                    continue
                for key in ("model", "base_url"):
                    if isinstance(raw.get(key), str) and raw[key].strip():
                        self._values["providers"][provider_id][key] = raw[key].strip()
                for key, low, high in (("timeout", 10, 1800), ("retries", 0, 10)):
                    if isinstance(raw.get(key), int) and low <= raw[key] <= high:
                        self._values["providers"][provider_id][key] = raw[key]
        ui = parsed.get("ui")
        if isinstance(ui, dict):
            for key, default in self._values["ui"].items():
                value = ui.get(key)
                if isinstance(value, type(default)):
                    self._values["ui"][key] = value

    def get(self, key: str, default: Any = None) -> Any:
        if key == "openrouter_model":
            return self._values["providers"]["openrouter"]["model"]
        if key == "openrouter_api_key":
            return self.credentials.get("openrouter")
        return self._values.get(key, default)

    def active_provider_id(self) -> str:
        return self._values["active_provider"]

    def provider_config(self, provider_id: str | None = None) -> dict[str, Any]:
        selected = provider_id or self.active_provider_id()
        return deepcopy(self._values["providers"][selected])

    def api_key(self, provider_id: str | None = None) -> str:
        return self.credentials.get(provider_id or self.active_provider_id())

    def update_provider(self, provider_id: str, **values: Any) -> None:
        if provider_id not in PROVIDER_NAMES:
            raise ValueError(f"Unknown provider: {provider_id}")
        target = self._values["providers"][provider_id]
        if "model" in values and isinstance(values["model"], str):
            target["model"] = values["model"].strip()
        if "base_url" in values and isinstance(values["base_url"], str):
            target["base_url"] = values["base_url"].strip().rstrip("/")
        if "timeout" in values:
            target["timeout"] = max(10, min(1800, int(values["timeout"])))
        if "retries" in values:
            target["retries"] = max(0, min(10, int(values["retries"])))

    def update(self, **values: Any) -> None:
        if values.get("active_provider") in PROVIDER_NAMES:
            self._values["active_provider"] = values["active_provider"]
        if values.get("appearance_mode") in {"System", "Light", "Dark"}:
            self._values["appearance_mode"] = values["appearance_mode"]
        if values.get("language") in {"ru", "en"}:
            self._values["language"] = values["language"]
        if isinstance(values.get("ui"), dict):
            self._values["ui"].update(values["ui"])
        # Compatibility with the prototype's public method.
        if isinstance(values.get("openrouter_model"), str):
            self.update_provider("openrouter", model=values["openrouter_model"])
        if isinstance(values.get("openrouter_api_key"), str):
            try:
                self.credentials.set("openrouter", values["openrouter_api_key"])
            except CredentialStoreError as exc:
                self.credentials.set("openrouter", values["openrouter_api_key"], persist=False)
                self.migration_warning = f"OpenRouter key is session-only: {exc}"

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._values["schema_version"] = SCHEMA_VERSION
        payload = json.dumps(self._values, ensure_ascii=False, indent=2)
        temp_name: str | None = None
        try:
            with NamedTemporaryFile(
                "w", encoding="utf-8", dir=self.path.parent, prefix="settings-", suffix=".tmp", delete=False
            ) as handle:
                handle.write(payload)
                temp_name = handle.name
            Path(temp_name).replace(self.path)
        finally:
            if temp_name:
                Path(temp_name).unlink(missing_ok=True)
