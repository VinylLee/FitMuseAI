from __future__ import annotations

from typing import Optional

DEFAULT_TRYON_SCENE = (
    "Studio full-body fashion photo, neutral background, natural standing pose, "
    "realistic lighting, high detail, clothing fits the body naturally."
)

DEFAULT_NEGATIVE_PROMPT = (
    "face deformation, identity change, hairstyle change, skin tone change, "
    "extra limbs, malformed hands, clothing color shift, logo distortion, "
    "text deformation, low resolution, blurry, heavy AI artifacts"
)

DEFAULT_VIDEO_PROMPT_TEMPLATE = (
    "Generate a short realistic fashion video from this try-on image. "
    "Keep the same person identity, face, hairstyle, skin tone, and body shape. "
    "Keep the clothing exactly the same: color, fabric, shape, logo, and text. "
    "Motion: {motion_description}. "
    "Camera: stable, smooth, no sudden cuts."
)

def build_tryon_prompt(
    person_description: Optional[str],
    garment_description: Optional[str],
    scene_description: Optional[str],
) -> str:
    parts: list[str] = []
    if scene_description:
        parts.append(scene_description.strip())
    if person_description:
        parts.append(f"Person: {person_description.strip()}.")
    if garment_description:
        parts.append(f"Garment: {garment_description.strip()}.")
    if not parts:
        return DEFAULT_TRYON_SCENE
    return " ".join(parts)


def build_video_prompt(motion_description: str) -> str:
    return DEFAULT_VIDEO_PROMPT_TEMPLATE.format(motion_description=motion_description)
