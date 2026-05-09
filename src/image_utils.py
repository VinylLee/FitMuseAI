from __future__ import annotations

from pathlib import Path
from typing import Optional

from PIL import Image, ImageDraw, ImageOps


def normalize_image(input_path: str, output_path: str, max_size: int = 2048) -> str:
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)

    with Image.open(input_path) as image:
        image = ImageOps.exif_transpose(image)
        image = image.convert("RGB")
        image.thumbnail((max_size, max_size))
        image.save(output, format="PNG", optimize=True)

    return str(output)


def create_thumbnail(input_path: str, output_path: str, size: int = 512) -> str:
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)

    with Image.open(input_path) as image:
        image = ImageOps.exif_transpose(image)
        image = image.convert("RGB")
        image = ImageOps.fit(image, (size, size))
        image.save(output, format="JPEG", quality=85, optimize=True)

    return str(output)


def create_placeholder_tryon(
    person_image_path: str,
    garment_image_path: Optional[str],
    output_path: str,
    label: str = "DUMMY TRYON",
) -> str:
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)

    with Image.open(person_image_path) as person_image:
        person_image = ImageOps.exif_transpose(person_image)
        person_image = person_image.convert("RGB")

        if garment_image_path:
            with Image.open(garment_image_path) as garment_image:
                garment_image = ImageOps.exif_transpose(garment_image)
                garment_image = garment_image.convert("RGB")
                _build_placeholder(person_image, garment_image, output, label)
        else:
            _build_placeholder(person_image, person_image, output, label)

    return str(output)


def _build_placeholder(person_image: Image.Image, garment_image: Image.Image, output: Path, label: str) -> None:
    label_height = 48
    target_width = max(person_image.width, garment_image.width)
    target_height = max(person_image.height, garment_image.height)

    canvas = Image.new("RGB", (target_width * 2, target_height + label_height), color=(245, 245, 245))

    person_fit = ImageOps.contain(person_image, (target_width, target_height))
    garment_fit = ImageOps.contain(garment_image, (target_width, target_height))

    canvas.paste(person_fit, (0, label_height))
    canvas.paste(garment_fit, (target_width, label_height))

    draw = ImageDraw.Draw(canvas)
    draw.rectangle([0, 0, canvas.width, label_height], fill=(30, 30, 30))
    draw.text((12, 16), label, fill=(255, 255, 255))

    canvas.save(output, format="PNG", optimize=True)
