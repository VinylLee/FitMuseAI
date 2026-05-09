from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
import time
import uuid

import requests

from src.config import AppConfig
from src.providers.base import GenerationProvider, ProviderTaskResult, TryOnRequest


STATUS_MAP = {
    "PENDING": "queued",
    "PRE-PROCESSING": "running",
    "RUNNING": "running",
    "POST-PROCESSING": "running",
    "SUCCEEDED": "success",
    "FAILED": "failed",
    "UNKNOWN": "failed",
    "CANCELED": "failed",
}


@dataclass
class AitryonResult:
    task_id: str
    status: str
    image_url: str | None
    error_code: str | None
    error_message: str | None
    raw_response: dict


class AliyunAitryonProvider(GenerationProvider):
    name = "aliyun_aitryon"
    supports_tryon = True
    supports_video = False
    requires_public_url = True

    def __init__(self, config: AppConfig, public_asset_store=None) -> None:
        super().__init__(public_asset_store)
        self._api_key = config.dashscope_api_key
        self._region = config.aliyun_region
        self._preview_model = config.aliyun_tryon_preview_model or "aitryon"
        self._high_model = config.aliyun_tryon_model or "aitryon-plus"
        self._public_url_ttl = config.public_asset_ttl_seconds
        self._api_base = self._resolve_api_base(self._region)

    def validate_environment(self) -> str | None:
        if not self._api_key:
            return "Missing config: DASHSCOPE_API_KEY"
        if self._region != "cn-beijing":
            return "AI try-on is only supported in cn-beijing region."
        if self.requires_public_url and self.public_asset_store and not self.public_asset_store.is_enabled():
            return "Public URL upload is not configured."
        return None

    def generate_tryon_image(self, request: TryOnRequest) -> ProviderTaskResult:
        error = self.validate_environment()
        if error:
            return ProviderTaskResult(
                task_id=None,
                provider=self.name,
                model="aitryon",
                status="failed",
                remote_urls=[],
                output_paths=[],
                error_message=error,
            )

        model = self._select_model(request)
        if model != "aitryon":
            return ProviderTaskResult(
                task_id=None,
                provider=self.name,
                model=model,
                status="failed",
                remote_urls=[],
                output_paths=[],
                error_message=f"Model not implemented: {model}",
            )

        try:
            person_url = self._ensure_public_url(request.person_image_path, request.person_public_url)
            garment_url = self._ensure_public_url(request.garment_image_path, request.garment_public_url)
        except RuntimeError as exc:
            return ProviderTaskResult(
                task_id=None,
                provider=self.name,
                model=model,
                status="failed",
                remote_urls=[],
                output_paths=[],
                error_message=str(exc),
            )

        category = (request.garment_category or "").strip()
        top_url = None
        bottom_url = None
        if category in {"lower_body"}:
            bottom_url = garment_url
        elif category in {"upper_body", "outerwear", "dress", "set", "other"}:
            top_url = garment_url
        elif category in {"shoes"}:
            return ProviderTaskResult(
                task_id=None,
                provider=self.name,
                model=model,
                status="failed",
                remote_urls=[],
                output_paths=[],
                error_message="Aitryon does not support shoes category.",
            )
        else:
            top_url = garment_url

        if not top_url and not bottom_url:
            return ProviderTaskResult(
                task_id=None,
                provider=self.name,
                model=model,
                status="failed",
                remote_urls=[],
                output_paths=[],
                error_message="Missing garment URL for try-on request.",
            )

        output_dir = Path(request.output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        output_paths: list[str] = []
        remote_urls: list[str] = []
        task_id: str | None = None
        raw_response: dict | None = None

        for _ in range(max(1, int(request.num_outputs))):
            create_result = self._create_task(model, person_url, top_url, bottom_url)
            task_id = create_result.task_id
            if create_result.status != "queued":
                return ProviderTaskResult(
                    task_id=task_id,
                    provider=self.name,
                    model=model,
                    status="failed",
                    remote_urls=[],
                    output_paths=[],
                    error_code=create_result.error_code,
                    error_message=create_result.error_message,
                    raw_response=create_result.raw_response,
                )

            poll_result = self._poll_task(task_id)
            raw_response = poll_result.raw_response
            if poll_result.status != "success" or not poll_result.image_url:
                return ProviderTaskResult(
                    task_id=task_id,
                    provider=self.name,
                    model=model,
                    status="failed",
                    remote_urls=[],
                    output_paths=[],
                    error_code=poll_result.error_code,
                    error_message=poll_result.error_message,
                    raw_response=raw_response,
                )

            remote_urls.append(poll_result.image_url)
            output_path = output_dir / f"aitryon_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}.png"
            self._download_image(poll_result.image_url, output_path)
            output_paths.append(str(output_path))

        return ProviderTaskResult(
            task_id=task_id,
            provider=self.name,
            model=model,
            status="success",
            remote_urls=remote_urls,
            output_paths=output_paths,
            raw_response=raw_response,
        )

    def generate_video(self, request):
        return ProviderTaskResult(
            task_id=None,
            provider=self.name,
            model="aitryon",
            status="failed",
            remote_urls=[],
            output_paths=[],
            error_message="Aitryon provider does not implement video generation.",
        )

    def _select_model(self, request: TryOnRequest) -> str:
        if request.model_override:
            return request.model_override.strip()
        if request.quality_mode == "high":
            return self._high_model
        return self._preview_model

    def _resolve_api_base(self, region: str) -> str:
        if region == "cn-beijing":
            return "https://dashscope.aliyuncs.com"
        return "https://dashscope.aliyuncs.com"

    def _ensure_public_url(self, local_path: str, provided_url: str | None) -> str:
        if provided_url:
            return provided_url
        if not self.public_asset_store:
            raise RuntimeError("Public URL upload is not configured.")
        asset = self.public_asset_store.ensure_public_url(local_path, self._public_url_ttl)
        if not asset.public_url:
            raise RuntimeError("Failed to obtain public URL for asset.")
        return asset.public_url

    def _create_task(
        self,
        model: str,
        person_url: str,
        top_url: str | None,
        bottom_url: str | None,
    ) -> AitryonResult:
        url = f"{self._api_base}/api/v1/services/aigc/image2image/image-synthesis/"
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
            "X-DashScope-Async": "enable",
        }
        payload: dict[str, object] = {
            "model": model,
            "input": {
                "person_image_url": person_url,
            },
            "parameters": {
                "resolution": -1,
                "restore_face": True,
            },
        }
        if top_url:
            payload["input"]["top_garment_url"] = top_url
        if bottom_url:
            payload["input"]["bottom_garment_url"] = bottom_url

        response = requests.post(url, json=payload, headers=headers, timeout=30)
        if response.status_code != 200:
            return AitryonResult(
                task_id="",
                status="failed",
                image_url=None,
                error_code=str(response.status_code),
                error_message=response.text,
                raw_response={},
            )

        data = _safe_json(response)
        task_id = data.get("output", {}).get("task_id", "")
        status = data.get("output", {}).get("task_status", "PENDING")
        return AitryonResult(
            task_id=task_id,
            status=STATUS_MAP.get(status, "queued"),
            image_url=None,
            error_code=None,
            error_message=None,
            raw_response=data,
        )

    def _poll_task(self, task_id: str, timeout_seconds: int = 120, interval_seconds: int = 3) -> AitryonResult:
        url = f"{self._api_base}/api/v1/tasks/{task_id}"
        headers = {
            "Authorization": f"Bearer {self._api_key}",
        }
        deadline = time.time() + timeout_seconds

        while time.time() < deadline:
            response = requests.get(url, headers=headers, timeout=15)
            if response.status_code != 200:
                return AitryonResult(
                    task_id=task_id,
                    status="failed",
                    image_url=None,
                    error_code=str(response.status_code),
                    error_message=response.text,
                    raw_response={},
                )

            data = _safe_json(response)
            output = data.get("output", {})
            status = output.get("task_status", "UNKNOWN")
            mapped = STATUS_MAP.get(status, "failed")

            if mapped == "success":
                image_url = output.get("image_url")
                return AitryonResult(
                    task_id=task_id,
                    status="success",
                    image_url=image_url,
                    error_code=None,
                    error_message=None,
                    raw_response=data,
                )

            if mapped == "failed":
                return AitryonResult(
                    task_id=task_id,
                    status="failed",
                    image_url=None,
                    error_code=output.get("code"),
                    error_message=output.get("message"),
                    raw_response=data,
                )

            time.sleep(interval_seconds)

        return AitryonResult(
            task_id=task_id,
            status="failed",
            image_url=None,
            error_code="Timeout",
            error_message="Timed out waiting for try-on result.",
            raw_response={},
        )

    def _download_image(self, url: str, output_path: Path) -> None:
        response = requests.get(url, stream=True, timeout=30)
        if response.status_code != 200:
            raise RuntimeError(f"Failed to download result: HTTP {response.status_code}")
        with output_path.open("wb") as handle:
            for chunk in response.iter_content(chunk_size=1024 * 512):
                if chunk:
                    handle.write(chunk)


def _safe_json(response: requests.Response) -> dict:
    try:
        return response.json()
    except ValueError:
        return {"raw": response.text}
