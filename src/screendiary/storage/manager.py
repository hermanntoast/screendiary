"""Storage orchestration - transparent access to WebP (live) and Video (archived) frames."""

from __future__ import annotations

from pathlib import Path

import structlog

from ..config import Config
from ..db import Database
from ..models import MonitorCapture
from .extractor import FrameExtractor

log = structlog.get_logger()


class StorageManager:
    def __init__(self, config: Config, db: Database) -> None:
        self.config = config
        self.db = db
        self.extractor = FrameExtractor(config)

    def get_frame(self, monitor_capture: MonitorCapture) -> bytes | None:
        """Get frame bytes (WebP) for a monitor capture, from live storage or video archive."""
        # Try live WebP first
        if monitor_capture.filepath:
            path = Path(monitor_capture.filepath)
            if path.is_file():
                return path.read_bytes()

        # Try archived video
        if monitor_capture.segment_path and monitor_capture.segment_offset_ms is not None:
            return self.extractor.extract_frame(
                monitor_capture.segment_path,
                monitor_capture.segment_offset_ms,
            )

        log.warning(
            "frame_not_found",
            monitor_capture_id=monitor_capture.id,
            filepath=monitor_capture.filepath,
            segment_path=monitor_capture.segment_path,
        )
        return None

    def get_thumbnail(self, screenshot_id: int) -> bytes | None:
        """Get thumbnail bytes for a screenshot."""
        s = self.db.get_screenshot(screenshot_id)
        if not s or not s.filepath_thumb:
            return None
        path = Path(s.filepath_thumb)
        if path.is_file():
            return path.read_bytes()
        return None

    def get_screenshot_frame(
        self, screenshot_id: int, monitor_index: int = 0
    ) -> bytes | None:
        """Get a specific monitor's frame for a screenshot."""
        captures = self.db.get_monitor_captures(screenshot_id)
        for mc in captures:
            if mc.monitor_index == monitor_index:
                return self.get_frame(mc)
        return None
