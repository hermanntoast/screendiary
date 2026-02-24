"""CLI entry point for ScreenDiary."""

from __future__ import annotations

import asyncio
import shutil
import subprocess
import sys
from pathlib import Path

import click
import structlog

from .config import load_config

structlog.configure(
    processors=[
        structlog.dev.ConsoleRenderer(),
    ],
    wrapper_class=structlog.make_filtering_bound_logger(0),
)


@click.group()
@click.option("--config", "-c", "config_path", default=None, help="Config file path")
@click.pass_context
def cli(ctx: click.Context, config_path: str | None) -> None:
    """ScreenDiary - Desktop activity tracker."""
    ctx.ensure_object(dict)
    ctx.obj["config_path"] = config_path


@cli.command()
@click.pass_context
def capture(ctx: click.Context) -> None:
    """Start the capture daemon."""
    config = load_config(ctx.obj["config_path"])
    _configure_logging(config.logging.level)

    # Check dependencies
    _check_deps()

    from .daemon import Daemon

    daemon = Daemon(config)
    asyncio.run(daemon.run())


@cli.command()
@click.pass_context
def web(ctx: click.Context) -> None:
    """Start the web UI server."""
    config = load_config(ctx.obj["config_path"])
    _configure_logging(config.logging.level)

    import uvicorn

    from .web.app import create_app

    app = create_app(config)
    uvicorn.run(app, host=config.web.host, port=config.web.port)


@cli.command()
@click.pass_context
def tray(ctx: click.Context) -> None:
    """Start the system tray icon."""
    config = load_config(ctx.obj["config_path"])

    from .tray import TrayApp

    app = TrayApp(config)
    app.run()


@cli.command()
@click.pass_context
def status(ctx: click.Context) -> None:
    """Show daemon status and statistics."""
    config = load_config(ctx.obj["config_path"])
    from .db import Database

    db = Database(config)
    db.init()
    stats = db.get_stats()
    db.close()

    click.echo("ScreenDiary Status")
    click.echo("=" * 40)
    click.echo(f"Screenshots:  {stats['total_screenshots']}")
    click.echo(f"  Live:       {stats['live_screenshots']}")
    click.echo(f"  Archived:   {stats['archived_screenshots']}")
    click.echo(f"OCR Results:  {stats['ocr_results']}")
    click.echo(f"Embeddings:   {stats['embeddings']}")
    click.echo(f"Segments:     {stats['video_segments']}")
    click.echo(f"Storage:      {stats['storage_gb']} GB")

    # Systemd status
    for svc in ["screendiary-capture", "screendiary-web", "screendiary-tray"]:
        result = subprocess.run(
            ["systemctl", "--user", "is-active", svc],
            capture_output=True,
            text=True,
        )
        state = result.stdout.strip() or "unknown"
        click.echo(f"{svc}: {state}")


@cli.command()
def build() -> None:
    """Build the frontend (npm install + npm run build)."""
    frontend_dir = Path(__file__).parent.parent.parent / "frontend"
    if not frontend_dir.is_dir():
        frontend_dir = Path.cwd() / "frontend"
    if not frontend_dir.is_dir():
        click.echo("Error: frontend/ directory not found", err=True)
        sys.exit(1)

    click.echo("Installing frontend dependencies...")
    subprocess.run(["npm", "install"], cwd=frontend_dir, check=True)
    click.echo("Building frontend...")
    subprocess.run(["npm", "run", "build"], cwd=frontend_dir, check=True)
    click.echo("Frontend built successfully.")


@cli.command()
def install() -> None:
    """Install systemd user services."""
    systemd_dir = Path.home() / ".config" / "systemd" / "user"
    systemd_dir.mkdir(parents=True, exist_ok=True)

    source_dir = Path(__file__).parent.parent.parent / "systemd"
    if not source_dir.is_dir():
        # Try relative to project
        source_dir = Path.cwd() / "systemd"

    if not source_dir.is_dir():
        click.echo("Error: systemd/ directory not found", err=True)
        sys.exit(1)

    for f in source_dir.glob("*"):
        dest = systemd_dir / f.name
        shutil.copy2(f, dest)
        click.echo(f"Installed: {dest}")

    subprocess.run(["systemctl", "--user", "daemon-reload"], check=True)
    click.echo("Services installed. Use 'screendiary start' to start.")


@cli.command()
def start() -> None:
    """Start all services via systemd."""
    subprocess.run(
        ["systemctl", "--user", "start", "screendiary.target"],
        check=True,
    )
    click.echo("ScreenDiary started.")


@cli.command()
def stop() -> None:
    """Stop all services via systemd."""
    subprocess.run(
        ["systemctl", "--user", "stop", "screendiary.target"],
        check=True,
    )
    click.echo("ScreenDiary stopped.")


@cli.command()
def logs() -> None:
    """Show service logs."""
    subprocess.run([
        "journalctl", "--user", "-u", "screendiary-capture",
        "-u", "screendiary-web", "-u", "screendiary-tray",
        "-f", "--no-pager",
    ])


def _check_deps() -> None:
    """Check that required system dependencies are available."""
    missing = []
    for cmd in ["spectacle", "tesseract", "ffmpeg"]:
        if not shutil.which(cmd):
            missing.append(cmd)
    if missing:
        click.echo(f"Missing system dependencies: {', '.join(missing)}", err=True)
        click.echo("Install with: sudo pacman -S " + " ".join(missing), err=True)
        sys.exit(1)


def _configure_logging(level: str) -> None:
    structlog.configure(
        processors=[
            structlog.stdlib.add_log_level,
            structlog.dev.ConsoleRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            {"DEBUG": 10, "INFO": 20, "WARNING": 30, "ERROR": 40}.get(level.upper(), 20)
        ),
    )


if __name__ == "__main__":
    cli()
