"""Screenshot capture via spectacle + Pillow crop per monitor."""

from __future__ import annotations

import asyncio
import tempfile
from pathlib import Path

import structlog
from PIL import Image

from ..config import Config
from ..models import Monitor

log = structlog.get_logger()


async def _spectacle_gui_running() -> bool:
    """Check if the user has Spectacle open (GUI, not our --background call)."""
    try:
        proc = await asyncio.create_subprocess_exec(
            "pgrep", "-x", "spectacle",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
        )
        await proc.communicate()
        return proc.returncode == 0
    except OSError:
        return False


async def take_screenshot(config: Config) -> Image.Image | None:
    """Take a fullscreen screenshot using spectacle. Returns PIL Image or None on failure."""
    # Wait if the user has Spectacle GUI open
    if await _spectacle_gui_running():
        log.debug("screenshot_skipped_spectacle_gui")
        return None

    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
        tmp_path = tmp.name

    try:
        proc = await asyncio.create_subprocess_exec(
            config.capture.tool,
            "--background", "--nonotify", "--fullscreen",
            "--output", tmp_path,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()

        if proc.returncode != 0:
            log.error("screenshot_failed", returncode=proc.returncode, stderr=stderr.decode())
            return None

        # Validate output file before opening (spectacle may produce
        # empty/corrupt files when the user has the GUI open)
        tmp = Path(tmp_path)
        if not tmp.exists() or tmp.stat().st_size == 0:
            log.warning("screenshot_empty", path=tmp_path)
            return None

        img = Image.open(tmp_path)
        img.load()
        return img
    except Exception as e:
        log.error("screenshot_error", error=str(e))
        return None
    finally:
        Path(tmp_path).unlink(missing_ok=True)


def crop_monitors(full_image: Image.Image, monitors: list[Monitor]) -> list[Image.Image]:
    """Crop full screenshot into per-monitor images."""
    crops = []
    for mon in monitors:
        box = (mon.x, mon.y, mon.x + mon.width, mon.y + mon.height)
        crops.append(full_image.crop(box))
    return crops


def save_webp(
    image: Image.Image,
    path: Path,
    quality: int = 80,
) -> int:
    """Save image as WebP, return file size in bytes."""
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(str(path), "WEBP", quality=quality)
    return path.stat().st_size


def save_thumbnail(
    image: Image.Image,
    path: Path,
    width: int = 320,
    quality: int = 75,
) -> int:
    """Save resized thumbnail as WebP."""
    ratio = width / image.width
    height = int(image.height * ratio)
    thumb = image.resize((width, height), Image.LANCZOS)
    return save_webp(thumb, path, quality)
