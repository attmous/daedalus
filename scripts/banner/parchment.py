"""Clean banner background baked once and reused on every frame."""

from __future__ import annotations

from PIL import Image

from . import config


def make_parchment(w: int = config.W, h: int = config.H) -> Image.Image:
    """Flat neutral background with no texture or colour wash."""
    return Image.new("RGB", (w, h), (242, 244, 242))
