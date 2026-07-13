from __future__ import annotations

import base64
import binascii

from .base import (
    GeneratedImageResult,
    GenerationOptions,
    ImageProvider,
    ProviderCapabilities,
    ProviderError,
    ProviderTestResult,
)


class OpenRouterProvider(ImageProvider):
    provider_id = "openrouter"

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}

    def test_connection(self) -> ProviderTestResult:
        self.validate_config()
        self._request("GET", f"{self.base_url}/images/models", headers=self._headers())
        return ProviderTestResult(True, "OpenRouter connection is configured and authorized", True)

    def generate_image(self, prompt: str, model: str, options: GenerationOptions) -> GeneratedImageResult:
        self.validate_config()
        payload = {"model": model, "prompt": prompt, "n": 1, "output_format": options.output_format.lower()}
        if options.size:
            payload["size"] = options.size
        response = self._request("POST", f"{self.base_url}/images", headers=self._headers(), json=payload)
        body = self._json(response)
        data = body.get("data")
        if not isinstance(data, list) or not data or not isinstance(data[0], dict):
            raise ProviderError("Selected model did not return an image. Check the model ID in Settings", "unsupported_model")
        item = data[0]
        encoded = item.get("b64_json")
        if not isinstance(encoded, str) or not encoded:
            raise ProviderError("OpenRouter returned an empty image", "invalid_response")
        try:
            image = base64.b64decode(encoded, validate=True)
        except (ValueError, binascii.Error) as exc:
            raise ProviderError("OpenRouter returned invalid image encoding", "invalid_response") from exc
        return GeneratedImageResult(
            image, item.get("media_type") or f"image/{options.output_format.lower()}", self.provider_id, model,
            request_id=response.headers.get("x-request-id"), metadata={"usage": body.get("usage", {})}
        )

    def get_supported_options(self) -> ProviderCapabilities:
        return ProviderCapabilities(frozenset({"output_format", "size", "quality", "background"}), True)

