from __future__ import annotations

from typing import Any

from .base import GeneratedImageResult, GenerationOptions, ImageProvider, ProviderCapabilities, ProviderError, ProviderTestResult


class AlibabaProvider(ImageProvider):
    provider_id = "alibaba"

    def _headers(self, asynchronous: bool = False) -> dict[str, str]:
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        if asynchronous:
            headers["X-DashScope-Async"] = "enable"
        return headers

    def test_connection(self) -> ProviderTestResult:
        self.validate_config()
        return ProviderTestResult(
            True,
            "Alibaba configuration is valid. A network test would create a potentially billable image, so it was not sent.",
            False,
        )

    def _sync_wan26(self, prompt: str, model: str) -> tuple[str, str | None, dict[str, Any]]:
        payload = {
            "model": model,
            "input": {"messages": [{"role": "user", "content": [{"text": prompt}]}]},
            "parameters": {"prompt_extend": True, "watermark": False, "n": 1, "size": "1280*1280"},
        }
        response = self._request(
            "POST", f"{self.base_url}/services/aigc/multimodal-generation/generation",
            headers=self._headers(), json=payload
        )
        body = self._json(response)
        if body.get("code"):
            raise ProviderError(str(body.get("message") or body["code"]), "invalid_request")
        try:
            content = body["output"]["choices"][0]["message"]["content"]
            image_url = next(item["image"] for item in content if item.get("type") == "image")
        except (KeyError, IndexError, StopIteration, TypeError) as exc:
            raise ProviderError("Alibaba returned no image URL", "invalid_response") from exc
        return image_url, body.get("request_id"), body

    def _async_legacy(self, prompt: str, model: str) -> tuple[str, str | None, dict[str, Any]]:
        payload = {"model": model, "input": {"prompt": prompt}, "parameters": {"n": 1}}
        response = self._request(
            "POST", f"{self.base_url}/services/aigc/text2image/image-synthesis",
            headers=self._headers(True), json=payload
        )
        body = self._json(response)
        try:
            task_id = body["output"]["task_id"]
        except (KeyError, TypeError) as exc:
            raise ProviderError(str(body.get("message") or "Alibaba did not return a task ID"), "invalid_response") from exc
        for _ in range(max(1, self.timeout // 2)):
            self._wait(2)
            result = self._json(self._request("GET", f"{self.base_url}/tasks/{task_id}", headers=self._headers()))
            output = result.get("output", {})
            status = output.get("task_status")
            if status == "SUCCEEDED":
                try:
                    return output["results"][0]["url"], result.get("request_id"), result
                except (KeyError, IndexError, TypeError) as exc:
                    raise ProviderError("Alibaba task completed without an image URL", "invalid_response") from exc
            if status in {"FAILED", "CANCELED", "UNKNOWN"}:
                raise ProviderError(str(output.get("message") or f"Alibaba task {status}"), "server_error")
        raise ProviderError("Alibaba image task timed out", "timeout", True)

    def generate_image(self, prompt: str, model: str, options: GenerationOptions) -> GeneratedImageResult:
        self.validate_config()
        if model.startswith("wan2.6"):
            url, request_id, body = self._sync_wan26(prompt, model)
        else:
            url, request_id, body = self._async_legacy(prompt, model)
        image, mime = self._download_image(url)
        return GeneratedImageResult(image, mime, self.provider_id, model, request_id, metadata={"usage": body.get("usage", {})})

    def get_supported_options(self) -> ProviderCapabilities:
        return ProviderCapabilities(frozenset({"size"}), False)

