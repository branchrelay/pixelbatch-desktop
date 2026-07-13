from pathlib import Path

from modules.logging_service import LoggingService, SANITIZER, sanitize_message


def test_known_secrets_and_headers_are_redacted(tmp_path: Path) -> None:
    secret = "sk-or-v1-this-is-a-secret-key"
    SANITIZER.register(secret)
    logger = LoggingService(tmp_path)
    ui_line = logger.write(f"Authorization: Bearer {secret} x-goog-api-key={secret}", "ERROR")
    disk = logger.path.read_text(encoding="utf-8")
    assert secret not in ui_line
    assert secret not in disk
    assert "[REDACTED]" in ui_line


def test_exception_text_is_sanitized() -> None:
    secret = "sk-1234567890SECRET"
    assert secret not in sanitize_message(RuntimeError(f"failed with {secret}"), [secret])

