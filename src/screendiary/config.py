"""Configuration loading and validation."""

from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

import structlog

log = structlog.get_logger()

_SEARCH_PATHS = [
    lambda: os.environ.get("SCREENDIARY_CONFIG"),
    lambda: "config.toml",
    lambda: str(Path.home() / ".config" / "screendiary" / "config.toml"),
]


@dataclass
class CaptureConfig:
    interval: int = 2
    similarity_threshold: float = 0.98
    tool: str = "spectacle"

    def __post_init__(self) -> None:
        if not 1 <= self.interval <= 30:
            raise ValueError(f"capture.interval must be 1-30, got {self.interval}")
        if not 0.0 <= self.similarity_threshold <= 1.0:
            raise ValueError(f"capture.similarity_threshold must be 0.0-1.0")


@dataclass
class StorageConfig:
    data_dir: str = "data"
    format: str = "webp"
    quality: int = 80
    thumbnail_width: int = 320
    max_storage_gb: int = 200
    archive_after_minutes: int = 10
    segment_duration_minutes: int = 5
    h265_crf: int = 28
    h265_preset: str = "medium"
    frame_cache_size: int = 100

    @property
    def data_path(self) -> Path:
        return Path(self.data_dir).resolve()

    @property
    def screenshots_path(self) -> Path:
        return self.data_path / "screenshots"

    @property
    def archive_path(self) -> Path:
        return self.data_path / "archive"

    @property
    def db_path(self) -> Path:
        return self.data_path / "screendiary.db"


@dataclass
class OCRConfig:
    languages: str = "deu+eng"
    psm: int = 3
    min_text_length: int = 10
    workers: int = 2


@dataclass
class AIConfig:
    api_base: str = "http://localhost:8000/v1"
    api_key: str = ""
    embedding_model: str = "text-embedding-3-small"
    chat_model: str = "gpt-4"
    chunk_max_tokens: int = 512
    enabled: bool = True


@dataclass
class WebConfig:
    host: str = "127.0.0.1"
    port: int = 18787
    page_size: int = 50


@dataclass
class LoggingConfig:
    level: str = "INFO"


@dataclass
class Config:
    capture: CaptureConfig = field(default_factory=CaptureConfig)
    storage: StorageConfig = field(default_factory=StorageConfig)
    ocr: OCRConfig = field(default_factory=OCRConfig)
    ai: AIConfig = field(default_factory=AIConfig)
    web: WebConfig = field(default_factory=WebConfig)
    logging: LoggingConfig = field(default_factory=LoggingConfig)
    _config_path: str | None = None


def _find_config() -> Path | None:
    for getter in _SEARCH_PATHS:
        path_str = getter()
        if path_str and Path(path_str).is_file():
            return Path(path_str).resolve()
    return None


def _build_section(cls: type, data: dict) -> object:
    known = {f.name for f in cls.__dataclass_fields__.values()}
    filtered = {k: v for k, v in data.items() if k in known}
    return cls(**filtered)


def load_config(path: str | Path | None = None) -> Config:
    """Load configuration from TOML file."""
    if path is not None:
        config_path = Path(path).resolve()
        if not config_path.is_file():
            raise FileNotFoundError(f"Config not found: {config_path}")
    else:
        config_path = _find_config()

    if config_path is None:
        log.warning("no_config_found, using defaults")
        return Config()

    log.info("loading_config", path=str(config_path))
    with open(config_path, "rb") as f:
        raw = tomllib.load(f)

    cfg = Config(
        capture=_build_section(CaptureConfig, raw.get("capture", {})),
        storage=_build_section(StorageConfig, raw.get("storage", {})),
        ocr=_build_section(OCRConfig, raw.get("ocr", {})),
        ai=_build_section(AIConfig, raw.get("ai", {})),
        web=_build_section(WebConfig, raw.get("web", {})),
        logging=_build_section(LoggingConfig, raw.get("logging", {})),
        _config_path=str(config_path),
    )
    return cfg
