from __future__ import annotations

from pathlib import Path
import shutil
from typing import Any, Iterable, Optional

import gradio as gr

from src.config import AppConfig
from src.metadata_store import MetadataStore
from src.prompt_builder import DEFAULT_NEGATIVE_PROMPT, DEFAULT_TRYON_SCENE, build_tryon_prompt
from src.providers.base import GenerationProvider, TryOnRequest
from src.storage import generate_id, save_garment_asset, save_person_asset, to_relative_path

IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp"}


def build_app(
    config: AppConfig,
    store: MetadataStore,
    providers: dict[str, GenerationProvider],
    public_asset_store,
) -> gr.Blocks:
    person_choices = _build_person_choices(store.list_persons())
    garment_choices = _build_garment_choices(store.list_garments())

    tryon_provider_choices = [
        name for name, provider in providers.items() if provider.supports_tryon
    ]

    provider_status_rows = _build_provider_status_rows(providers)

    with gr.Blocks(title="FitMuse AI MVP") as app:
        gr.Markdown("# FitMuse AI MVP")
        gr.Markdown(
            "Local virtual try-on MVP. Dummy provider is enabled by default; real providers are stubbed."
        )

        with gr.Tab("Assets"):
            with gr.Row():
                with gr.Column():
                    gr.Markdown("## Persons")
                    person_files = gr.Files(label="Person images", file_count="multiple")
                    person_name_prefix = gr.Textbox(label="Name prefix")
                    person_description = gr.Textbox(label="Description", lines=2)
                    person_authorized = gr.Checkbox(
                        label="I confirm I have rights to use these images.", value=False
                    )
                    person_save_btn = gr.Button("Save persons")
                    person_status = gr.Markdown()
                    person_gallery = gr.Gallery(
                        label="Persons", value=_build_person_gallery(store.list_persons()), columns=4
                    )

                with gr.Column():
                    gr.Markdown("## Garments")
                    garment_files = gr.Files(label="Garment images", file_count="multiple")
                    garment_name_prefix = gr.Textbox(label="Name prefix")
                    garment_category = gr.Dropdown(
                        label="Category",
                        choices=[
                            "upper_body",
                            "lower_body",
                            "dress",
                            "outerwear",
                            "set",
                            "shoes",
                            "other",
                        ],
                        value="upper_body",
                    )
                    garment_description = gr.Textbox(label="Description", lines=2)
                    garment_preserve_logo = gr.Checkbox(label="Preserve logo/pattern", value=False)
                    garment_save_btn = gr.Button("Save garments")
                    garment_status = gr.Markdown()
                    garment_gallery = gr.Gallery(
                        label="Garments", value=_build_garment_gallery(store.list_garments()), columns=4
                    )

        with gr.Tab("Single Try-On"):
            single_person = gr.Dropdown(label="Person", choices=person_choices)
            single_garment = gr.Dropdown(label="Garment", choices=garment_choices)
            single_provider = gr.Dropdown(
                label="Provider",
                choices=tryon_provider_choices,
                value=config.default_tryon_provider if config.default_tryon_provider in tryon_provider_choices else "dummy",
            )
            single_quality = gr.Dropdown(
                label="Quality mode",
                choices=["preview", "high", "compare"],
                value=config.default_image_quality if config.default_image_quality else "preview",
            )
            single_aspect = gr.Dropdown(
                label="Aspect ratio",
                choices=["1:1", "3:4", "4:5", "9:16", "16:9"],
                value="3:4",
            )
            single_num = gr.Slider(1, 4, step=1, value=1, label="Num outputs")
            single_scene = gr.Textbox(label="Scene description", value=DEFAULT_TRYON_SCENE, lines=2)
            single_negative = gr.Textbox(
                label="Negative prompt", value=DEFAULT_NEGATIVE_PROMPT, lines=2
            )
            single_generate_btn = gr.Button("Generate")
            single_status = gr.Markdown()
            single_gallery = gr.Gallery(label="Results", columns=4)

        with gr.Tab("Batch"):
            batch_persons = gr.Dropdown(
                label="Persons", choices=person_choices, multiselect=True
            )
            batch_garments = gr.Dropdown(
                label="Garments", choices=garment_choices, multiselect=True
            )
            batch_provider = gr.Dropdown(
                label="Provider",
                choices=tryon_provider_choices,
                value=config.default_tryon_provider if config.default_tryon_provider in tryon_provider_choices else "dummy",
            )
            batch_quality = gr.Dropdown(
                label="Quality mode",
                choices=["preview", "high", "compare"],
                value=config.default_image_quality if config.default_image_quality else "preview",
            )
            batch_aspect = gr.Dropdown(
                label="Aspect ratio",
                choices=["1:1", "3:4", "4:5", "9:16", "16:9"],
                value="3:4",
            )
            batch_num = gr.Slider(1, 4, step=1, value=1, label="Num outputs per combo")
            batch_scene = gr.Textbox(label="Scene description", value=DEFAULT_TRYON_SCENE, lines=2)
            batch_negative = gr.Textbox(
                label="Negative prompt", value=DEFAULT_NEGATIVE_PROMPT, lines=2
            )
            batch_generate_btn = gr.Button("Start batch")
            batch_status = gr.Markdown()
            batch_gallery = gr.Gallery(label="Batch results", columns=4)

        with gr.Tab("Canonical"):
            canonical_person = gr.Dropdown(label="Person", choices=person_choices)
            canonical_garment = gr.Dropdown(label="Garment", choices=garment_choices)
            canonical_results = gr.Dropdown(label="Result to set as canonical", choices=[])
            canonical_image = gr.Image(label="Current canonical image")
            canonical_set_btn = gr.Button("Set canonical")
            canonical_clear_btn = gr.Button("Clear canonical")
            canonical_status = gr.Markdown()

        with gr.Tab("History"):
            history_type = gr.Dropdown(
                label="Result type", choices=["all", "image", "video"], value="all"
            )
            history_person = gr.Dropdown(label="Person", choices=person_choices)
            history_garment = gr.Dropdown(label="Garment", choices=garment_choices)
            history_refresh_btn = gr.Button("Refresh")
            history_status = gr.Markdown()
            history_gallery = gr.Gallery(label="History", columns=4)

        with gr.Tab("Admin"):
            gr.Markdown("## Database Admin")
            with gr.Row():
                with gr.Column():
                    gr.Markdown("### Persons")
                    admin_person = gr.Dropdown(label="Person", choices=person_choices)
                    admin_person_refresh_btn = gr.Button("Refresh persons")
                    admin_person_id = gr.Textbox(label="Person ID", interactive=False)
                    admin_person_name = gr.Textbox(label="Name")
                    admin_person_description = gr.Textbox(label="Description", lines=2)
                    admin_person_authorized = gr.Checkbox(label="Authorized", value=False)
                    admin_person_image = gr.Image(label="Image", height=320)
                    admin_person_update_btn = gr.Button("Update person")
                    admin_person_delete_files = gr.Checkbox(label="Also delete files", value=False)
                    admin_person_delete_btn = gr.Button("Delete person")
                    admin_person_bulk_authorized = gr.Checkbox(
                        label="Mark as authorized", value=True
                    )
                    admin_person_bulk_btn = gr.Button("Register from data/persons")
                    admin_person_status = gr.Markdown()

                with gr.Column():
                    gr.Markdown("### Garments")
                    admin_garment = gr.Dropdown(label="Garment", choices=garment_choices)
                    admin_garment_refresh_btn = gr.Button("Refresh garments")
                    admin_garment_id = gr.Textbox(label="Garment ID", interactive=False)
                    admin_garment_name = gr.Textbox(label="Name")
                    admin_garment_category = gr.Dropdown(
                        label="Category",
                        choices=[
                            "upper_body",
                            "lower_body",
                            "dress",
                            "outerwear",
                            "set",
                            "shoes",
                            "other",
                        ],
                        value="upper_body",
                    )
                    admin_garment_description = gr.Textbox(label="Description", lines=2)
                    admin_garment_preserve_logo = gr.Checkbox(
                        label="Preserve logo/pattern", value=False
                    )
                    admin_garment_image = gr.Image(label="Image", height=320)
                    admin_garment_update_btn = gr.Button("Update garment")
                    admin_garment_delete_files = gr.Checkbox(
                        label="Also delete files", value=False
                    )
                    admin_garment_delete_btn = gr.Button("Delete garment")
                    admin_garment_bulk_category = gr.Dropdown(
                        label="Default category",
                        choices=[
                            "upper_body",
                            "lower_body",
                            "dress",
                            "outerwear",
                            "set",
                            "shoes",
                            "other",
                        ],
                        value="upper_body",
                    )
                    admin_garment_bulk_btn = gr.Button("Register from data/garments")
                    admin_garment_status = gr.Markdown()

            with gr.Row():
                with gr.Column():
                    gr.Markdown("### Results")
                    admin_result_person = gr.Dropdown(
                        label="Filter by person", choices=[("All", "")] + person_choices
                    )
                    admin_result_garment = gr.Dropdown(
                        label="Filter by garment", choices=[("All", "")] + garment_choices
                    )
                    admin_result_status_filter = gr.Dropdown(
                        label="Filter by status",
                        choices=["all", "success", "failed", "queued", "running"],
                        value="all",
                    )
                    admin_result_refresh_btn = gr.Button("Refresh results")
                    admin_result_by_id = gr.Textbox(
                        label="Delete by result ID",
                        placeholder="Paste a result ID to delete",
                    )
                    admin_result_delete_id_btn = gr.Button("Delete by ID")
                    admin_result_clear_btn = gr.Button("Delete all filtered")
                    admin_result_delete_files = gr.Checkbox(
                        label="Also delete image files", value=False
                    )
                    admin_result_status = gr.Markdown()
                    admin_result_gallery = gr.Gallery(label="Filtered results", columns=4)

        with gr.Tab("Settings"):
            gr.Markdown("## Configuration")
            gr.Markdown(
                f"Edit .env to add API keys and provider settings. Public upload status: {public_asset_store.status_message()}"
            )
            settings_refresh_btn = gr.Button("Refresh provider status")
            settings_table = gr.Dataframe(
                headers=["Provider", "Status"],
                value=provider_status_rows,
                row_count=(len(provider_status_rows) or 1),
                col_count=2,
            )

        person_outputs = [
            person_status,
            person_gallery,
            single_person,
            batch_persons,
            canonical_person,
            history_person,
            admin_person,
        ]
        garment_outputs = [
            garment_status,
            garment_gallery,
            single_garment,
            batch_garments,
            canonical_garment,
            history_garment,
            admin_garment,
        ]

        person_save_btn.click(
            fn=lambda files, prefix, desc, authorized: _handle_save_person(
                files, prefix, desc, authorized, store, config
            ),
            inputs=[person_files, person_name_prefix, person_description, person_authorized],
            outputs=person_outputs,
        )

        garment_save_btn.click(
            fn=lambda files, prefix, category, desc, preserve: _handle_save_garment(
                files, prefix, category, desc, preserve, store, config
            ),
            inputs=[garment_files, garment_name_prefix, garment_category, garment_description, garment_preserve_logo],
            outputs=garment_outputs,
        )

        single_generate_btn.click(
            fn=lambda person_id, garment_id, provider_name, quality, aspect, num_outputs, scene, negative: _handle_generate_single(
                person_id,
                garment_id,
                provider_name,
                quality,
                aspect,
                num_outputs,
                scene,
                negative,
                store,
                providers,
                config,
            ),
            inputs=[
                single_person,
                single_garment,
                single_provider,
                single_quality,
                single_aspect,
                single_num,
                single_scene,
                single_negative,
            ],
            outputs=[single_status, single_gallery],
        )

        batch_generate_btn.click(
            fn=lambda person_ids, garment_ids, provider_name, quality, aspect, num_outputs, scene, negative: _handle_generate_batch(
                person_ids,
                garment_ids,
                provider_name,
                quality,
                aspect,
                num_outputs,
                scene,
                negative,
                store,
                providers,
                config,
            ),
            inputs=[
                batch_persons,
                batch_garments,
                batch_provider,
                batch_quality,
                batch_aspect,
                batch_num,
                batch_scene,
                batch_negative,
            ],
            outputs=[batch_status, batch_gallery],
        )

        canonical_person.change(
            fn=lambda person_id, garment_id: _refresh_canonical_options(person_id, garment_id, store),
            inputs=[canonical_person, canonical_garment],
            outputs=[canonical_results, canonical_image, canonical_status],
        )
        canonical_garment.change(
            fn=lambda person_id, garment_id: _refresh_canonical_options(person_id, garment_id, store),
            inputs=[canonical_person, canonical_garment],
            outputs=[canonical_results, canonical_image, canonical_status],
        )

        canonical_set_btn.click(
            fn=lambda person_id, garment_id, result_id: _handle_set_canonical(
                person_id, garment_id, result_id, store
            ),
            inputs=[canonical_person, canonical_garment, canonical_results],
            outputs=[canonical_status, canonical_image],
        )
        canonical_clear_btn.click(
            fn=lambda person_id, garment_id: _handle_clear_canonical(person_id, garment_id, store),
            inputs=[canonical_person, canonical_garment],
            outputs=[canonical_status, canonical_image],
        )

        history_refresh_btn.click(
            fn=lambda result_type, person_id, garment_id: _handle_refresh_history(
                result_type, person_id, garment_id, store
            ),
            inputs=[history_type, history_person, history_garment],
            outputs=[history_status, history_gallery],
        )

        admin_person.change(
            fn=lambda person_id: _load_admin_person(person_id, store, config.project_root),
            inputs=[admin_person],
            outputs=[
                admin_person_id,
                admin_person_name,
                admin_person_description,
                admin_person_authorized,
                admin_person_image,
                admin_person_status,
            ],
        )
        admin_person_refresh_btn.click(
            fn=lambda: _handle_admin_refresh_persons(store),
            inputs=[],
            outputs=[
                admin_person_status,
                person_gallery,
                single_person,
                batch_persons,
                canonical_person,
                history_person,
                admin_person,
            ],
        )
        admin_person_update_btn.click(
            fn=lambda person_id, name, desc, authorized: _handle_admin_update_person(
                person_id, name, desc, authorized, store
            ),
            inputs=[admin_person, admin_person_name, admin_person_description, admin_person_authorized],
            outputs=[
                admin_person_status,
                person_gallery,
                single_person,
                batch_persons,
                canonical_person,
                history_person,
                admin_person,
            ],
        )
        admin_person_delete_btn.click(
            fn=lambda person_id, delete_files: _handle_admin_delete_person(
                person_id, delete_files, store, config
            ),
            inputs=[admin_person, admin_person_delete_files],
            outputs=[
                admin_person_status,
                admin_person_id,
                admin_person_name,
                admin_person_description,
                admin_person_authorized,
                admin_person_image,
                person_gallery,
                single_person,
                batch_persons,
                canonical_person,
                history_person,
                admin_person,
            ],
        )
        admin_person_bulk_btn.click(
            fn=lambda authorized: _handle_admin_register_persons(authorized, store, config),
            inputs=[admin_person_bulk_authorized],
            outputs=[
                admin_person_status,
                person_gallery,
                single_person,
                batch_persons,
                canonical_person,
                history_person,
                admin_person,
            ],
        )

        admin_garment.change(
            fn=lambda garment_id: _load_admin_garment(garment_id, store, config.project_root),
            inputs=[admin_garment],
            outputs=[
                admin_garment_id,
                admin_garment_name,
                admin_garment_category,
                admin_garment_description,
                admin_garment_preserve_logo,
                admin_garment_image,
                admin_garment_status,
            ],
        )
        admin_garment_refresh_btn.click(
            fn=lambda: _handle_admin_refresh_garments(store),
            inputs=[],
            outputs=[
                admin_garment_status,
                garment_gallery,
                single_garment,
                batch_garments,
                canonical_garment,
                history_garment,
                admin_garment,
            ],
        )
        admin_garment_update_btn.click(
            fn=lambda garment_id, name, category, desc, preserve: _handle_admin_update_garment(
                garment_id, name, category, desc, preserve, store
            ),
            inputs=[
                admin_garment,
                admin_garment_name,
                admin_garment_category,
                admin_garment_description,
                admin_garment_preserve_logo,
            ],
            outputs=[
                admin_garment_status,
                garment_gallery,
                single_garment,
                batch_garments,
                canonical_garment,
                history_garment,
                admin_garment,
            ],
        )
        admin_garment_delete_btn.click(
            fn=lambda garment_id, delete_files: _handle_admin_delete_garment(
                garment_id, delete_files, store, config
            ),
            inputs=[admin_garment, admin_garment_delete_files],
            outputs=[
                admin_garment_status,
                admin_garment_id,
                admin_garment_name,
                admin_garment_category,
                admin_garment_description,
                admin_garment_preserve_logo,
                admin_garment_image,
                garment_gallery,
                single_garment,
                batch_garments,
                canonical_garment,
                history_garment,
                admin_garment,
            ],
        )
        admin_garment_bulk_btn.click(
            fn=lambda category: _handle_admin_register_garments(category, store, config),
            inputs=[admin_garment_bulk_category],
            outputs=[
                admin_garment_status,
                garment_gallery,
                single_garment,
                batch_garments,
                canonical_garment,
                history_garment,
                admin_garment,
            ],
        )

        admin_result_refresh_btn.click(
            fn=lambda person_id, garment_id, status: _handle_admin_refresh_results(
                person_id, garment_id, status, store
            ),
            inputs=[admin_result_person, admin_result_garment, admin_result_status_filter],
            outputs=[admin_result_status, admin_result_gallery],
        )
        admin_result_delete_id_btn.click(
            fn=lambda result_id, delete_files: _handle_admin_delete_result_by_id(
                result_id, delete_files, store, config
            ),
            inputs=[admin_result_by_id, admin_result_delete_files],
            outputs=[admin_result_status, admin_result_by_id],
        )
        admin_result_clear_btn.click(
            fn=lambda person_id, garment_id, status, delete_files: _handle_admin_clear_results(
                person_id, garment_id, status, delete_files, store, config
            ),
            inputs=[
                admin_result_person,
                admin_result_garment,
                admin_result_status_filter,
                admin_result_delete_files,
            ],
            outputs=[admin_result_status, admin_result_gallery],
        )

        settings_refresh_btn.click(
            fn=lambda: _build_provider_status_rows(providers),
            inputs=[],
            outputs=[settings_table],
        )

    return app


