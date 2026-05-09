from __future__ import annotations

from typing import Dict, Optional

from src.providers.base import GenerationProvider, ProviderTaskResult, TryOnRequest, VideoRequest


class PlaceholderProvider(GenerationProvider):
    def __init__(
        self,
        name: str,
        required_env: Dict[str, str],
        supports_tryon: bool = True,
        supports_video: bool = False,
        requires_public_url: bool = True,
        public_asset_store=None,
    ) -> None:
        super().__init__(public_asset_store)
        self.name = name
        self.supports_tryon = supports_tryon
        self.supports_video = supports_video
        self.requires_public_url = requires_public_url
        self.required_env = required_env

    def validate_environment(self) -> Optional[str]:
        missing = [key for key, value in self.required_env.items() if not value]
        if missing:
            return f"Missing config: {', '.join(missing)}"
        if self.requires_public_url and self.public_asset_store and not self.public_asset_store.is_enabled():
            return "Public URL upload is not configured."
        return "Provider stub: implement API calls before use."

    def generate_tryon_image(self, request: TryOnRequest) -> ProviderTaskResult:
        return ProviderTaskResult(
            task_id=None,
            provider=self.name,
            model="stub",
            status="failed",
            remote_urls=[],
            output_paths=[],
            error_message=self.validate_environment(),
        )

    def generate_video(self, request: VideoRequest) -> ProviderTaskResult:
        return ProviderTaskResult(
            task_id=None,
            provider=self.name,
            model="stub",
            status="failed",
            remote_urls=[],
            output_paths=[],
            error_message=self.validate_environment(),
        )
