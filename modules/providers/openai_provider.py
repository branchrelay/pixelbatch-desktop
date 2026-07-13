from __future__ import annotations

import base64
import binascii

from .base import GeneratedImageResult, GenerationOptions, ImageProvider, ProviderCapabilities, ProviderError, ProviderTestResult


class OpenAIProvider(ImageProvider):
    provider_id = "openai"

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}

    def test_connection(self) -> ProviderTestResult:
        self.validate_config()
        self._request("GET", f"{self.base_url}/models/{self.model}", headers=self._headers())
        return ProviderTestResult(True, "OpenAI connection is configured and the model is accessible", True)

    def generate_image(self, prompt: str, model: str, options: GenerationOptions) -> GeneratedImageResult:
        self.validate_config()
        payload: dict[str, object] = {
            "model": model,
            "prompt": prompt,
            "n": 1,
            "output_format": options.output_format.lower().replace("jpg", "jpeg"),
        }
        if options.size:
            payload["size"] = options.size
        if options.quality:
            payload["quality"] = options.quality
        if options.background:
            payload["background"] = options.background
        response = self._request("POST", f"{self.base_url}/images/generations", headers=self._headers(), json=payload)
        body = self._json(response)
        data = body.get("data")
        if not isinstance(data, list) or not data or not isinstance(data[0], dict):
            raise ProviderError("Selected model does not support image generation. Check the model ID in Settings", "unsupported_model")
        item = data[0]
        if isinstance(item.get("b64_json"), str):
            try:
                image = base64.b64decode(item["b64_json"], validate=True)
            except (ValueError, binascii.Error) as exc:
                raise ProviderError("OpenAI returned invalid image encoding", "invalid_response") from exc
            mime = f"image/{options.output_format.lower().replace('jpg', 'jpeg')}"
        elif isinstance(item.get("url"), str):
            image, mime = self._download_image(item["url"])
        else:
            raise ProviderError("OpenAI returned an empty image", "invalid_response")
        return GeneratedImageResult(
            image, mime, self.provider_id, model, response.headers.get("x-request-id"), item.get("revised_prompt"),
            {"usage": body.get("usage", {})}
        )

    def get_supported_options(self) -> ProviderCapabilities:
        return ProviderCapabilities(frozenset({"output_format", "size", "quality", "background"}), True)