def _resolve_file_paths(files: Optional[Iterable[Any]]) -> list[str]:
    paths: list[str] = []
    if not files:
        return paths
    for item in files:
        if isinstance(item, str):
            paths.append(item)
        elif hasattr(item, "name"):
            paths.append(getattr(item, "name"))
    return paths


def _build_person_choices(persons: list[dict[str, Any]]) -> list[tuple[str, str]]:
    return [(f"{p['name']} ({p['id']})", p["id"]) for p in persons]


def _build_garment_choices(garments: list[dict[str, Any]]) -> list[tuple[str, str]]:
    return [(f"{g['name']} ({g['id']})", g["id"]) for g in garments]


def _build_person_gallery(persons: list[dict[str, Any]]) -> list[tuple[str, str]]:
    items = []
    for person in persons:
        image_path = person.get("thumbnail_path") or person.get("image_path")
        label = f"{person['name']} ({person['id']})"
        if image_path:
            items.append((image_path, label))
    return items


def _build_garment_gallery(garments: list[dict[str, Any]]) -> list[tuple[str, str]]:
    items = []
    for garment in garments:
        image_path = garment.get("thumbnail_path") or garment.get("image_path")
        label = f"{garment['name']} ({garment['id']})"
        if image_path:
            items.append((image_path, label))
    return items


