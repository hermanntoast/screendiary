"""WebP to H.265 video archiving worker."""

from __future__ import annotations

import asyncio
import os
import subprocess
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

import structlog

from ..config import Config
from ..db import Database

log = structlog.get_logger()


class Archiver:
    def __init__(self, config: Config, db: Database) -> None:
        self.config = config
        self.db = db
        self._running = False

    async def run(self) -> None:
        """Run the archiver loop in the background."""
        self._running = True
        log.info("archiver_started")
        while self._running:
            try:
                await self._archive_cycle()
            except Exception as e:
                log.error("archiver_error", error=str(e))
            await asyncio.sleep(60)  # Check every minute

    def stop(self) -> None:
        self._running = False

    async def _archive_cycle(self) -> None:
        """Archive old WebP screenshots into H.265 video segments."""
        cutoff = datetime.now() - timedelta(minutes=self.config.storage.archive_after_minutes)
        screenshots = self.db.get_live_screenshots_before(cutoff)

        if not screenshots:
            return

        # Group by date and 5-minute segment
        segments: dict[tuple[str, str, int], list] = {}
        seg_minutes = self.config.storage.segment_duration_minutes

        for s in screenshots:
            seg_start_minute = (s.timestamp.minute // seg_minutes) * seg_minutes
            seg_key_time = s.timestamp.replace(minute=seg_start_minute, second=0, microsecond=0)
            seg_end_time = seg_key_time + timedelta(minutes=seg_minutes)

            # Only archive complete segments (segment end time must be before cutoff)
            if seg_end_time > cutoff:
                continue

            captures = self.db.get_monitor_captures(s.id)
            for mc in captures:
                if not mc.filepath or not Path(mc.filepath).is_file():
                    continue
                key = (s.date, seg_key_time.strftime("%H%M"), mc.monitor_index)
                if key not in segments:
                    segments[key] = []
                segments[key].append((s, mc, seg_key_time, seg_end_time))

        for (date, time_key, monitor_idx), items in segments.items():
            await self._create_video_segment(date, time_key, monitor_idx, items)

        # Pruning
        await self._prune_old_segments()

    async def _create_video_segment(
        self,
        date: str,
        time_key: str,
        monitor_idx: int,
        items: list[tuple],
    ) -> None:
        """Create a single H.265 video segment from WebP frames."""
        if not items:
            return

        _, _, seg_start, seg_end = items[0]
        # Sort by timestamp
        items.sort(key=lambda x: x[0].timestamp)

        archive_dir = self.config.storage.archive_path / date.replace("-", "/")
        archive_dir.mkdir(parents=True, exist_ok=True)

        end_time_key = time_key[:2] + str(int(time_key[2:]) + self.config.storage.segment_duration_minutes).zfill(2)
        segment_filename = f"monitor{monitor_idx}_{time_key}-{end_time_key}.mp4"
        segment_path = archive_dir / segment_filename

        if segment_path.is_file():
            log.debug("segment_exists", path=str(segment_path))
            return

        # Create temp dir with symlinked/copied frames in order
        with tempfile.TemporaryDirectory() as tmpdir:
            frame_paths = []
            for i, (s, mc, _, _) in enumerate(items):
                src = Path(mc.filepath)
                dst = Path(tmpdir) / f"frame_{i:04d}.webp"
                # Symlink for speed
                dst.symlink_to(src.resolve())
                frame_paths.append(dst)

            if not frame_paths:
                return

            # Calculate framerate based on capture interval
            fps = 1.0 / self.config.capture.interval

            cmd = [
                "ffmpeg", "-y",
                "-framerate", str(fps),
                "-i", str(Path(tmpdir) / "frame_%04d.webp"),
                "-c:v", "libx265",
                "-crf", str(self.config.storage.h265_crf),
                "-preset", self.config.storage.h265_preset,
                "-tag:v", "hvc1",
                "-pix_fmt", "yuv420p",
                str(segment_path),
            ]

            log.info("creating_segment", path=str(segment_path), frames=len(frame_paths))

            result = await asyncio.to_thread(
                subprocess.run, cmd, capture_output=True, timeout=300
            )

            if result.returncode != 0:
                log.error(
                    "ffmpeg_encode_failed",
                    stderr=result.stderr.decode()[:500],
                    path=str(segment_path),
                )
                segment_path.unlink(missing_ok=True)
                return

        # Update DB entries and delete WebP files
        from ..models import VideoSegment

        seg = VideoSegment(
            date=date,
            monitor_index=monitor_idx,
            filepath=str(segment_path),
            start_time=seg_start,
            end_time=seg_end,
            frame_count=len(items),
            file_size=segment_path.stat().st_size,
        )
        self.db.insert_video_segment(seg)

        for i, (s, mc, _, _) in enumerate(items):
            # Offset = frame index * interval * 1000ms
            offset_ms = int(i * self.config.capture.interval * 1000)
            self.db.update_monitor_capture_archived(mc.id, str(segment_path), offset_ms)
            self.db.update_screenshot_archived(s.id, str(segment_path), offset_ms)

            # Delete original WebP (keep thumbnail)
            if mc.filepath:
                Path(mc.filepath).unlink(missing_ok=True)

        log.info("segment_created", path=str(segment_path), frames=len(items))

    async def _prune_old_segments(self) -> None:
        """Delete oldest video segments if storage exceeds max_storage_gb."""
        max_bytes = self.config.storage.max_storage_gb * (1024**3)
        total = self.db.get_total_storage_bytes()

        if total <= max_bytes:
            return

        log.info("pruning_segments", total_gb=round(total / (1024**3), 2))

        while total > max_bytes:
            oldest = self.db.get_oldest_video_segments(limit=1)
            if not oldest:
                break
            seg = oldest[0]
            Path(seg.filepath).unlink(missing_ok=True)
            self.db.delete_video_segment(seg.id)
            total -= seg.file_size
            log.info("pruned_segment", path=seg.filepath, freed_mb=round(seg.file_size / (1024**2), 1))
