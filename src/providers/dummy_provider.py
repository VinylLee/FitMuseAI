from __future__ import annotations

from datetime import datetime
from pathlib import Path
import uuid

from src.image_utils import create_placeholder_tryon
from src.providers.base import GenerationProvider, ProviderTaskResult, TryOnRequest, VideoRequest


class DummyProvider(GenerationProvider):
    name = "dummy"
    supports_tryon = True
    supports_video = False
    requires_public_url = False

    def generate_tryon_image(self, request: TryOnRequest) -> ProviderTaskResult:
        output_dir = Path(request.output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        output_paths: list[str] = []
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")

        for index in range(request.num_outputs):
            output_path = output_dir / f"result_{timestamp}_{uuid.uuid4().hex[:8]}_{index + 1}.png"
            create_placeholder_tryon(
                request.person_image_path,
                request.garment_image_path,
                str(output_path),
                label="DUMMY TRYON - NOT REAL",
            )
            output_paths.append(str(output_path))

        return ProviderTaskResult(
            task_id=None,
            provider=self.name,
            model="dummy",
            status="success",
            remote_urls=[],
            output_paths=output_paths,
        )

    def generate_video(self, request: VideoRequest) -> ProviderTaskResult:
        return ProviderTaskResult(
            task_id=None,
            provider=self.name,
            model="dummy",
            status="failed",
            remote_urls=[],
            output_paths=[],
            error_message="Dummy provider does not implement video generation.",
        )
