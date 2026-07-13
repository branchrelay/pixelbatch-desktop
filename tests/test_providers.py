import base64
import sys
from io import BytesIO
from types import SimpleNamespace

import pytest
from PIL import Image

from modules.providers import GenerationOptions, ProviderError, ProviderFactory


class FakeResponse:
    def __init__(self, payload=None, content=b"", status=200, headers=None) -> None:
        self.payload = payload
        self.content = content
        self.status_code = status
        self.headers = headers or {}
        self.text = ""

    @property
    def ok(self) -> bool:
        return 200 <= self.status_code < 300

    def json(self):
        return self.payload


class FakeSession:
    def __init__(self, responses) -> None:
        self.responses = list(responses)
        self.calls = []

    def request(self, method, url, **kwargs):
        self.calls.append((method, url, kwargs))
        return self.responses.pop(0)


@pytest.fixture(autouse=True)
def fake_requests(monkeypatch):
    class RequestException(Exception):
        """Fake requests base error."""

    class Timeout(RequestException):
        """Fake requests timeout."""

    module = SimpleNamespace(Session=lambda: FakeSession([]), RequestException=RequestException, Timeout=Timeout)
    monkeypatch.setitem(sys.modules, "requests", module)


def png_bytes() -> bytes:
    buffer = BytesIO()
    Image.new("RGB", (2, 2), "red").save(buffer, "PNG")
    return buffer.getvalue()


@pytest.mark.parametrize("provider_id", ["openrouter", "openai", "google", "alibaba"])
def test_factory(provider_id: str) -> None:
    class Settings:
        def provider_config(self, _provider):
            return {"model": "model", "base_url": "https://provider.example/v1", "timeout": 30, "retries": 0}

        def api_key(self, _provider):
            return "secret"

    assert ProviderFactory.create(provider_id, Settings(), session=FakeSession([])).provider_id == provider_id


def test_openrouter_adapter() -> None:
    encoded = base64.b64encode(png_bytes()).decode()
    session = FakeSession([FakeResponse({"data": [{"b64_json": encoded}]})])
    provider = ProviderFactory.PROVIDERS["openrouter"](
        {"model": "vendor/image", "base_url": "https://openrouter.ai/api/v1", "timeout": 30, "retries": 0},
        "or-key", session=session
    )
    result = provider.generate_image("prompt", provider.model, GenerationOptions())
    assert result.image_bytes == png_bytes()
    assert session.calls[0][2]["headers"]["Authorization"] == "Bearer or-key"


def test_openai_and_google_response_parsing() -> None:
    encoded = base64.b64encode(png_bytes()).decode()
    openai = ProviderFactory.PROVIDERS["openai"](
        {"model": "gpt-image-2", "base_url": "https://api.openai.com/v1", "timeout": 30, "retries": 0},
        "openai-key", session=FakeSession([FakeResponse({"data": [{"b64_json": encoded}]})])
    )
    assert openai.generate_image("prompt", openai.model, GenerationOptions()).provider == "openai"
    google_session = FakeSession([FakeResponse({"candidates": [{"content": {"parts": [{"inlineData": {"data": encoded, "mimeType": "image/png"}}]}}]})])
    google = ProviderFactory.PROVIDERS["google"](
        {"model": "gemini-image", "base_url": "https://generativelanguage.googleapis.com/v1", "timeout": 30, "retries": 0},
        "google-key", session=google_session
    )
    assert google.generate_image("prompt", google.model, GenerationOptions()).mime_type == "image/png"
    assert "x-goog-api-key" in google_session.calls[0][2]["headers"]


def test_alibaba_sync_and_auth_error() -> None:
    body = {"output": {"choices": [{"message": {"content": [{"type": "image", "image": "https://cdn.example/image.png"}]}}]}, "request_id": "r1"}
    session = FakeSession([FakeResponse(body), FakeResponse(content=png_bytes(), headers={"Content-Type": "image/png"})])
    provider = ProviderFactory.PROVIDERS["alibaba"](
        {"model": "wan2.6-t2i", "base_url": "https://dashscope-us.aliyuncs.com/api/v1", "timeout": 30, "retries": 0},
        "ali-key", session=session
    )
    assert provider.generate_image("prompt", provider.model, GenerationOptions()).request_id == "r1"
    bad = ProviderFactory.PROVIDERS["openai"](
        {"model": "gpt-image-2", "base_url": "https://api.openai.com/v1", "timeout": 30, "retries": 0},
        "bad-key", session=FakeSession([FakeResponse({"error": {"message": "bad key"}}, status=401)])
    )
    with pytest.raises(ProviderError) as captured:
        bad.generate_image("prompt", bad.model, GenerationOptions())
    assert captured.value.error_type == "authentication_error"
