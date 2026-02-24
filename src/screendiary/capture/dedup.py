"""Pixel-difference based screenshot deduplication."""

from __future__ import annotations

import numpy as np
from PIL import Image

# Downscale target for fast comparison
_COMPARE_SIZE = (480, 300)


def image_similarity(img_a: Image.Image, img_b: Image.Image) -> float:
    """Compare two images by downscaled pixel difference. Returns 0.0-1.0 similarity."""
    a = np.asarray(img_a.resize(_COMPARE_SIZE, Image.BILINEAR).convert("RGB"), dtype=np.float32)
    b = np.asarray(img_b.resize(_COMPARE_SIZE, Image.BILINEAR).convert("RGB"), dtype=np.float32)
    diff = np.abs(a - b).mean()
    # Max possible diff is 255, normalize to 0-1 similarity
    return 1.0 - (diff / 255.0)


def is_duplicate(
    img_new: Image.Image,
    img_prev: Image.Image,
    threshold: float = 0.98,
) -> tuple[bool, float]:
    """Check if new image is too similar to previous. Returns (is_dup, similarity)."""
    sim = image_similarity(img_new, img_prev)
    return sim >= threshold, sim
