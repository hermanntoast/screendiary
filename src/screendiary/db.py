"""SQLite database layer with WAL mode and FTS5."""

from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path

import structlog

from .config import Config
from .models import (
    Embedding,
    MonitorCapture,
    OCRResult,
    OCRWord,
    Screenshot,
    VideoSegment,
    WindowEvent,
)

log = structlog.get_logger()

SCHEMA_VERSION = 4

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS app_meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS screenshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    date TEXT NOT NULL,
    width INTEGER NOT NULL DEFAULT 0,
    height INTEGER NOT NULL DEFAULT 0,
    file_size INTEGER NOT NULL DEFAULT 0,
    similarity REAL NOT NULL DEFAULT 0.0,
    storage_type TEXT NOT NULL DEFAULT 'live',
    segment_path TEXT,
    segment_offset_ms INTEGER,
    filepath_thumb TEXT
);

CREATE TABLE IF NOT EXISTS monitor_captures (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    screenshot_id INTEGER NOT NULL REFERENCES screenshots(id) ON DELETE CASCADE,
    monitor_name TEXT NOT NULL,
    monitor_index INTEGER NOT NULL,
    filepath TEXT,
    segment_path TEXT,
    segment_offset_ms INTEGER,
    x INTEGER NOT NULL DEFAULT 0,
    y INTEGER NOT NULL DEFAULT 0,
    w INTEGER NOT NULL DEFAULT 0,
    h INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS ocr_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    screenshot_id INTEGER NOT NULL REFERENCES screenshots(id) ON DELETE CASCADE,
    monitor_capture_id INTEGER REFERENCES monitor_captures(id) ON DELETE CASCADE,
    text TEXT NOT NULL,
    language TEXT NOT NULL DEFAULT '',
    confidence REAL NOT NULL DEFAULT 0.0
);

CREATE TABLE IF NOT EXISTS embeddings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    screenshot_id INTEGER NOT NULL REFERENCES screenshots(id) ON DELETE CASCADE,
    vector BLOB NOT NULL,
    model TEXT NOT NULL,
    dimensions INTEGER NOT NULL DEFAULT 0,
    text_hash TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS video_segments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT NOT NULL,
    monitor_index INTEGER NOT NULL,
    filepath TEXT NOT NULL,
    start_time TEXT NOT NULL,
    end_time TEXT NOT NULL,
    frame_count INTEGER NOT NULL DEFAULT 0,
    file_size INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS ocr_words (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ocr_result_id INTEGER NOT NULL REFERENCES ocr_results(id) ON DELETE CASCADE,
    monitor_capture_id INTEGER NOT NULL REFERENCES monitor_captures(id) ON DELETE CASCADE,
    word TEXT NOT NULL,
    left_x INTEGER NOT NULL DEFAULT 0,
    top_y INTEGER NOT NULL DEFAULT 0,
    width INTEGER NOT NULL DEFAULT 0,
    height INTEGER NOT NULL DEFAULT 0,
    confidence REAL NOT NULL DEFAULT 0.0
);

CREATE TABLE IF NOT EXISTS window_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    screenshot_id INTEGER NOT NULL REFERENCES screenshots(id) ON DELETE CASCADE,
    timestamp TEXT NOT NULL,
    app_class TEXT NOT NULL DEFAULT '',
    app_name TEXT NOT NULL DEFAULT '',
    window_title TEXT NOT NULL DEFAULT '',
    desktop_file TEXT NOT NULL DEFAULT '',
    pid INTEGER NOT NULL DEFAULT 0,
    browser_domain TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS activity_day_summaries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT NOT NULL UNIQUE,
    summary_text TEXT NOT NULL,
    session_labels TEXT NOT NULL DEFAULT '',
    model TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    event_count INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_window_events_screenshot ON window_events(screenshot_id);
CREATE INDEX IF NOT EXISTS idx_window_events_date ON window_events(timestamp);
CREATE INDEX IF NOT EXISTS idx_window_events_app ON window_events(app_class);

