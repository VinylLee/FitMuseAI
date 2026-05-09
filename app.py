from __future__ import annotations

import os

from src.config import load_config
from src.metadata_store import MetadataStore
from src.public_asset_store import build_public_asset_store
from src.storage import ensure_app_dirs
from src.providers import build_provider_registry
from src.ui.gradio_app import build_app


def main() -> None:
    config = load_config()
    os.chdir(config.project_root)

    ensure_app_dirs(config)
    store = MetadataStore(config.database_path)
    public_asset_store = build_public_asset_store(config)
    provider_registry = build_provider_registry(config, public_asset_store)

    app = build_app(config, store, provider_registry, public_asset_store)
    app.queue()
    app.launch()


if __name__ == "__main__":
    main()
