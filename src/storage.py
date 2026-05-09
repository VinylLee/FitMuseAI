from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
import uuid

from src.image_utils import create_thumbnail, normalize_image
from src.config import AppConfig


@dataclass(frozen=True)
class SavedAssetPaths:
    image_path: str
    thumbnail_path: str


def ensure_app_dirs(config: AppConfig) -> None:
    paths = [
        config.app_data_dir,
        config.app_data_dir / "persons",
        config.app_data_dir / "garments",
        config.app_data_dir / "results" / "images",
        config.app_data_dir / "results" / "videos",
        config.app_data_dir / "thumbnails",
    ]

    for path in paths:
        path.mkdir(parents=True, exist_ok=True)


def generate_id(prefix: str) -> str:
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    return f"{prefix}_{timestamp}_{uuid.uuid4().hex[:8]}"


def to_relative_path(path: Path, project_root: Path) -> str:
    try:
        return str(path.relative_to(project_root))
    except ValueError:
        return str(path)


def save_person_asset(file_path: str, asset_id: str, config: AppConfig) -> SavedAssetPaths:
    asset_dir = config.app_data_dir / "persons" / asset_id
    image_path = asset_dir / "image.png"
    thumb_path = asset_dir / "thumb.jpg"

    normalize_image(file_path, str(image_path))
    create_thumbnail(str(image_path), str(thumb_path))

    return SavedAssetPaths(
        image_path=to_relative_path(image_path, config.project_root),
        thumbnail_path=to_relative_path(thumb_path, config.project_root),
    )


def save_garment_asset(file_path: str, asset_id: str, config: AppConfig) -> SavedAssetPaths:
    asset_dir = config.app_data_dir / "garments" / asset_id
    image_path = asset_dir / "image.png"
    thumb_path = asset_dir / "thumb.jpg"

    normalize_image(file_path, str(image_path))
    create_thumbnail(str(image_path), str(thumb_path))

    return SavedAssetPaths(
        image_path=to_relative_path(image_path, config.project_root),
        thumbnail_path=to_relative_path(thumb_path, config.project_root),
    )
