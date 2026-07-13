"""Provider contracts and shared retry/error handling."""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from threading import Event
from typing import Any
from urllib.parse import urlparse

from ..logging_service import SANITIZER


ERROR_TYPES = {
    "authentication_error",
    "authorization_error",
    "rate_limit",
    "invalid_request",
    "unsupported_model",
    "timeout",
    "network_error",
    "server_error",
    "content_policy_error",
    "invalid_response",
    "unknown_error",
}


@dataclass(frozen=True)
class GenerationOptions:
    output_format: str = "png"
    size: str | None = None
    quality: str | None = None
    background: str | None = None


@dataclass(frozen=True)
class GeneratedImageResult:
    image_bytes: bytes
    mime_type: str
    provider: str
    model: str
    request_id: str | None = None
    revised_prompt: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ProviderCapabilities:
    supported_options: frozenset[str]
    free_connection_test: bool


@dataclass(frozen=True)
class ProviderTestResult:
    success: bool
    message: str
    network_request_used: bool = False


class ProviderError(RuntimeError):
    def __init__(
        self,
        message: str,
        error_type: str = "unknown_error",
        retryable: bool = False,
        status_code: int | None = None,
    ) -> None:
        super().__init__(SANITIZER.sanitize(message))
        self.error_type = error_type if error_type in ERROR_TYPES else "unknown_error"
        self.retryable = retryable
        self.status_code = status_code


class ImageProvider(ABC):
    provider_id = "base"

    def __init__(
        self,
        config: dict[str, Any],
        api_key: str,
        cancel: Event | None = None,
        session: Any = None,
    ) -> None:
        self.config = dict(config)
        self.api_key = api_key.strip()
        self.model = str(config.get("model", "")).strip()
        self.base_url = str(config.get("base_url", "")).strip().rstrip("/")
        self.timeout = int(config.get("timeout", 360))
        self.retries = int(config.get("retries", 3))
        self.cancel = cancel or Event()
        SANITIZER.register(self.api_key)
        try:
            import requests
        except ImportError as exc:
            raise ProviderError("The requests package is not installed", "invalid_request") from exc
        self.requests = requests
        self.session = session or requests.Session()

    def validate_config(self) -> None:
        if not self.api_key:
            raise ProviderError(f"{self.provider_id}: API Key is missing", "authentication_error")
        if not self.model:
            raise ProviderError(f"{self.provider_id}: model is missing", "unsupported_model")
        parsed = urlparse(self.base_url)
        if parsed.scheme != "https" or not parsed.netloc:
            raise ProviderError("Base URL must be a valid HTTPS URL", "invalid_request")
        if not 10 <= self.timeout <= 1800:
            raise ProviderError("Timeout must be between 10 and 1800 seconds", "invalid_request")
        if not 0 <= self.retries <= 10:
            raise ProviderError("Retries must be between 0 and 10", "invalid_request")

    def _wait(self, seconds: float) -> None:
        if self.cancel.wait(seconds):
            raise ProviderError("Operation cancelled", "unknown_error")

    def _request(self, method: str, url: str, **kwargs: Any) -> Any:
        last_error: ProviderError | None = None
        for attempt in range(self.retries + 1):
            if self.cancel.is_set():
                raise ProviderError("Operation cancelled", "unknown_error")
            try:
                response = self.session.request(method, url, timeout=(20, self.timeout), **kwargs)
            except self.requests.Timeout as exc:
                error = ProviderError("Provider request timed out", "timeout", True)
                last_error = error
                if attempt < self.retries:
                    self._wait(min(2 ** (attempt + 1), 30))
                    continue
                raise error from exc
            except self.requests.RequestException as exc:
                error = ProviderError(f"Network error: {exc}", "network_error", True)
                last_error = error
                if attempt < self.retries:
                    self._wait(min(2 ** (attempt + 1), 30))
                    continue
                raise error from exc
            if response.ok:
                return response
            error = self._http_error(response)
            last_error = error
            if error.retryable and attempt < self.retries:
                retry_after = response.headers.get("Retry-After", "")
                delay = float(retry_after) if retry_after.replace(".", "", 1).isdigit() else 2 ** (attempt + 1)
                self._wait(min(delay, 30))
                continue
            raise error
        raise last_error or ProviderError("Unknown provider error")

    def _http_error(self, response: Any) -> ProviderError:
        message = ""
        try:
            payload = response.json()
            error = payload.get("error", payload) if isinstance(payload, dict) else {}
            if isinstance(error, dict):
                message = str(error.get("message") or error.get("code") or "")
            else:
                message = str(error)
        except ValueError:
            message = str(getattr(response, "text", ""))[:300]
        status = int(response.status_code)
        lowered = message.lower()
        if status == 401:
            category, retryable = "authentication_error", False
        elif status == 403:
            category, retryable = "authorization_error", False
        elif status == 429:
            category, retryable = "rate_limit", True
        elif status >= 500:
            category, retryable = "server_error", True
        elif "policy" in lowered or "safety" in lowered:
            category, retryable = "content_policy_error", False
        elif "model" in lowered and ("not" in lowered or "support" in lowered):
            category, retryable = "unsupported_model", False
        elif status == 400:
            category, retryable = "invalid_request", False
        else:
            category, retryable = "unknown_error", False
        detail = f": {message}" if message else ""
        return ProviderError(f"{self.provider_id} HTTP {status}{detail}", category, retryable, status)

    def _json(self, response: Any) -> dict[str, Any]:
        try:
            payload = response.json()
        except ValueError as exc:
            raise ProviderError("Provider returned invalid JSON", "invalid_response") from exc
        if not isinstance(payload, dict):
            raise ProviderError("Provider returned an invalid response object", "invalid_response")
        return payload

    def _download_image(self, url: str) -> tuple[bytes, str]:
        response = self._request("GET", url)
        data = bytes(response.content)
        if not data:
            raise ProviderError("Provider returned an empty image", "invalid_response")
        mime = str(response.headers.get("Content-Type", "image/png")).split(";", 1)[0]
        return data, mime

    @abstractmethod
    def test_connection(self) -> ProviderTestResult:
        raise NotImplementedError

    @abstractmethod
    def generate_image(self, prompt: str, model: str, options: GenerationOptions) -> GeneratedImageResult:
        raise NotImplementedError

    @abstractmethod
    def get_supported_options(self) -> ProviderCapabilities:
        raise NotImplementedError

    def normalize_error(self, error: Exception) -> ProviderError:
        if isinstance(error, ProviderError):
            return error
        return ProviderError(str(error), "unknown_error")