def _build_result_gallery(results: list[dict[str, Any]]) -> list[tuple[str, str]]:
    items = []
    for result in results:
        image_path = result.get("output_path")
        if not image_path:
            continue
        label = f"{result.get('provider', '')} | {result.get('id', '')}"
        items.append((image_path, label))
    return items


def _build_result_choices(results: list[dict[str, Any]]) -> list[tuple[str, str]]:
    choices: list[tuple[str, str]] = []
    for result in results:
        label = f"{result.get('created_at', '')} | {result.get('provider', '')} | {result.get('id', '')}"
        choices.append((label, result["id"]))
    return choices


def _build_provider_status_rows(providers: dict[str, GenerationProvider]) -> list[list[str]]:
    rows: list[list[str]] = []
    for name, provider in providers.items():
        status = provider.validate_environment() or "Ready"
        rows.append([name, status])
    return rows


def _find_asset_image(asset_dir: Path) -> Optional[Path]:
    for ext in IMAGE_EXTS:
        candidate = asset_dir / f"image{ext}"
        if candidate.exists():
            return candidate
    for item in asset_dir.iterdir():
        if item.is_file() and item.suffix.lower() in IMAGE_EXTS:
            return item
    return None


def _refresh_person_ui(store: MetadataStore) -> tuple[list[tuple[str, str]], list[tuple[str, str]]]:
    persons = store.list_persons()
    return _build_person_choices(persons), _build_person_gallery(persons)


