from __future__ import annotations

import base64
import binascii
from urllib.parse import quote

from .base import GeneratedImageResult, GenerationOptions, ImageProvider, ProviderCapabilities, ProviderError, ProviderTestResult


class GoogleProvider(ImageProvider):
    provider_id = "google"

    def _headers(self) -> dict[str, str]:
        return {"x-goog-api-key": self.api_key, "Content-Type": "application/json"}

    @staticmethod
    def _model_path(model: str) -> str:
        return quote(model.removeprefix("models/"), safe="._-")

    def test_connection(self) -> ProviderTestResult:
        self.validate_config()
        self._request("GET", f"{self.base_url}/models/{self._model_path(self.model)}", headers=self._headers())
        return ProviderTestResult(True, "Google connection is configured and the model is accessible", True)

    def generate_image(self, prompt: str, model: str, options: GenerationOptions) -> GeneratedImageResult:
        self.validate_config()
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"responseModalities": ["Image"]},
        }
        response = self._request(
            "POST", f"{self.base_url}/models/{self._model_path(model)}:generateContent", headers=self._headers(), json=payload
        )
        body = self._json(response)
        candidates = body.get("candidates")
        try:
            parts = candidates[0]["content"]["parts"]
        except (IndexError, KeyError, TypeError) as exc:
            raise ProviderError("Selected model does not support image generation. Check the model ID in Settings", "unsupported_model") from exc
        for part in parts:
            inline = part.get("inlineData") or part.get("inline_data") if isinstance(part, dict) else None
            if not isinstance(inline, dict):
                continue
            encoded = inline.get("data")
            if not isinstance(encoded, str):
                continue
            try:
                image = base64.b64decode(encoded, validate=True)
            except (ValueError, binascii.Error) as exc:
                raise ProviderError("Google returned invalid image encoding", "invalid_response") from exc
            return GeneratedImageResult(
                image, inline.get("mimeType") or inline.get("mime_type") or "image/png", self.provider_id, model,
                response.headers.get("x-request-id"), metadata={"usage": body.get("usageMetadata", {})}
            )
        raise ProviderError("Google returned no image data", "invalid_response")

    def get_supported_options(self) -> ProviderCapabilities:
        return ProviderCapabilities(frozenset({"size"}), True)

