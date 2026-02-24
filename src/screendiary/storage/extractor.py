"""Frame extraction from H.265 video segments via ffmpeg."""

from __future__ import annotations

import hashlib
import subprocess
from collections import OrderedDict
from pathlib import Path

import structlog

from ..config import Config

log = structlog.get_logger()


class FrameExtractor:
    def __init__(self, config: Config) -> None:
        self.config = config
        self._cache: OrderedDict[tuple[str, int], bytes] = OrderedDict()
        self._max_cache = config.storage.frame_cache_size
        self._disk_cache_dir = config.storage.data_path / "frame_cache"
        self._disk_cache_dir.mkdir(parents=True, exist_ok=True)

    def _disk_cache_path(self, segment_path: str, offset_ms: int) -> Path:
        key = f"{segment_path}:{offset_ms}"
        h = hashlib.md5(key.encode()).hexdigest()
        return self._disk_cache_dir / f"{h}.webp"

    def extract_frame(self, segment_path: str, offset_ms: int) -> bytes | None:
        """Extract a single frame from a video segment at the given offset."""
        cache_key = (segment_path, offset_ms)

        # 1. Memory cache (LRU)
        if cache_key in self._cache:
            self._cache.move_to_end(cache_key)
            return self._cache[cache_key]

        # 2. Disk cache
        disk_path = self._disk_cache_path(segment_path, offset_ms)
        if disk_path.is_file():
            frame_data = disk_path.read_bytes()
            if frame_data:
                self._cache[cache_key] = frame_data
                if len(self._cache) > self._max_cache:
                    self._cache.popitem(last=False)
                return frame_data

        # 3. Extract via ffmpeg
        offset_sec = offset_ms / 1000.0
        try:
            result = subprocess.run(
                [
                    "ffmpeg",
                    "-ss", f"{offset_sec:.3f}",
                    "-i", segment_path,
                    "-frames:v", "1",
                    "-c:v", "libwebp",
                    "-quality", "80",
                    "-f", "image2pipe",
                    "-",
                ],
                capture_output=True,
                timeout=10,
            )
            if result.returncode != 0:
                log.error(
                    "frame_extraction_failed",
                    segment=segment_path,
                    offset_ms=offset_ms,
                    stderr=result.stderr.decode()[:200],
                )
                return None

            frame_data = result.stdout
            if not frame_data:
                return None

            # Memory cache (LRU)
            self._cache[cache_key] = frame_data
            if len(self._cache) > self._max_cache:
                self._cache.popitem(last=False)

            # Disk cache (persistent)
            try:
                disk_path.write_bytes(frame_data)
            except OSError:
                pass

            return frame_data

        except subprocess.TimeoutExpired:
            log.error("frame_extraction_timeout", segment=segment_path, offset_ms=offset_ms)
            return None
        except Exception as e:
            log.error("frame_extraction_error", error=str(e))
            return None
