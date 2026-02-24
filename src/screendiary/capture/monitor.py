"""Monitor detection via xrandr."""

from __future__ import annotations

import asyncio
import re

import structlog

from ..models import Monitor

log = structlog.get_logger()

_XRANDR_PATTERN = re.compile(
    r"^(\S+)\s+connected\s+(?:primary\s+)?(\d+)x(\d+)\+(\d+)\+(\d+)"
)


async def detect_monitors() -> list[Monitor]:
    """Detect connected monitors using xrandr."""
    proc = await asyncio.create_subprocess_exec(
        "xrandr", "--query",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate()

    if proc.returncode != 0:
        log.error("xrandr_failed", stderr=stderr.decode())
        raise RuntimeError(f"xrandr failed: {stderr.decode()}")

    monitors = []
    for line in stdout.decode().splitlines():
        m = _XRANDR_PATTERN.match(line)
        if m:
            monitors.append(Monitor(
                name=m.group(1),
                index=len(monitors),
                width=int(m.group(2)),
                height=int(m.group(3)),
                x=int(m.group(4)),
                y=int(m.group(5)),
            ))

    monitors.sort(key=lambda m: m.x)
    for i, mon in enumerate(monitors):
        mon.index = i

    log.info("monitors_detected", count=len(monitors), monitors=[
        f"{m.name}:{m.width}x{m.height}+{m.x}+{m.y}" for m in monitors
    ])
    return monitors
