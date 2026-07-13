import json
from pathlib import Path

from modules.paths import display_settings_path, settings_path
from modules.settings import CredentialStoreError, SettingsManager


class FakeCredentials:
    available = True
    error = ""

    def __init__(self, fail: bool = False) -> None:
        self.values: dict[str, str] = {}
        self.fail = fail

    def get(self, provider_id: str) -> str:
        return self.values.get(provider_id, "")

    def set(self, provider_id: str, value: str, persist: bool = True) -> bool:
        self.values[provider_id] = value
        if self.fail and persist:
            raise CredentialStoreError("unavailable")
        return persist

    def delete(self, provider_id: str) -> None:
        self.values.pop(provider_id, None)


def test_defaults_and_provider_settings(tmp_path: Path) -> None:
    manager = SettingsManager(tmp_path / "settings.json", FakeCredentials())
    assert manager.active_provider_id() == "openrouter"
    assert manager.path.exists()
    manager.update_provider("google", model="custom-image-model", timeout=120, retries=2)
    manager.update(active_provider="google")
    manager.save()
    loaded = SettingsManager(manager.path, FakeCredentials())
    assert loaded.active_provider_id() == "google"
    assert loaded.provider_config("google")["model"] == "custom-image-model"


def test_language_is_validated_and_persisted(tmp_path: Path) -> None:
    manager = SettingsManager(tmp_path / "settings.json", FakeCredentials())
    assert manager.get("language") == "ru"
    manager.update(language="en")
    manager.save()
    assert SettingsManager(manager.path, FakeCredentials()).get("language") == "en"
    manager.update(language="unsupported")
    assert manager.get("language") == "en"


def test_legacy_migration_removes_key_from_json(tmp_path: Path) -> None:
    path = tmp_path / "settings.json"
    path.write_text(json.dumps({"openrouter_api_key": "legacy-secret", "openrouter_model": "legacy/model"}), encoding="utf-8")
    credentials = FakeCredentials()
    manager = SettingsManager(path, credentials)
    assert manager.provider_config("openrouter")["model"] == "legacy/model"
    assert credentials.get("openrouter") == "legacy-secret"
    assert "legacy-secret" not in path.read_text(encoding="utf-8")


def test_corrupt_json_creates_backup(tmp_path: Path) -> None:
    path = tmp_path / "settings.json"
    path.write_text("{bad", encoding="utf-8")
    manager = SettingsManager(path, FakeCredentials())
    assert manager.migration_warning
    assert (tmp_path / "settings.corrupt.json.bak").exists()


def test_api_key_never_serialized(tmp_path: Path) -> None:
    credentials = FakeCredentials()
    manager = SettingsManager(tmp_path / "settings.json", credentials)
    credentials.set("openai", "top-secret")
    manager.save()
    assert "top-secret" not in manager.path.read_text(encoding="utf-8")


def test_settings_path_uses_roaming_appdata_without_duplicate_app_name(
    tmp_path: Path, monkeypatch
) -> None:
    appdata = tmp_path / "Roaming"
    monkeypatch.setenv("APPDATA", str(appdata))
    assert settings_path() == appdata / "PixelBatch" / "settings.json"
    assert "PixelBatch" not in str(settings_path().parent.parent.name)
    assert display_settings_path() == r"%APPDATA%\PixelBatch\settings.json"