def _refresh_garment_ui(store: MetadataStore) -> tuple[list[tuple[str, str]], list[tuple[str, str]]]:
    garments = store.list_garments()
    return _build_garment_choices(garments), _build_garment_gallery(garments)


def _delete_asset_dir(asset_root: Path, asset_id: str) -> bool:
    base = asset_root.resolve()
    target = (asset_root / asset_id).resolve()
    if base == target or base not in target.parents:
        return False
    if target.exists():
        shutil.rmtree(target)
    return True


def _load_admin_person(person_id: str, store: MetadataStore, project_root: Path):
    if not person_id:
        return "", "", "", False, None, "Select person."
    person = store.get_person(person_id)
    if not person:
        return person_id, "", "", False, None, "Person not found."

    image_path = person.get("image_path")
    image_path = _to_absolute_path(image_path, project_root) if image_path else None

    return (
        person.get("id", ""),
        person.get("name", ""),
        person.get("description") or "",
        bool(person.get("is_authorized")),
        image_path,
        "Loaded person.",
    )


def _load_admin_garment(garment_id: str, store: MetadataStore, project_root: Path):
    if not garment_id:
        return "", "", "upper_body", "", False, None, "Select garment."
    garment = store.get_garment(garment_id)
    if not garment:
        return garment_id, "", "upper_body", "", False, None, "Garment not found."

    image_path = garment.get("image_path")
    image_path = _to_absolute_path(image_path, project_root) if image_path else None

    return (
        garment.get("id", ""),
        garment.get("name", ""),
        garment.get("category") or "upper_body",
        garment.get("description") or "",
        bool(garment.get("must_preserve_logo")),
        image_path,
        "Loaded garment.",
    )


