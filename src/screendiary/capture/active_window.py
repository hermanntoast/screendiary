"""Active window detection via KWin scripting on KDE Wayland.

Uses gdbus to load a temporary KWin script that reads workspace.activeWindow
properties, then parses the output from journalctl.
"""

from __future__ import annotations

import asyncio
import json
import tempfile
import uuid
from dataclasses import dataclass
from pathlib import Path

import structlog

log = structlog.get_logger()

# KWin script that prints active window info with a unique prefix
_KWIN_SCRIPT_TEMPLATE = """\
(function() {{
    var w = workspace.activeWindow;
    if (w) {{
        print("{prefix}" + JSON.stringify({{
            caption: w.caption || "",
            resourceClass: w.resourceClass || "",
            resourceName: w.resourceName || "",
            desktopFileName: w.desktopFileName || "",
            pid: w.pid || 0
        }}));
    }} else {{
        print("{prefix}null");
    }}
}})();
"""

_DBUS_SERVICE = "org.kde.KWin"
_DBUS_PATH = "/Scripting"
_DBUS_IFACE = "org.kde.kwin.Scripting"

_TIMEOUT_S = 2.0


@dataclass
class WindowInfo:
    caption: str = ""
    resource_class: str = ""
    resource_name: str = ""
    desktop_file: str = ""
    pid: int = 0


async def _run(cmd: list[str], timeout: float = _TIMEOUT_S) -> tuple[int, str, str]:
    """Run a command and return (returncode, stdout, stderr)."""
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
    except asyncio.TimeoutError:
        proc.kill()
        await proc.communicate()
        return -1, "", "timeout"
    return proc.returncode, stdout.decode(), stderr.decode()


async def get_active_window() -> WindowInfo | None:
    """Detect the currently active window via KWin scripting + journalctl.

    Returns WindowInfo or None if detection fails.
    """
    prefix = f"SCREENDIARY_WINDOW:{uuid.uuid4().hex[:12]}:"
    script_content = _KWIN_SCRIPT_TEMPLATE.format(prefix=prefix)

    # Write temporary script file
    tmp = tempfile.NamedTemporaryFile(
        suffix=".js", prefix="sd_kwin_", delete=False, mode="w"
    )
    try:
        tmp.write(script_content)
        tmp.close()
        script_path = tmp.name

        # Load script via gdbus
        rc, out, err = await _run([
            "gdbus", "call", "--session",
            "--dest", _DBUS_SERVICE,
            "--object-path", _DBUS_PATH,
            "--method", f"{_DBUS_IFACE}.loadScript",
            script_path,
        ])
        if rc != 0:
            log.debug("kwin_load_failed", rc=rc, err=err.strip())
            return None

        # Parse script ID from output like "(int32 N,)"
        script_id = out.strip().strip("()").split(",")[0].replace("int32 ", "").strip()

        # Start (run) the script
        rc, _, err = await _run([
            "gdbus", "call", "--session",
            "--dest", _DBUS_SERVICE,
            "--object-path", f"/Scripting/Script{script_id}",
            "--method", "org.kde.kwin.Script.run",
        ])
        if rc != 0:
            log.debug("kwin_run_failed", rc=rc, err=err.strip())
            await _unload_script(script_id)
            return None

        # Small delay for KWin to process and write to journal
        await asyncio.sleep(0.05)

        # Read output from journalctl
        rc, journal_out, _ = await _run([
            "journalctl", "--user",
            "-u", "plasma-kwin_wayland.service",
            "--since", "-3s",
            "--no-pager", "-o", "cat",
            "--grep", prefix,
        ], timeout=_TIMEOUT_S)

        # Unload script
        await _unload_script(script_id)

        if rc != 0 or not journal_out.strip():
            # Fallback: try plasma-kwin_x11 service or generic kwin
            rc, journal_out, _ = await _run([
                "journalctl", "--user",
                "--since", "-3s",
                "--no-pager", "-o", "cat",
                "--grep", prefix,
            ], timeout=_TIMEOUT_S)
            if rc != 0 or not journal_out.strip():
                log.debug("kwin_journal_empty")
                return None

        # Parse output — find the line with our prefix
        for line in journal_out.strip().splitlines():
            idx = line.find(prefix)
            if idx == -1:
                continue
            payload = line[idx + len(prefix):]
            if payload.strip() == "null":
                return None
            try:
                data = json.loads(payload)
                return WindowInfo(
                    caption=data.get("caption", ""),
                    resource_class=data.get("resourceClass", ""),
                    resource_name=data.get("resourceName", ""),
                    desktop_file=data.get("desktopFileName", ""),
                    pid=data.get("pid", 0),
                )
            except json.JSONDecodeError:
                log.debug("kwin_json_parse_error", payload=payload[:200])
                return None

        return None
    except Exception as e:
        log.debug("active_window_error", error=str(e))
        return None
    finally:
        Path(tmp.name).unlink(missing_ok=True)


async def _unload_script(script_id: str) -> None:
    """Unload a KWin script by ID."""
    await _run([
        "gdbus", "call", "--session",
        "--dest", _DBUS_SERVICE,
        "--object-path", f"/Scripting/Script{script_id}",
        "--method", "org.kde.kwin.Script.stop",
    ])
    await _run([
        "gdbus", "call", "--session",
        "--dest", _DBUS_SERVICE,
        "--object-path", _DBUS_PATH,
        "--method", f"{_DBUS_IFACE}.unloadScript",
        script_id,
    ])
