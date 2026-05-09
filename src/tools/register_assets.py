from __future__ import annotations

from pathlib import Path
import argparse
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.config import load_config
from src.metadata_store import MetadataStore
from src.storage import to_relative_path

IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp"}


def _find_image(asset_dir: Path) -> Path | None:
    for ext in IMAGE_EXTS:
        candidate = asset_dir / f"image{ext}"
        if candidate.exists():
            return candidate
    for item in asset_dir.iterdir():
        if item.is_file() and item.suffix.lower() in IMAGE_EXTS:
            return item
    return None


def register_persons(root: Path, store: MetadataStore, project_root: Path, authorized: bool) -> int:
    added = 0
    for asset_dir in root.iterdir():
        if not asset_dir.is_dir():
            continue
        image = _find_image(asset_dir)
        if not image:
            continue
        asset_id = asset_dir.name
        if store.get_person(asset_id):
            continue
        store.add_person(
            {
                "id": asset_id,
                "name": asset_id,
                "image_path": to_relative_path(image, project_root),
                "thumbnail_path": None,
                "description": "",
                "is_authorized": authorized,
            }
        )
        added += 1
    return added


def register_garments(
    root: Path, store: MetadataStore, project_root: Path, category: str
) -> int:
    added = 0
    for asset_dir in root.iterdir():
        if not asset_dir.is_dir():
            continue
        image = _find_image(asset_dir)
        if not image:
            continue
        asset_id = asset_dir.name
        if store.get_garment(asset_id):
            continue
        store.add_garment(
            {
                "id": asset_id,
                "name": asset_id,
                "image_path": to_relative_path(image, project_root),
                "thumbnail_path": None,
                "category": category,
                "description": "",
                "must_preserve_logo": False,
            }
        )
        added += 1
    return added


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--persons-dir", default="data/persons")
    parser.add_argument("--garments-dir", default="data/garments")
    parser.add_argument("--garment-category", default="upper_body")
    parser.add_argument("--authorized", action="store_true")
    args = parser.parse_args()

    config = load_config()
    store = MetadataStore(config.database_path)

    persons_added = register_persons(Path(args.persons_dir), store, config.project_root, args.authorized)
    garments_added = register_garments(Path(args.garments_dir), store, config.project_root, args.garment_category)

    print(f"Added persons: {persons_added}, garments: {garments_added}")


if __name__ == "__main__":
    main()