def _register_persons_from_folder(
    store: MetadataStore, config: AppConfig, authorized: bool
) -> int:
    root = config.app_data_dir / "persons"
    if not root.exists():
        return 0

    added = 0
    for asset_dir in root.iterdir():
        if not asset_dir.is_dir():
            continue
        asset_id = asset_dir.name
        if store.get_person(asset_id):
            continue
        image_path = _find_asset_image(asset_dir)
        if not image_path:
            continue
        store.add_person(
            {
                "id": asset_id,
                "name": asset_id,
                "image_path": to_relative_path(image_path, config.project_root),
                "thumbnail_path": None,
                "description": "",
                "is_authorized": authorized,
            }
        )
        added += 1

    return added


def _register_garments_from_folder(
    store: MetadataStore, config: AppConfig, category: str
) -> int:
    root = config.app_data_dir / "garments"
    if not root.exists():
        return 0

    added = 0
    for asset_dir in root.iterdir():
        if not asset_dir.is_dir():
            continue
        asset_id = asset_dir.name
        if store.get_garment(asset_id):
            continue
        image_path = _find_asset_image(asset_dir)
        if not image_path:
            continue
        store.add_garment(
            {
                "id": asset_id,
                "name": asset_id,
                "image_path": to_relative_path(image_path, config.project_root),
                "thumbnail_path": None,
                "category": category,
                "description": "",
                "must_preserve_logo": False,
            }
        )
        added += 1

    return added


def _handle_admin_update_person(
    person_id: str,
    name: str,
    description: str,
    is_authorized: bool,
    store: MetadataStore,
):
    if not person_id:
        choices, gallery = _refresh_person_ui(store)
        return (
            "Select person.",
            gallery,
            gr.update(choices=choices),
            gr.update(choices=choices),
            gr.update(choices=choices),
            gr.update(choices=choices),
            gr.update(choices=choices),
        )

    updated = store.update_person(person_id, name, description, is_authorized)
    choices, gallery = _refresh_person_ui(store)
    status = "Person updated." if updated else "Person not found."
    admin_value = person_id if updated else None

    return (
        status,
        gallery,
        gr.update(choices=choices),
        gr.update(choices=choices),
        gr.update(choices=choices),
        gr.update(choices=choices),
        gr.update(choices=choices, value=admin_value),
    )


def _handle_admin_update_garment(
    garment_id: str,
    name: str,
    category: str,
    description: str,
    must_preserve_logo: bool,
    store: MetadataStore,
):
    if not garment_id:
        choices, gallery = _refresh_garment_ui(store)
        return (
            "Select garment.",
            gallery,
            gr.update(choices=choices),
            gr.update(choices=choices),
            gr.update(choices=choices),
            gr.update(choices=choices),
            gr.update(choices=choices),
        )

    updated = store.update_garment(garment_id, name, category, description, must_preserve_logo)
    choices, gallery = _refresh_garment_ui(store)
    status = "Garment updated." if updated else "Garment not found."
    admin_value = garment_id if updated else None

    return (
        status,
        gallery,
        gr.update(choices=choices),
        gr.update(choices=choices),
        gr.update(choices=choices),
        gr.update(choices=choices),
        gr.update(choices=choices, value=admin_value),
    )


def _handle_admin_delete_person(
    person_id: str,
    delete_files: bool,
    store: MetadataStore,
    config: AppConfig,
):
    person = store.get_person(person_id) if person_id else None
    if not person_id or not person:
        choices, gallery = _refresh_person_ui(store)
        return (
            "Person not found." if person_id else "Select person.",
            "",
            "",
            "",
            False,
            None,
            gallery,
            gr.update(choices=choices, value=None),
            gr.update(choices=choices, value=None),
            gr.update(choices=choices, value=None),
            gr.update(choices=choices, value=None),
            gr.update(choices=choices, value=None),
        )

    store.delete_person(person_id)
    if delete_files:
        _delete_asset_dir(config.app_data_dir / "persons", person_id)

    choices, gallery = _refresh_person_ui(store)
    return (
        "Person deleted.",
        "",
        "",
        "",
        False,
        None,
        gallery,
        gr.update(choices=choices, value=None),
        gr.update(choices=choices, value=None),
        gr.update(choices=choices, value=None),
        gr.update(choices=choices, value=None),
        gr.update(choices=choices, value=None),
    )


