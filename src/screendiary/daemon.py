"""Async capture daemon with processing queue and archiver."""

from __future__ import annotations

import asyncio
import signal
from datetime import datetime
from pathlib import Path

import structlog

from .capture.active_window import get_active_window
from .capture.browser_domain import extract_domain, is_browser
from .capture.dedup import is_duplicate
from .capture.monitor import detect_monitors
from .capture.screenshot import (
    crop_monitors,
    save_thumbnail,
    save_webp,
    take_screenshot,
)
from .config import Config
from .db import Database
from .models import MonitorCapture, Screenshot, WindowEvent
from .processing.pipeline import ProcessingPipeline
from .storage.archiver import Archiver

log = structlog.get_logger()


class Daemon:
    _MONITOR_CHECK_INTERVAL = 30  # re-detect monitors every N capture cycles

    def __init__(self, config: Config) -> None:
        self.config = config
        self.db = Database(config)
        self.pipeline = ProcessingPipeline(config, self.db)
        self.archiver = Archiver(config, self.db)
        self._running = False
        self._paused = False
        self._monitors: list = []
        self._prev_images: dict[int, "Image"] = {}  # monitor_index -> last PIL Image
        self._capture_count = 0
        self._skip_count = 0
        self._cycles_since_monitor_check = 0

    async def run(self) -> None:
        """Main daemon entry point."""
        self.db.init()
        self.config.storage.screenshots_path.mkdir(parents=True, exist_ok=True)
        self.config.storage.archive_path.mkdir(parents=True, exist_ok=True)

        self._monitors = await detect_monitors()
        if not self._monitors:
            log.error("no_monitors_detected")
            return

        self._running = True

        # Setup signal handlers
        loop = asyncio.get_event_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, self._handle_signal)
        loop.add_signal_handler(signal.SIGUSR1, self._handle_pause)
        loop.add_signal_handler(signal.SIGUSR2, self._handle_resume)

        # Start background tasks
        await self.pipeline.start()
        archiver_task = asyncio.create_task(self.archiver.run())

        log.info(
            "daemon_started",
            interval=self.config.capture.interval,
            monitors=len(self._monitors),
        )

        try:
            while self._running:
                if self._paused:
                    await asyncio.sleep(1)
                    continue
                start = asyncio.get_event_loop().time()
                await self._refresh_monitors()
                await self._capture_cycle(self._monitors)
                elapsed = asyncio.get_event_loop().time() - start
                sleep_time = max(0, self.config.capture.interval - elapsed)
                await asyncio.sleep(sleep_time)
        finally:
            log.info(
                "daemon_stopping",
                captured=self._capture_count,
                skipped=self._skip_count,
            )
            self.archiver.stop()
            await self.pipeline.stop()
            archiver_task.cancel()
            try:
                await archiver_task
            except asyncio.CancelledError:
                pass
            self.db.close()

    def _handle_signal(self) -> None:
        log.info("shutdown_signal_received")
        self._running = False

    def _handle_pause(self) -> None:
        self._paused = True
        log.info("capture_paused")

    def _handle_resume(self) -> None:
        self._paused = False
        log.info("capture_resumed")

    async def _refresh_monitors(self) -> None:
        """Re-detect monitors periodically and update if changed."""
        self._cycles_since_monitor_check += 1
        if self._cycles_since_monitor_check < self._MONITOR_CHECK_INTERVAL:
            return
        self._cycles_since_monitor_check = 0

        try:
            new_monitors = await detect_monitors()
        except Exception as e:
            log.warning("monitor_refresh_failed", error=str(e))
            return

        if not new_monitors:
            log.warning("monitor_refresh_empty")
            return

        if self._monitors_changed(new_monitors):
            log.info(
                "monitors_changed",
                old=[f"{m.name}:{m.width}x{m.height}" for m in self._monitors],
                new=[f"{m.name}:{m.width}x{m.height}" for m in new_monitors],
            )
            self._monitors = new_monitors
            self._prev_images.clear()

    def _monitors_changed(self, new_monitors: list) -> bool:
        """Compare current monitors with newly detected ones."""
        if len(self._monitors) != len(new_monitors):
            return True
        for old, new in zip(self._monitors, new_monitors):
            if (old.name != new.name or old.width != new.width
                    or old.height != new.height or old.x != new.x
                    or old.y != new.y):
                return True
        return False

    async def _capture_cycle(self, monitors: list) -> None:
        """Single capture cycle: screenshot -> dedup -> save -> enqueue OCR."""
        full_image, window_info = await asyncio.gather(
            take_screenshot(self.config),
            get_active_window(),
        )
        if full_image is None:
            return

        monitor_images = crop_monitors(full_image, monitors)

        # Check dedup across all monitors combined
        any_changed = False
        for i, img in enumerate(monitor_images):
            if i in self._prev_images:
                dup, sim = is_duplicate(
                    img, self._prev_images[i], self.config.capture.similarity_threshold
                )
                if not dup:
                    any_changed = True
                    break
            else:
                any_changed = True
                break

        if not any_changed:
            self._skip_count += 1
            return

        # Save screenshot
        now = datetime.now()
        date_str = now.strftime("%Y-%m-%d")
        date_path = now.strftime("%Y/%m/%d")
        time_str = now.strftime("%H%M%S_%f")[:11]

        # Thumbnail from first monitor (or combine?)
        thumb_dir = self.config.storage.screenshots_path / date_path
        thumb_path = thumb_dir / f"thumb_{time_str}.webp"
        save_thumbnail(monitor_images[0], thumb_path, self.config.storage.thumbnail_width)

        total_size = 0
        screenshot = Screenshot(
            timestamp=now,
            date=date_str,
            width=full_image.width,
            height=full_image.height,
            similarity=0.0,
            storage_type="live",
            filepath_thumb=str(thumb_path),
        )
        screenshot_id = self.db.insert_screenshot(screenshot)

        # Save window event if we captured active window info
        if window_info:
            browser_domain = ""
            if is_browser(window_info.resource_class):
                browser_domain = extract_domain(window_info.resource_class)
            event = WindowEvent(
                screenshot_id=screenshot_id,
                timestamp=now,
                app_class=window_info.resource_class,
                app_name=window_info.resource_name,
                window_title=window_info.caption,
                desktop_file=window_info.desktop_file,
                pid=window_info.pid,
                browser_domain=browser_domain,
            )
            self.db.insert_window_event(event)

        # Save per-monitor images and create DB entries
        ocr_items: list[tuple[int, any]] = []
        for i, img in enumerate(monitor_images):
            mon = monitors[i]
            img_dir = self.config.storage.screenshots_path / date_path
            img_path = img_dir / f"monitor{i}_{time_str}.webp"
            size = save_webp(img, img_path, self.config.storage.quality)
            total_size += size

            mc = MonitorCapture(
                screenshot_id=screenshot_id,
                monitor_name=mon.name,
                monitor_index=i,
                filepath=str(img_path),
                x=mon.x,
                y=mon.y,
                width=mon.width,
                height=mon.height,
            )
            mc_id = self.db.insert_monitor_capture(mc)
            ocr_items.append((mc_id, img))
            self._prev_images[i] = img

        # Update file_size
        self.db.conn.execute(
            "UPDATE screenshots SET file_size = ? WHERE id = ?",
            (total_size, screenshot_id),
        )
        self.db.conn.commit()

        # Enqueue for OCR processing
        await self.pipeline.enqueue(screenshot_id, ocr_items)
        self._capture_count += 1

        log.debug(
            "captured",
            id=screenshot_id,
            monitors=len(monitor_images),
            size_kb=round(total_size / 1024, 1),
        )