CREATE INDEX IF NOT EXISTS idx_screenshots_timestamp ON screenshots(timestamp);
CREATE INDEX IF NOT EXISTS idx_screenshots_date ON screenshots(date);
CREATE INDEX IF NOT EXISTS idx_screenshots_storage ON screenshots(storage_type);
CREATE INDEX IF NOT EXISTS idx_monitor_captures_screenshot ON monitor_captures(screenshot_id);
CREATE INDEX IF NOT EXISTS idx_ocr_results_screenshot ON ocr_results(screenshot_id);
CREATE INDEX IF NOT EXISTS idx_ocr_words_monitor_capture ON ocr_words(monitor_capture_id);
CREATE INDEX IF NOT EXISTS idx_embeddings_screenshot ON embeddings(screenshot_id);
CREATE INDEX IF NOT EXISTS idx_video_segments_date ON video_segments(date);
"""

FTS5_SQL = """
CREATE VIRTUAL TABLE IF NOT EXISTS ocr_fts USING fts5(
    text,
    content='ocr_results',
    content_rowid='id',
    tokenize='unicode61 remove_diacritics 2'
);

CREATE TRIGGER IF NOT EXISTS ocr_fts_insert AFTER INSERT ON ocr_results BEGIN
    INSERT INTO ocr_fts(rowid, text) VALUES (new.id, new.text);
END;

CREATE TRIGGER IF NOT EXISTS ocr_fts_delete AFTER DELETE ON ocr_results BEGIN
    INSERT INTO ocr_fts(ocr_fts, rowid, text) VALUES('delete', old.id, old.text);
END;

CREATE TRIGGER IF NOT EXISTS ocr_fts_update AFTER UPDATE ON ocr_results BEGIN
    INSERT INTO ocr_fts(ocr_fts, rowid, text) VALUES('delete', old.id, old.text);
    INSERT INTO ocr_fts(rowid, text) VALUES (new.id, new.text);
