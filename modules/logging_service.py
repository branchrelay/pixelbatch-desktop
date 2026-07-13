"""Timestamped application logging with secret redaction."""

from __future__ import annotations

import logging
import re
import threading
import traceback
from datetime import datetime
from pathlib import Path
from typing import Iterable

from .paths import logs_dir


LOG_LEVELS = {"DEBUG", "INFO", "OK", "WARNING", "ERROR", "SKIP"}
_HEADER_PATTERN = re.compile(
    r"(?i)\b(authorization|proxy-authorization|cookie|set-cookie|x-api-key|x-goog-api-key)\b\s*[:=]\s*([^\s,;]+)"
)
_KEY_PATTERN = re.compile(r"(?i)\b(sk-(?:or-)?[A-Za-z0-9_-]{8,}|AIza[A-Za-z0-9_-]{16,})\b")


class SecretSanitizer:
    def __init__(self, secrets: Iterable[str] = ()) -> None:
        self._lock = threading.Lock()
        self._secrets = {secret for secret in secrets if secret}

    def register(self, secret: str) -> None:
        if secret:
            with self._lock:
                self._secrets.add(secret)

    def sanitize(self, value: object) -> str:
        text = str(value)
        with self._lock:
            secrets = sorted(self._secrets, key=len, reverse=True)
        for secret in secrets:
            text = text.replace(secret, "[REDACTED]")
        text = _HEADER_PATTERN.sub(lambda match: f"{match.group(1)}: [REDACTED]", text)
        return _KEY_PATTERN.sub("[REDACTED]", text)


SANITIZER = SecretSanitizer()


def sanitize_message(value: object, secrets: Iterable[str] = ()) -> str:
    local = SecretSanitizer(secrets)
    return local.sanitize(SANITIZER.sanitize(value))


def format_log(message: object, level: str = "INFO") -> str:
    normalized = level.upper() if level.upper() in LOG_LEVELS else "INFO"
    return f"[{datetime.now():%H:%M:%S}] {normalized} {SANITIZER.sanitize(message)}"


class LoggingService:
    """Write sanitized technical logs and return UI-ready messages."""

    def __init__(self, directory: Path | None = None) -> None:
        directory = directory or logs_dir()
        directory.mkdir(parents=True, exist_ok=True)
        self.path = directory / f"pixelbatch-{datetime.now():%Y-%m-%d}.log"
        self._logger = logging.getLogger(f"pixelbatch-{id(self)}")
        self._logger.setLevel(logging.DEBUG)
        self._logger.propagate = False
        handler = logging.FileHandler(self.path, encoding="utf-8")
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
        self._logger.addHandler(handler)

    def write(self, message: object, level: str = "INFO") -> str:
        cleaned = SANITIZER.sanitize(message)
        method = getattr(self._logger, "warning" if level == "WARNING" else level.lower(), self._logger.info)
        method(cleaned)
        return format_log(cleaned, level)

    def exception(self, error: BaseException) -> str:
        cleaned = SANITIZER.sanitize("".join(traceback.format_exception(error)))
        self._logger.error(cleaned)
        return format_log(error, "ERROR")
