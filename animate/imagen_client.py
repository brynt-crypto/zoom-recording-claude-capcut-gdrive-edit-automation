"""Google Imagen (google-genai) image generation — the `imagen` provider.

Exposes prompt-building + a single-image generate call. Batch orchestration
(idempotency, dry-run, cost, retries) lives in animate/providers.py so every
provider shares it.
"""
from __future__ import annotations
from pathlib import Path

from . import config


def full_prompt(scene: dict, style: str) -> str:
    """Combine the built-in style anchor + global style + the scene prompt."""
    parts = [config.STYLE_ANCHOR]
    if style.strip():
        parts.append(style.strip())
    parts.append(scene["image_prompt"].strip())
    return ". ".join(p.rstrip(". ") for p in parts if p) + "."


def make_client(api_key: str):
    from google import genai
    return genai.Client(api_key=api_key)


def generate_one(client, scene: dict, style: str, model: str, out: Path) -> None:
    """Generate one image for `scene` and save it to `out`. Raises on failure."""
    from google.genai import types

    cfg = types.GenerateImagesConfig(
        number_of_images=1,
        aspect_ratio=config.IMAGEN_ASPECT,
        image_size=config.IMAGEN_SIZE,
        person_generation="allow_adult",
    )
    resp = client.models.generate_images(
        model=model, prompt=full_prompt(scene, style), config=cfg)
    imgs = getattr(resp, "generated_images", None) or []
    if not imgs:
        raise RuntimeError("Imagen returned no image (prompt may have been filtered)")
    imgs[0].image.save(str(out))