def _handle_admin_delete_garment(
    garment_id: str,
    delete_files: bool,
    store: MetadataStore,
    config: AppConfig,
):
    garment = store.get_garment(garment_id) if garment_id else None
    if not garment_id or not garment:
        choices, gallery = _refresh_garment_ui(store)
        return (
            "Garment not found." if garment_id else "Select garment.",
            "",
            "",
            "upper_body",
            "",
            False,
            None,
            gallery,
            gr.update(choices=choices, value=None),
            gr.update(choices=choices, value=None),
            gr.update(choices=choices, value=None),
            gr.update(choices=choices, value=None),
            gr.update(choices=choices, value=None),
        )

    store.delete_garment(garment_id)
    if delete_files:
        _delete_asset_dir(config.app_data_dir / "garments", garment_id)

    choices, gallery = _refresh_garment_ui(store)
    return (
        "Garment deleted.",
        "",
        "",
        "upper_body",
        "",
        False,
        None,
        gallery,
        gr.update(choices=choices, value=None),
        gr.update(choices=choices, value=None),
        gr.update(choices=choices, value=None),
        gr.update(choices=choices, value=None),
        gr.update(choices=choices, value=None),
    )


def _handle_admin_register_persons(
    authorized: bool,
    store: MetadataStore,
    config: AppConfig,
):
    added = _register_persons_from_folder(store, config, authorized)
    choices, gallery = _refresh_person_ui(store)
    return (
        f"Registered {added} person(s) from folder.",
        gallery,
        gr.update(choices=choices),
        gr.update(choices=choices),
        gr.update(choices=choices),
        gr.update(choices=choices),
        gr.update(choices=choices),
    )


def _handle_admin_register_garments(
    category: str,
    store: MetadataStore,
    config: AppConfig,
):
    added = _register_garments_from_folder(store, config, category)
    choices, gallery = _refresh_garment_ui(store)
    return (
        f"Registered {added} garment(s) from folder.",
        gallery,
        gr.update(choices=choices),
        gr.update(choices=choices),
        gr.update(choices=choices),
        gr.update(choices=choices),
        gr.update(choices=choices),
    )


def _handle_admin_refresh_persons(store: MetadataStore):
    choices, gallery = _refresh_person_ui(store)
    return (
        "Refreshed persons.",
        gallery,
        gr.update(choices=choices),
        gr.update(choices=choices),
        gr.update(choices=choices),
        gr.update(choices=choices),
        gr.update(choices=choices),
    )


def _handle_admin_refresh_garments(store: MetadataStore):
    choices, gallery = _refresh_garment_ui(store)
    return (
        "Refreshed garments.",
        gallery,
        gr.update(choices=choices),
        gr.update(choices=choices),
        gr.update(choices=choices),
        gr.update(choices=choices),
        gr.update(choices=choices),
    )


def _result_filter_args(
    person_id: str, garment_id: str, status: str
) -> tuple[Optional[str], Optional[str], Optional[str]]:
    return (
        person_id if person_id else None,
        garment_id if garment_id else None,
        status if status and status != "all" else None,
    )


def _handle_admin_refresh_results(
    person_id: str, garment_id: str, status: str, store: MetadataStore
):
    p, g, s = _result_filter_args(person_id, garment_id, status)
    results = store.list_results(p, g, status=s, limit=0)
    gallery = _build_result_gallery(results)
    count = len(results)
    return f"Found {count} result(s)." if count else "No results found.", gallery


def _handle_admin_delete_result_by_id(
    result_id: str, delete_files: bool, store: MetadataStore, config: AppConfig
):
    if not result_id:
        return "Enter a result ID.", ""

    result = store.get_result(result_id)
    if not result:
        return f"Result not found: {result_id}", ""

    output_path = result.get("output_path", "")
    store.delete_result(result_id)

    if delete_files and output_path:
        _delete_result_file(output_path, config.project_root)

    return f"Deleted result: {result_id}", ""


def _handle_admin_clear_results(
    person_id: str,
    garment_id: str,
    status: str,
    delete_files: bool,
    store: MetadataStore,
    config: AppConfig,
):
    p, g, s = _result_filter_args(person_id, garment_id, status)

    if not p and not g and not s:
        return "Please narrow the filter to avoid deleting all results.", []

    # Collect output paths before DB deletion
    to_delete = store.list_results(p, g, status=s, limit=0)
    output_paths = [r["output_path"] for r in to_delete if r.get("output_path")]

    deleted = store.delete_results(p, g, s)

    if delete_files:
        for path in output_paths:
            _delete_result_file(path, config.project_root)

    remaining = store.list_results(p, g, status=s, limit=0)
    gallery = _build_result_gallery(remaining)
    return f"Deleted {deleted} result(s).", gallery


def _delete_result_file(output_path: str, project_root: Path) -> bool:
    if not output_path:
        return False
    path = _to_absolute_path(output_path, project_root)
    p = Path(path)
    if p.exists():
        p.unlink()
        return True
    return False


