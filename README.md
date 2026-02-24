<p align="center">
  <img src="logo.png" alt="ScreenDiary" width="300" />
</p>

# ScreenDiary

Automatic desktop activity tracker for Linux (KDE Plasma / Wayland). Takes periodic screenshots with OCR text recognition, active window tracking, and a searchable web interface.

## Features

- **Periodic Screenshots** — Configurable interval (default: 2s) with duplicate detection
- **OCR Text Recognition** — Tesseract-based, German + English
- **Active Window Tracking** — App name, window title, browser domain
- **Video Archiving** — Older screenshots are compressed into H.265 segments
- **Web UI** — Timeline player, full-text search, activity dashboard
- **System Tray** — Pause/resume with timer options
- **Multi-Monitor** — Supports multiple displays

## System Dependencies

```bash
# Arch Linux / CachyOS
sudo pacman -S tesseract tesseract-data-deu tesseract-data-eng spectacle ffmpeg

# For system tray
sudo pacman -S libayatana-appindicator python-gobject
```

## Installation

```bash
# Clone the repository
git clone https://github.com/user/screendiary.git
cd screendiary

# Install Python dependencies
uv sync
source .venv/bin/activate

# Copy and edit configuration
cp config.example.toml config.toml

# Build the frontend
screendiary build

# Install systemd services
screendiary install

# Start
screendiary start
```

## Configuration

Configuration is read from `config.toml` (or `~/.config/screendiary/config.toml`):

```toml
[capture]
interval = 2                    # Screenshot interval in seconds
similarity_threshold = 0.98     # Duplicate threshold (0.0 - 1.0)
tool = "spectacle"              # Screenshot tool

[storage]
data_dir = "data"               # Data directory
quality = 80                    # WebP quality
max_storage_gb = 200            # Max storage usage
archive_after_minutes = 10      # Archive after X minutes
h265_crf = 28                   # Video quality (lower = better)

[ocr]
languages = "deu+eng"           # Tesseract languages
workers = 2                     # Parallel OCR workers

[web]
host = "127.0.0.1"
port = 18787                    # Web UI port

[logging]
level = "INFO"
```

## CLI Commands

```bash
screendiary capture    # Start the capture daemon
screendiary web        # Start the web UI server
screendiary tray       # Start the system tray icon
screendiary build      # Build the frontend (npm install + build)
screendiary status     # Show status and statistics
screendiary install    # Install systemd user services
screendiary start      # Start all services (via systemd)
screendiary stop       # Stop all services
screendiary logs       # Show logs (follow)
```

## Web UI

Available at `http://127.0.0.1:18787` after starting:

- **Player** — Timeline with screenshot playback and full-text search
- **Activity** — Daily overview with top apps, window titles, and browser domains

## System Tray

The tray icon provides:

- **Pause capture** — 5, 10, 30, 60 minutes or until manually resumed
- **Resume capture** — Immediately continue capturing
- **Open WebUI** — Opens the web interface in a browser
- **Quit** — Exit tray (resumes capture before stopping)

## Architecture

```
src/screendiary/
├── __main__.py            # CLI (Click)
├── daemon.py              # Capture loop (asyncio)
├── tray.py                # System tray (pystray)
├── config.py              # TOML configuration
├── db.py                  # SQLite + FTS5
├── models.py              # Data classes
├── capture/
│   ├── screenshot.py      # Spectacle + Pillow
│   ├── active_window.py   # KWin DBus
│   ├── browser_domain.py  # Firefox/Chrome history
│   ├── dedup.py           # Image comparison
│   └── monitor.py         # Monitor detection
├── processing/
│   └── pipeline.py        # OCR queue
├── storage/
│   └── archiver.py        # H.265 archiving
└── web/
    ├── app.py             # FastAPI
    └── routes/            # API endpoints

frontend/                  # React 19 + TypeScript + Vite
systemd/                   # Systemd user services
```
