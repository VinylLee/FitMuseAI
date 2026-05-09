from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from src.config import AppConfig


@dataclass(frozen=True)
class PublicAsset:
    local_path: str
    public_url: Optional[str] = None
    expires_at: Optional[str] = None
    storage_provider: Optional[str] = None


class PublicAssetStore:
    def ensure_public_url(self, local_path: str, ttl_seconds: int = 86400) -> PublicAsset:
        raise NotImplementedError

    def is_enabled(self) -> bool:
        return False

    def status_message(self) -> str:
        return "Public asset upload is disabled."


class DisabledPublicAssetStore(PublicAssetStore):
    def __init__(self, enabled_flag: bool) -> None:
        self._enabled_flag = enabled_flag

    def ensure_public_url(self, local_path: str, ttl_seconds: int = 86400) -> PublicAsset:
        raise RuntimeError("Public URL upload is not configured.")

    def is_enabled(self) -> bool:
        return self._enabled_flag

    def status_message(self) -> str:
        if self._enabled_flag:
            return "Public URL upload is enabled but no store is implemented yet."
        return "Public URL upload is disabled."


def build_public_asset_store(config: AppConfig) -> PublicAssetStore:
    return DisabledPublicAssetStore(config.enable_public_url_upload)