def _handle_save_person(
    files: Optional[Iterable[Any]],
    name_prefix: str,
    description: str,
    is_authorized: bool,
    store: MetadataStore,
    config: AppConfig,
):
    if not is_authorized:
        return (
            "Please confirm you have rights to use these images.",
            _build_person_gallery(store.list_persons()),
            gr.update(choices=_build_person_choices(store.list_persons()), value=None),
            gr.update(choices=_build_person_choices(store.list_persons()), value=None),
            gr.update(choices=_build_person_choices(store.list_persons()), value=None),
            gr.update(choices=_build_person_choices(store.list_persons()), value=None),
            gr.update(choices=_build_person_choices(store.list_persons()), value=None),
        )

    file_paths = _resolve_file_paths(files)
    if not file_paths:
        return (
            "No files selected.",
            _build_person_gallery(store.list_persons()),
            gr.update(choices=_build_person_choices(store.list_persons()), value=None),
            gr.update(choices=_build_person_choices(store.list_persons()), value=None),
            gr.update(choices=_build_person_choices(store.list_persons()), value=None),
            gr.update(choices=_build_person_choices(store.list_persons()), value=None),
            gr.update(choices=_build_person_choices(store.list_persons()), value=None),
        )

    saved = 0
    total = len(file_paths)
    for index, file_path in enumerate(file_paths):
        asset_id = generate_id("person")
        asset_name = _format_asset_name(name_prefix, asset_id, index, total)
        paths = save_person_asset(file_path, asset_id, config)
        store.add_person(
            {
                "id": asset_id,
                "name": asset_name,
                "image_path": paths.image_path,
                "thumbnail_path": paths.thumbnail_path,
                "description": description,
                "is_authorized": is_authorized,
            }
        )
        saved += 1

    persons = store.list_persons()
    choices = _build_person_choices(persons)
    gallery = _build_person_gallery(persons)
    status = f"Saved {saved} person(s)."

    return (
        status,
        gallery,
        gr.update(choices=choices, value=None),
        gr.update(choices=choices, value=None),
        gr.update(choices=choices, value=None),
        gr.update(choices=choices, value=None),
        gr.update(choices=choices, value=None),
    )


def _handle_save_garment(
    files: Optional[Iterable[Any]],
    name_prefix: str,
    category: str,
    description: str,
    preserve_logo: bool,
    store: MetadataStore,
    config: AppConfig,
):
    file_paths = _resolve_file_paths(files)
    if not file_paths:
        return (
            "No files selected.",
            _build_garment_gallery(store.list_garments()),
            gr.update(choices=_build_garment_choices(store.list_garments()), value=None),
            gr.update(choices=_build_garment_choices(store.list_garments()), value=None),
            gr.update(choices=_build_garment_choices(store.list_garments()), value=None),
            gr.update(choices=_build_garment_choices(store.list_garments()), value=None),
            gr.update(choices=_build_garment_choices(store.list_garments()), value=None),
        )

    saved = 0
    total = len(file_paths)
    for index, file_path in enumerate(file_paths):
        asset_id = generate_id("garment")
        asset_name = _format_asset_name(name_prefix, asset_id, index, total)
        paths = save_garment_asset(file_path, asset_id, config)
        store.add_garment(
            {
                "id": asset_id,
                "name": asset_name,
                "image_path": paths.image_path,
                "thumbnail_path": paths.thumbnail_path,
                "category": category,
                "description": description,
                "must_preserve_logo": preserve_logo,
            }
        )
        saved += 1

    garments = store.list_garments()
    choices = _build_garment_choices(garments)
    gallery = _build_garment_gallery(garments)
    status = f"Saved {saved} garment(s)."

    return (
        status,
        gallery,
        gr.update(choices=choices, value=None),
        gr.update(choices=choices, value=None),
        gr.update(choices=choices, value=None),
        gr.update(choices=choices, value=None),
        gr.update(choices=choices, value=None),
    )


def _handle_generate_single(
    person_id: str,
    garment_id: str,
    provider_name: str,
    quality: str,
    aspect_ratio: str,
    num_outputs: int,
    scene_description: str,
    negative_prompt: str,
    store: MetadataStore,
    providers: dict[str, GenerationProvider],
    config: AppConfig,
):
    if not person_id or not garment_id:
        return "Please select both person and garment.", []

    person = store.get_person(person_id)
    garment = store.get_garment(garment_id)
    if not person or not garment:
        return "Invalid person or garment selection.", []

    prompt = build_tryon_prompt(
        person_description=person.get("description"),
        garment_description=garment.get("description"),
        scene_description=scene_description,
    )

    provider = providers.get(provider_name)
    if not provider:
        return f"Unknown provider: {provider_name}", []

    error_message = provider.validate_environment()
    if error_message and provider.name != "dummy":
        result_records = _save_failed_result(
            store,
            person_id,
            garment_id,
            provider.name,
            error_message,
            prompt,
            negative_prompt,
        )
        return f"Failed: {error_message}", _build_result_gallery(result_records)

    request = TryOnRequest(
        person_image_path=_to_absolute_path(person["image_path"], config.project_root),
        garment_image_path=_to_absolute_path(garment["image_path"], config.project_root),
        garment_category=garment.get("category", ""),
        prompt=prompt,
        negative_prompt=negative_prompt,
        aspect_ratio=aspect_ratio,
        num_outputs=int(num_outputs),
        output_dir=str(config.app_data_dir / "results" / "images"),
        quality_mode=quality,
    )

    result = provider.generate_tryon_image(request)
    result_records = _save_provider_results(
        store,
        result,
        person_id,
        garment_id,
        prompt,
        negative_prompt,
        config.project_root,
    )

    if result.status != "success":
        message = f"Failed: {result.error_message or 'Unknown error'}"
    else:
        message = f"Generated {len(result.output_paths)} image(s) with {result.provider}."

    return message, _build_result_gallery(result_records)


