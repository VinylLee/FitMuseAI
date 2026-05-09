from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Literal, Any

TaskStatus = Literal["queued", "running", "success", "failed", "moderated"]


@dataclass
class TryOnRequest:
    person_image_path: str
    garment_image_path: str
    garment_category: str
    prompt: str
    negative_prompt: str
    aspect_ratio: str
    num_outputs: int = 1
    seed: Optional[int] = None
    output_dir: str = "data/results/images"
    person_public_url: Optional[str] = None
    garment_public_url: Optional[str] = None
    quality_mode: str = "preview"
    model_override: Optional[str] = None


@dataclass
class VideoRequest:
    canonical_image_path: str
    prompt: str
    negative_prompt: str
    aspect_ratio: str
    duration_seconds: int
    seed: Optional[int] = None
    output_dir: str = "data/results/videos"
    canonical_public_url: Optional[str] = None
    motion_template: Optional[str] = None


@dataclass
class ProviderTaskResult:
    task_id: Optional[str]
    provider: str
    model: str
    status: TaskStatus
    remote_urls: List[str]
    output_paths: List[str]
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    raw_response: Optional[dict] = None


class GenerationProvider:
    name: str = "base"
    supports_tryon: bool = False
    supports_video: bool = False
    requires_public_url: bool = False

    def __init__(self, public_asset_store: Optional[Any] = None) -> None:
        self.public_asset_store = public_asset_store

    def validate_environment(self) -> Optional[str]:
        return None

    def generate_tryon_image(self, request: TryOnRequest) -> ProviderTaskResult:
        raise NotImplementedError

    def generate_video(self, request: VideoRequest) -> ProviderTaskResult:
        raise NotImplementedError