END;
"""


class Database:
    def __init__(self, config: Config) -> None:
        self.config = config
        self.db_path = config.storage.db_path
        self._conn: sqlite3.Connection | None = None

    @property
    def conn(self) -> sqlite3.Connection:
        if self._conn is None:
            raise RuntimeError("Database not initialized. Call init() first.")
        return self._conn

    def init(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA foreign_keys=ON")
        self._conn.execute("PRAGMA busy_timeout=5000")
        self._conn.executescript(SCHEMA_SQL)
        self._conn.executescript(FTS5_SQL)
        self._migrate()
        # Set schema version
        self._conn.execute(
            "INSERT OR REPLACE INTO app_meta (key, value) VALUES (?, ?)",
            ("schema_version", str(SCHEMA_VERSION)),
        )
        self._conn.commit()
        log.info("database_initialized", path=str(self.db_path))

    def _migrate(self) -> None:
        """Run schema migrations from current version to SCHEMA_VERSION."""
        row = self.conn.execute(
            "SELECT value FROM app_meta WHERE key = 'schema_version'"
        ).fetchone()
        current = int(row["value"]) if row else 1

        if current < 2:
            # v2: add ocr_words table (already in SCHEMA_SQL via CREATE IF NOT EXISTS)
            log.info("migration_v2", msg="ocr_words table added")

        if current < 3:
            # v3: add window_events table (already in SCHEMA_SQL via CREATE IF NOT EXISTS)
            log.info("migration_v3", msg="window_events table added")

        if current < 4:
            # v4: add activity_day_summaries table (already in SCHEMA_SQL via CREATE IF NOT EXISTS)
            log.info("migration_v4", msg="activity_day_summaries table added")

        self.conn.commit()

    def close(self) -> None:
        if self._conn:
            self._conn.close()
            self._conn = None

    # -- Screenshots --

    def insert_screenshot(self, s: Screenshot) -> int:
        cur = self.conn.execute(
            """INSERT INTO screenshots
               (timestamp, date, width, height, file_size, similarity,
                storage_type, segment_path, segment_offset_ms, filepath_thumb)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                s.timestamp.isoformat(),
                s.date,
                s.width,
                s.height,
                s.file_size,
                s.similarity,
                s.storage_type,
                s.segment_path,
                s.segment_offset_ms,
                s.filepath_thumb,
            ),
        )
        self.conn.commit()
        return cur.lastrowid

    def insert_monitor_capture(self, mc: MonitorCapture) -> int:
        cur = self.conn.execute(
            """INSERT INTO monitor_captures
               (screenshot_id, monitor_name, monitor_index, filepath,
                segment_path, segment_offset_ms, x, y, w, h)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                mc.screenshot_id,
                mc.monitor_name,
                mc.monitor_index,
                mc.filepath,
                mc.segment_path,
                mc.segment_offset_ms,
                mc.x,
                mc.y,
                mc.width,
                mc.height,
            ),
        )
        self.conn.commit()
        return cur.lastrowid

    def get_screenshot(self, screenshot_id: int) -> Screenshot | None:
        row = self.conn.execute(
            "SELECT * FROM screenshots WHERE id = ?", (screenshot_id,)
        ).fetchone()
        if not row:
            return None
        return self._row_to_screenshot(row)

    def get_screenshots(
        self,
        date: str | None = None,
        offset: int = 0,
        limit: int = 50,
    ) -> list[Screenshot]:
        if date:
            rows = self.conn.execute(
                """SELECT * FROM screenshots WHERE date = ?
                   ORDER BY timestamp DESC LIMIT ? OFFSET ?""",
                (date, limit, offset),
            ).fetchall()
        else:
            rows = self.conn.execute(
                """SELECT * FROM screenshots
                   ORDER BY timestamp DESC LIMIT ? OFFSET ?""",
                (limit, offset),
            ).fetchall()
        return [self._row_to_screenshot(r) for r in rows]

    def get_screenshot_count(self, date: str | None = None) -> int:
        if date:
            row = self.conn.execute(
                "SELECT COUNT(*) FROM screenshots WHERE date = ?", (date,)
            ).fetchone()
        else:
            row = self.conn.execute("SELECT COUNT(*) FROM screenshots").fetchone()
        return row[0]

    def get_dates(self) -> list[dict]:
        rows = self.conn.execute(
            """SELECT date, COUNT(*) as count FROM screenshots
               GROUP BY date ORDER BY date DESC"""
        ).fetchall()
        return [{"date": r["date"], "count": r["count"]} for r in rows]

    def get_monitor_captures(self, screenshot_id: int) -> list[MonitorCapture]:
        rows = self.conn.execute(
            "SELECT * FROM monitor_captures WHERE screenshot_id = ? ORDER BY monitor_index",
            (screenshot_id,),
        ).fetchall()
        return [self._row_to_monitor_capture(r) for r in rows]

    # -- OCR --

    def insert_ocr_result(self, ocr: OCRResult) -> int:
        cur = self.conn.execute(
            """INSERT INTO ocr_results
               (screenshot_id, monitor_capture_id, text, language, confidence)
               VALUES (?, ?, ?, ?, ?)""",
            (
                ocr.screenshot_id,
                ocr.monitor_capture_id,
                ocr.text,
                ocr.language,
                ocr.confidence,
            ),
        )
        self.conn.commit()
        return cur.lastrowid

    def get_ocr_text(self, screenshot_id: int) -> str:
        rows = self.conn.execute(
            "SELECT text FROM ocr_results WHERE screenshot_id = ? ORDER BY monitor_capture_id",
            (screenshot_id,),
        ).fetchall()
        return "\n\n".join(r["text"] for r in rows if r["text"])

    def get_ocr_for_monitor(self, monitor_capture_id: int) -> str:
        row = self.conn.execute(
            "SELECT text FROM ocr_results WHERE monitor_capture_id = ?",
            (monitor_capture_id,),
        ).fetchone()
        return row["text"] if row else ""

    # -- OCR Words --

    def insert_ocr_words(self, words: list[OCRWord]) -> None:
        """Batch insert OCR word-level bounding boxes."""
        self.conn.executemany(
            """INSERT INTO ocr_words
               (ocr_result_id, monitor_capture_id, word, left_x, top_y, width, height, confidence)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            [
                (w.ocr_result_id, w.monitor_capture_id, w.word,
                 w.left, w.top, w.width, w.height, w.confidence)
                for w in words
            ],
        )
        self.conn.commit()

    def get_ocr_words_for_screenshot(self, screenshot_id: int) -> dict[int, list[dict]]:
        """Get all OCR words for a screenshot, grouped by monitor_capture_id."""
        rows = self.conn.execute(
            """SELECT ow.* FROM ocr_words ow
               JOIN monitor_captures mc ON mc.id = ow.monitor_capture_id
               WHERE mc.screenshot_id = ?
               ORDER BY ow.monitor_capture_id, ow.id""",
            (screenshot_id,),
        ).fetchall()
        grouped: dict[int, list[dict]] = {}
        for r in rows:
            mc_id = r["monitor_capture_id"]
            grouped.setdefault(mc_id, []).append({
                "word": r["word"],
                "left": r["left_x"],
                "top": r["top_y"],
                "width": r["width"],
                "height": r["height"],
                "confidence": r["confidence"],
            })
        return grouped

    # -- Timeline --

    def get_timeline(self, date: str) -> list[dict]:
        """Get all screenshot IDs + timestamps for a given day, chronologically."""
        rows = self.conn.execute(
            """SELECT id, timestamp FROM screenshots
               WHERE date = ? ORDER BY timestamp ASC""",
            (date,),
        ).fetchall()
        return [{"id": r["id"], "timestamp": r["timestamp"]} for r in rows]

    # -- FTS5 Search --

    def search_fts(self, query: str, limit: int = 50) -> list[dict]:
        rows = self.conn.execute(
            """SELECT ocr_results.screenshot_id, ocr_results.text,
                      bm25(ocr_fts) as rank,
                      snippet(ocr_fts, 0, '<mark>', '</mark>', '...', 32) as snippet
               FROM ocr_fts
               JOIN ocr_results ON ocr_results.id = ocr_fts.rowid
               WHERE ocr_fts MATCH ?
               ORDER BY rank
               LIMIT ?""",
            (query, limit),
        ).fetchall()
        return [dict(r) for r in rows]

    # -- Embeddings --

    def insert_embedding(self, emb: Embedding) -> int:
        cur = self.conn.execute(
            """INSERT INTO embeddings
               (screenshot_id, vector, model, dimensions, text_hash)
               VALUES (?, ?, ?, ?, ?)""",
            (emb.screenshot_id, emb.vector, emb.model, emb.dimensions, emb.text_hash),
        )
        self.conn.commit()
        return cur.lastrowid

    def get_all_embeddings(self) -> list[tuple[int, bytes]]:
        rows = self.conn.execute(
            "SELECT screenshot_id, vector FROM embeddings"
        ).fetchall()
        return [(r["screenshot_id"], r["vector"]) for r in rows]

    def has_embedding(self, screenshot_id: int, text_hash: str) -> bool:
        row = self.conn.execute(
            "SELECT 1 FROM embeddings WHERE screenshot_id = ? AND text_hash = ?",
            (screenshot_id, text_hash),
        ).fetchone()
        return row is not None

    # -- Video Segments --

    def insert_video_segment(self, seg: VideoSegment) -> int:
        cur = self.conn.execute(
            """INSERT INTO video_segments
               (date, monitor_index, filepath, start_time, end_time, frame_count, file_size)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                seg.date,
                seg.monitor_index,
                seg.filepath,
                seg.start_time.isoformat() if seg.start_time else "",
                seg.end_time.isoformat() if seg.end_time else "",
                seg.frame_count,
                seg.file_size,
            ),
        )
        self.conn.commit()
        return cur.lastrowid

    def update_screenshot_archived(
        self,
        screenshot_id: int,
        segment_path: str,
        segment_offset_ms: int,
    ) -> None:
        self.conn.execute(
            """UPDATE screenshots
               SET storage_type = 'archived', segment_path = ?, segment_offset_ms = ?
               WHERE id = ?""",
            (segment_path, segment_offset_ms, screenshot_id),
        )
        self.conn.commit()

    def update_monitor_capture_archived(
        self,
        monitor_capture_id: int,
        segment_path: str,
        segment_offset_ms: int,
    ) -> None:
        self.conn.execute(
            """UPDATE monitor_captures
               SET filepath = NULL, segment_path = ?, segment_offset_ms = ?
               WHERE id = ?""",
            (segment_path, segment_offset_ms, monitor_capture_id),
        )
        self.conn.commit()

    def get_live_screenshots_before(self, before: datetime) -> list[Screenshot]:
        rows = self.conn.execute(
            """SELECT * FROM screenshots
               WHERE storage_type = 'live' AND timestamp < ?
               ORDER BY timestamp ASC""",
            (before.isoformat(),),
        ).fetchall()
        return [self._row_to_screenshot(r) for r in rows]

    def get_total_storage_bytes(self) -> int:
        row = self.conn.execute(
            "SELECT COALESCE(SUM(file_size), 0) FROM video_segments"
        ).fetchone()
        archive = row[0]
        row = self.conn.execute(
            "SELECT COALESCE(SUM(file_size), 0) FROM screenshots WHERE storage_type = 'live'"
        ).fetchone()
        live = row[0]
        return archive + live

    def get_oldest_video_segments(self, limit: int = 10) -> list[VideoSegment]:
        rows = self.conn.execute(
            "SELECT * FROM video_segments ORDER BY start_time ASC LIMIT ?", (limit,)
        ).fetchall()
        return [self._row_to_video_segment(r) for r in rows]

    def delete_video_segment(self, segment_id: int) -> None:
        self.conn.execute("DELETE FROM video_segments WHERE id = ?", (segment_id,))
        self.conn.commit()

    # -- Window Events --

    def insert_window_event(self, event: WindowEvent) -> int:
        cur = self.conn.execute(
            """INSERT INTO window_events
               (screenshot_id, timestamp, app_class, app_name,
                window_title, desktop_file, pid, browser_domain)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                event.screenshot_id,
                event.timestamp.isoformat(),
                event.app_class,
                event.app_name,
                event.window_title,
                event.desktop_file,
                event.pid,
                event.browser_domain,
            ),
        )
        self.conn.commit()
        return cur.lastrowid

    def get_top_apps(self, date: str, limit: int = 10) -> list[dict]:
        rows = self.conn.execute(
            """SELECT app_class, app_name, COUNT(*) as count
               FROM window_events
               WHERE timestamp LIKE ? || '%' AND app_class != ''
               GROUP BY app_class
               ORDER BY count DESC LIMIT ?""",
            (date, limit),
        ).fetchall()
        return [
            {"app_class": r["app_class"], "app_name": r["app_name"], "count": r["count"]}
            for r in rows
        ]

    def get_top_window_titles(self, date: str, limit: int = 10) -> list[dict]:
        rows = self.conn.execute(
            """SELECT window_title, app_class, COUNT(*) as count
               FROM window_events
               WHERE timestamp LIKE ? || '%' AND window_title != ''
               GROUP BY window_title
               ORDER BY count DESC LIMIT ?""",
            (date, limit),
        ).fetchall()
        return [
            {"window_title": r["window_title"], "app_class": r["app_class"], "count": r["count"]}
            for r in rows
        ]

    def get_top_browser_domains(self, date: str, limit: int = 10) -> list[dict]:
        rows = self.conn.execute(
            """SELECT browser_domain, COUNT(*) as count
               FROM window_events
               WHERE timestamp LIKE ? || '%' AND browser_domain != ''
               GROUP BY browser_domain
               ORDER BY count DESC LIMIT ?""",
            (date, limit),
        ).fetchall()
        return [
            {"browser_domain": r["browser_domain"], "count": r["count"]}
            for r in rows
        ]

    def get_activity_timeline(self, date: str) -> list[dict]:
        rows = self.conn.execute(
            """SELECT timestamp, app_class, window_title
               FROM window_events
               WHERE timestamp LIKE ? || '%'
               ORDER BY timestamp ASC""",
            (date,),
        ).fetchall()
        return [
            {
                "timestamp": r["timestamp"],
                "app_class": r["app_class"],
                "window_title": r["window_title"],
            }
            for r in rows
        ]

    def get_window_event_count(self, date: str) -> int:
        row = self.conn.execute(
            """SELECT COUNT(*) FROM window_events
               WHERE timestamp LIKE ? || '%'""",
            (date,),
        ).fetchone()
        return row[0]

    # -- Activity Day Summaries --

    def get_window_events_for_day(self, date: str) -> list[dict]:
        """Get all window events for a day with full details, sorted by timestamp."""
        rows = self.conn.execute(
            """SELECT timestamp, app_class, app_name, window_title, browser_domain
               FROM window_events
               WHERE timestamp LIKE ? || '%'
               ORDER BY timestamp ASC""",
            (date,),
        ).fetchall()
        return [
            {
                "timestamp": r["timestamp"],
                "app_class": r["app_class"],
                "app_name": r["app_name"],
                "window_title": r["window_title"],
                "browser_domain": r["browser_domain"],
            }
            for r in rows
        ]

    def get_cached_day_summary(self, date: str) -> dict | None:
        """Get cached AI summary for a day. Returns dict or None."""
        row = self.conn.execute(
            "SELECT * FROM activity_day_summaries WHERE date = ?", (date,)
        ).fetchone()
        if not row:
            return None
        return {
            "date": row["date"],
            "summary_text": row["summary_text"],
            "session_labels": row["session_labels"],
            "model": row["model"],
            "created_at": row["created_at"],
            "event_count": row["event_count"],
        }

    def save_day_summary(
        self,
        date: str,
        summary_text: str,
        session_labels: str,
        model: str,
        event_count: int,
    ) -> None:
        """Save or overwrite AI summary for a day."""
        self.conn.execute(
            """INSERT OR REPLACE INTO activity_day_summaries
               (date, summary_text, session_labels, model, created_at, event_count)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (date, summary_text, session_labels, model, datetime.now().isoformat(), event_count),
        )
        self.conn.commit()

    # -- MOTD Cache --

    def get_cached_motd(self, date: str) -> str | None:
        """Get cached MOTD for a date from app_meta."""
        row = self.conn.execute(
            "SELECT value FROM app_meta WHERE key = ?", (f"motd_{date}",)
        ).fetchone()
        return row["value"] if row else None

    def save_motd(self, date: str, motd: str) -> None:
        """Cache MOTD for a date."""
        self.conn.execute(
            "INSERT OR REPLACE INTO app_meta (key, value) VALUES (?, ?)",
            (f"motd_{date}", motd),
        )
        self.conn.commit()

    # -- Stats --

    def get_stats(self) -> dict:
        total = self.get_screenshot_count()
        live_count = self.conn.execute(
            "SELECT COUNT(*) FROM screenshots WHERE storage_type = 'live'"
        ).fetchone()[0]
        archived_count = self.conn.execute(
            "SELECT COUNT(*) FROM screenshots WHERE storage_type = 'archived'"
        ).fetchone()[0]
        ocr_count = self.conn.execute(
            "SELECT COUNT(*) FROM ocr_results"
        ).fetchone()[0]
        embedding_count = self.conn.execute(
            "SELECT COUNT(*) FROM embeddings"
        ).fetchone()[0]
        segment_count = self.conn.execute(
            "SELECT COUNT(*) FROM video_segments"
        ).fetchone()[0]
        storage_bytes = self.get_total_storage_bytes()
        return {
            "total_screenshots": total,
            "live_screenshots": live_count,
            "archived_screenshots": archived_count,
            "ocr_results": ocr_count,
            "embeddings": embedding_count,
            "video_segments": segment_count,
            "storage_bytes": storage_bytes,
            "storage_gb": round(storage_bytes / (1024**3), 2),
        }

    # -- Helpers --

    def _row_to_screenshot(self, row: sqlite3.Row) -> Screenshot:
        return Screenshot(
            id=row["id"],
            timestamp=datetime.fromisoformat(row["timestamp"]),
            date=row["date"],
            width=row["width"],
            height=row["height"],
            file_size=row["file_size"],
            similarity=row["similarity"],
            storage_type=row["storage_type"],
            segment_path=row["segment_path"],
            segment_offset_ms=row["segment_offset_ms"],
            filepath_thumb=row["filepath_thumb"],
        )

    def _row_to_monitor_capture(self, row: sqlite3.Row) -> MonitorCapture:
        return MonitorCapture(
            id=row["id"],
            screenshot_id=row["screenshot_id"],
            monitor_name=row["monitor_name"],
            monitor_index=row["monitor_index"],
            filepath=row["filepath"],
            segment_path=row["segment_path"],
            segment_offset_ms=row["segment_offset_ms"],
            x=row["x"],
            y=row["y"],
            width=row["w"],
            height=row["h"],
        )

    def _row_to_video_segment(self, row: sqlite3.Row) -> VideoSegment:
        return VideoSegment(
            id=row["id"],
            date=row["date"],
            monitor_index=row["monitor_index"],
            filepath=row["filepath"],
            start_time=datetime.fromisoformat(row["start_time"]) if row["start_time"] else None,
            end_time=datetime.fromisoformat(row["end_time"]) if row["end_time"] else None,
            frame_count=row["frame_count"],
            file_size=row["file_size"],
        )