def _handle_generate_batch(
    person_ids: list[str],
    garment_ids: list[str],
    provider_name: str,
    quality: str,
    aspect_ratio: str,
    num_outputs: int,
    scene_description: str,
    negative_prompt: str,
    store: MetadataStore,
    providers: dict[str, GenerationProvider],
    config: AppConfig,
):
    if not person_ids or not garment_ids:
        yield "Please select persons and garments.", []
        return

    provider = providers.get(provider_name)
    if not provider:
        yield f"Unknown provider: {provider_name}", []
        return

    error_message = provider.validate_environment()
    if error_message and provider.name != "dummy":
        yield f"Failed: {error_message}", []
        return

    total = len(person_ids) * len(garment_ids)
    completed = 0
    gallery_items: list[tuple[str, str]] = []

    for person_id in person_ids:
        for garment_id in garment_ids:
            person = store.get_person(person_id)
            garment = store.get_garment(garment_id)
            if not person or not garment:
                completed += 1
                continue

            prompt = build_tryon_prompt(
                person_description=person.get("description"),
                garment_description=garment.get("description"),
                scene_description=scene_description,
            )

            request = TryOnRequest(
                person_image_path=_to_absolute_path(person["image_path"], config.project_root),
                garment_image_path=_to_absolute_path(garment["image_path"], config.project_root),
                garment_category=garment.get("category", ""),
                prompt=prompt,
                negative_prompt=negative_prompt,
                aspect_ratio=aspect_ratio,
                num_outputs=int(num_outputs),
                output_dir=str(config.app_data_dir / "results" / "images"),
                quality_mode=quality,
            )

            result = provider.generate_tryon_image(request)
            records = _save_provider_results(
                store,
                result,
                person_id,
                garment_id,
                prompt,
                negative_prompt,
                config.project_root,
            )
            gallery_items.extend(_build_result_gallery(records))

            completed += 1
            yield f"Progress {completed}/{total}", gallery_items


def _refresh_canonical_options(person_id: str, garment_id: str, store: MetadataStore):
    if not person_id or not garment_id:
        return gr.update(choices=[], value=None), None, "Select person and garment."

    results = store.list_results_for_combo(person_id, garment_id)
    choices = _build_result_choices(results)
    canonical = store.get_canonical_image(person_id, garment_id)
    canonical_path = canonical.get("image_path") if canonical else None

    status = "Canonical image set." if canonical_path else "No canonical image for this combo."
    return gr.update(choices=choices, value=None), canonical_path, status


def _handle_set_canonical(person_id: str, garment_id: str, result_id: str, store: MetadataStore):
    if not person_id or not garment_id or not result_id:
        return "Select person, garment, and result.", None

    canonical = store.set_canonical_image(person_id, garment_id, result_id)
    if not canonical:
        return "Failed to set canonical image.", None

    return "Canonical image updated.", canonical.get("image_path")


def _handle_clear_canonical(person_id: str, garment_id: str, store: MetadataStore):
    if not person_id or not garment_id:
        return "Select person and garment.", None

    store.clear_canonical_image(person_id, garment_id)
    return "Canonical image cleared.", None


def _handle_refresh_history(result_type: str, person_id: str, garment_id: str, store: MetadataStore):
    results = store.list_results(person_id, garment_id, result_type)
    return f"Loaded {len(results)} result(s).", _build_result_gallery(results)


def _format_asset_name(prefix: str, asset_id: str, index: int, total: int) -> str:
    prefix = (prefix or "").strip()
    if not prefix:
        return asset_id
    if total > 1:
        return f"{prefix}_{index + 1}"
    return prefix


def _to_absolute_path(path: str, project_root: Path) -> str:
    path_obj = Path(path)
    if path_obj.is_absolute():
        return str(path_obj)
    return str(project_root / path_obj)


def _save_provider_results(
    store: MetadataStore,
    result,
    person_id: str,
    garment_id: str,
    prompt: str,
    negative_prompt: str,
    project_root: Path,
) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    if result.output_paths:
        for output_path in result.output_paths:
            record = {
                "id": generate_id("result"),
                "person_id": person_id,
                "garment_id": garment_id,
                "result_type": "image",
                "provider": result.provider,
                "model": result.model,
                "prompt": prompt,
                "negative_prompt": negative_prompt,
                "output_path": to_relative_path(Path(output_path), project_root),
                "seed": None,
                "status": result.status,
                "error_message": result.error_message,
                "is_canonical": False,
            }
            records.append(record)
    else:
        records.append(
            {
                "id": generate_id("result"),
                "person_id": person_id,
                "garment_id": garment_id,
                "result_type": "image",
                "provider": result.provider,
                "model": result.model,
                "prompt": prompt,
                "negative_prompt": negative_prompt,
                "output_path": "",
                "seed": None,
                "status": result.status,
                "error_message": result.error_message,
                "is_canonical": False,
            }
        )

    store.add_results(records)
    return records


def _save_failed_result(
    store: MetadataStore,
    person_id: str,
    garment_id: str,
    provider_name: str,
    error_message: str,
    prompt: str,
    negative_prompt: str,
) -> list[dict[str, Any]]:
    record = {
        "id": generate_id("result"),
        "person_id": person_id,
        "garment_id": garment_id,
        "result_type": "image",
        "provider": provider_name,
        "model": "stub",
        "prompt": prompt,
        "negative_prompt": negative_prompt,
        "output_path": "",
        "seed": None,
        "status": "failed",
        "error_message": error_message,
        "is_canonical": False,
    }
    store.add_results([record])
    return [record]
