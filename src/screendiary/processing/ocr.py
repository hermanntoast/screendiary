"""Tesseract OCR wrapper."""

from __future__ import annotations

import asyncio
import os

import pytesseract
import structlog
from PIL import Image

from ..config import Config

log = structlog.get_logger()

# Limit Tesseract's internal OpenMP threads (one thread per worker is enough)
os.environ.setdefault("OMP_THREAD_LIMIT", "1")

_OCR_MAX_WIDTH = 2000


def _prepare_image(image: Image.Image) -> Image.Image:
    """Downscale and convert to grayscale for faster OCR."""
    if image.width > _OCR_MAX_WIDTH:
        ratio = _OCR_MAX_WIDTH / image.width
        image = image.resize(
            (int(image.width * ratio), int(image.height * ratio)),
            Image.LANCZOS,
        )
    if image.mode != "L":
        image = image.convert("L")
    return image


def ocr_image(image: Image.Image, config: Config) -> tuple[str, float, list[dict]]:
    """Run Tesseract OCR on an image. Returns (text, confidence, word_boxes)."""
    try:
        scale = 1.0
        if image.width > _OCR_MAX_WIDTH:
            scale = image.width / _OCR_MAX_WIDTH
        prepared = _prepare_image(image)

        data = pytesseract.image_to_data(
            prepared,
            lang=config.ocr.languages,
            config=f"--psm {config.ocr.psm}",
            output_type=pytesseract.Output.DICT,
        )

        # Extract text, confidence, and word-level bounding boxes
        words = []
        confidences = []
        word_boxes = []
        for i, text in enumerate(data["text"]):
            text = text.strip()
            if text:
                words.append(text)
                conf = data["conf"][i]
                conf_val = float(conf) if isinstance(conf, (int, float)) and conf >= 0 else 0.0
                if conf_val >= 0:
                    confidences.append(conf_val)
                word_boxes.append({
                    "word": text,
                    "left": int(data["left"][i] * scale),
                    "top": int(data["top"][i] * scale),
                    "width": int(data["width"][i] * scale),
                    "height": int(data["height"][i] * scale),
                    "confidence": conf_val,
                })

        full_text = " ".join(words)
        avg_conf = sum(confidences) / len(confidences) if confidences else 0.0

        return full_text, avg_conf, word_boxes

    except Exception as e:
        log.error("ocr_error", error=str(e))
        return "", 0.0, []


async def ocr_image_async(
    image: Image.Image, config: Config
) -> tuple[str, float, list[dict]]:
    """Async wrapper for OCR (runs in thread pool)."""
    return await asyncio.to_thread(ocr_image, image, config)
