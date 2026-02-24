"""Data models."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class Monitor:
    name: str
    index: int
    x: int
    y: int
    width: int
    height: int


@dataclass
class MonitorCapture:
    id: int | None = None
    screenshot_id: int | None = None
    monitor_name: str = ""
    monitor_index: int = 0
    filepath: str | None = None
    segment_path: str | None = None
    segment_offset_ms: int | None = None
    x: int = 0
    y: int = 0
    width: int = 0
    height: int = 0


@dataclass
class Screenshot:
    id: int | None = None
    timestamp: datetime = field(default_factory=datetime.now)
    date: str = ""
    width: int = 0
    height: int = 0
    file_size: int = 0
    similarity: float = 0.0
    storage_type: str = "live"
    segment_path: str | None = None
    segment_offset_ms: int | None = None
    filepath_thumb: str | None = None
    monitors: list[MonitorCapture] = field(default_factory=list)


@dataclass
class OCRResult:
    id: int | None = None
    screenshot_id: int | None = None
    monitor_capture_id: int | None = None
    text: str = ""
    language: str = ""
    confidence: float = 0.0


@dataclass
class Embedding:
    id: int | None = None
    screenshot_id: int | None = None
    vector: bytes = b""
    model: str = ""
    dimensions: int = 0
    text_hash: str = ""


@dataclass
class VideoSegment:
    id: int | None = None
    date: str = ""
    monitor_index: int = 0
    filepath: str = ""
    start_time: datetime | None = None
    end_time: datetime | None = None
    frame_count: int = 0
    file_size: int = 0


@dataclass
class OCRWord:
    id: int | None = None
    ocr_result_id: int | None = None
    monitor_capture_id: int | None = None
    word: str = ""
    left: int = 0
    top: int = 0
    width: int = 0
    height: int = 0
    confidence: float = 0.0


@dataclass
class WindowEvent:
    id: int | None = None
    screenshot_id: int | None = None
    timestamp: datetime = field(default_factory=datetime.now)
    app_class: str = ""
    app_name: str = ""
    window_title: str = ""
    desktop_file: str = ""
    pid: int = 0
    browser_domain: str = ""


@dataclass
class SearchResult:
    screenshot: Screenshot
    ocr_text: str = ""
    score: float = 0.0
    highlights: list[str] = field(default_factory=list)
