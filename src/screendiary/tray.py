"""System tray icon for ScreenDiary with pause/resume controls."""

from __future__ import annotations

import subprocess
import threading
import webbrowser
from pathlib import Path

import pystray
from PIL import Image, ImageDraw, ImageFont

from .config import Config

SERVICE_NAME = "screendiary-capture.service"
_ICON_SIZE = 64


def _create_sd_icon(bg_color: tuple = (20, 20, 24, 255),
                    text_color: tuple = (255, 255, 255)) -> Image.Image:
    """Dark rounded square with 'SD' monogram."""
    size = _ICON_SIZE
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.rounded_rectangle([0, 0, size - 1, size - 1], radius=size // 6, fill=bg_color)
    font_size = int(size * 0.47)
    try:
        font = ImageFont.truetype("/usr/share/fonts/TTF/DejaVuSans-Bold.ttf", font_size)
    except OSError:
        font = ImageFont.load_default()
    bbox = draw.textbbox((0, 0), "SD", font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    tx = (size - tw) // 2 - bbox[0]
    ty = (size - th) // 2 - bbox[1]
    draw.text((tx, ty), "SD", fill=text_color, font=font)
    return img


def _create_icon_active() -> Image.Image:
    """SD on dark square — capture active."""
    return _create_sd_icon()


def _create_icon_paused() -> Image.Image:
    """SD on orange square — capture paused."""
    return _create_sd_icon(bg_color=(230, 150, 30, 255), text_color=(255, 255, 255))


def _send_signal(sig: str) -> None:
    """Send a signal to the capture service via systemctl."""
    subprocess.run(
        ["systemctl", "--user", "kill", "-s", sig, SERVICE_NAME],
        capture_output=True,
    )


class TrayApp:
    def __init__(self, config: Config) -> None:
        self.config = config
        self._paused = False
        self._timer: threading.Timer | None = None
        self._icon: pystray.Icon | None = None

    def run(self) -> None:
        self._icon = pystray.Icon(
            "screendiary",
            icon=_create_icon_active(),
            title="ScreenDiary",
            menu=self._build_menu(),
        )
        self._icon.run()

    def _build_menu(self) -> pystray.Menu:
        if self._paused:
            return pystray.Menu(
                pystray.MenuItem("Aufnahme fortsetzen", self._on_resume),
                pystray.Menu.SEPARATOR,
                pystray.MenuItem("WebUI öffnen", self._on_open_web),
                pystray.MenuItem("Beenden", self._on_quit),
            )
        return pystray.Menu(
            pystray.MenuItem(
                "Aufnahme pausieren",
                pystray.Menu(
                    pystray.MenuItem("5 Minuten", lambda icon, item: self._on_pause(5)),
                    pystray.MenuItem("10 Minuten", lambda icon, item: self._on_pause(10)),
                    pystray.MenuItem("30 Minuten", lambda icon, item: self._on_pause(30)),
                    pystray.MenuItem("60 Minuten", lambda icon, item: self._on_pause(60)),
                    pystray.Menu.SEPARATOR,
                    pystray.MenuItem("Bis zum Aktivieren", lambda icon, item: self._on_pause(0)),
                ),
            ),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("WebUI öffnen", self._on_open_web),
            pystray.MenuItem("Beenden", self._on_quit),
        )

    def _refresh(self) -> None:
        if self._icon is None:
            return
        self._icon.icon = _create_icon_paused() if self._paused else _create_icon_active()
        self._icon.title = "ScreenDiary (pausiert)" if self._paused else "ScreenDiary"
        self._icon.menu = self._build_menu()
        self._icon.update_menu()

    def _cancel_timer(self) -> None:
        if self._timer is not None:
            self._timer.cancel()
            self._timer = None

    def _on_pause(self, minutes: int) -> None:
        self._cancel_timer()
        self._paused = True
        _send_signal("SIGUSR1")
        if minutes > 0:
            self._timer = threading.Timer(minutes * 60, self._on_resume)
            self._timer.daemon = True
            self._timer.start()
        self._refresh()

    def _on_resume(self, icon=None, item=None) -> None:
        self._cancel_timer()
        self._paused = False
        _send_signal("SIGUSR2")
        self._refresh()

    def _on_open_web(self, icon=None, item=None) -> None:
        url = f"http://{self.config.web.host}:{self.config.web.port}"
        webbrowser.open(url)

    def _on_quit(self, icon=None, item=None) -> None:
        if self._paused:
            self._on_resume()
        if self._icon is not None:
            self._icon.stop()
