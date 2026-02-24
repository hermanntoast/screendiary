"""Browser domain extraction from Firefox/Chrome history databases."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from urllib.parse import urlparse

import structlog

log = structlog.get_logger()

_BROWSERS: dict[str, dict] = {
    "firefox": {
        "glob": str(Path.home() / ".mozilla/firefox/*/places.sqlite"),
        "query": "SELECT url FROM moz_places ORDER BY last_visit_date DESC LIMIT 1",
    },
    "firefox-esr": {
        "glob": str(Path.home() / ".mozilla/firefox/*/places.sqlite"),
        "query": "SELECT url FROM moz_places ORDER BY last_visit_date DESC LIMIT 1",
    },
    "librewolf": {
        "glob": str(Path.home() / ".librewolf/*/places.sqlite"),
        "query": "SELECT url FROM moz_places ORDER BY last_visit_date DESC LIMIT 1",
    },
    "google-chrome": {
        "glob": str(Path.home() / ".config/google-chrome/Default/History"),
        "query": "SELECT url FROM urls ORDER BY last_visit_time DESC LIMIT 1",
    },
    "chromium-browser": {
        "glob": str(Path.home() / ".config/chromium/Default/History"),
        "query": "SELECT url FROM urls ORDER BY last_visit_time DESC LIMIT 1",
    },
    "brave-browser": {
        "glob": str(Path.home() / ".config/BraveSoftware/Brave-Browser/Default/History"),
        "query": "SELECT url FROM urls ORDER BY last_visit_time DESC LIMIT 1",
    },
}

# Normalized browser class names
_BROWSER_ALIASES: dict[str, str] = {
    "navigator": "firefox",
    "firefox": "firefox",
    "firefox-esr": "firefox-esr",
    "librewolf": "librewolf",
    "google-chrome": "google-chrome",
    "chromium": "chromium-browser",
    "chromium-browser": "chromium-browser",
    "brave": "brave-browser",
    "brave-browser": "brave-browser",
}


def is_browser(app_class: str) -> bool:
    """Check if an app_class corresponds to a known browser."""
    return app_class.lower() in _BROWSER_ALIASES


def _find_db_path(glob_pattern: str) -> Path | None:
    """Find the most recently modified DB matching the glob pattern."""
    from glob import glob
    matches = glob(glob_pattern)
    if not matches:
        return None
    # Sort by modification time, most recent first
    matches.sort(key=lambda p: Path(p).stat().st_mtime, reverse=True)
    return Path(matches[0])


def extract_domain(app_class: str) -> str:
    """Extract the domain from the most recently visited URL for the given browser.

    Opens the browser history database in immutable/read-only mode to avoid
    interfering with the running browser.

    Returns the domain string or empty string on failure.
    """
    normalized = _BROWSER_ALIASES.get(app_class.lower(), "")
    if not normalized or normalized not in _BROWSERS:
        return ""

    browser_info = _BROWSERS[normalized]
    db_path = _find_db_path(browser_info["glob"])
    if not db_path or not db_path.exists():
        return ""

    try:
        # Open with immutable=1 to avoid locking issues with the running browser
        uri = f"file:{db_path}?immutable=1"
        conn = sqlite3.connect(uri, uri=True, timeout=1)
        try:
            row = conn.execute(browser_info["query"]).fetchone()
            if row and row[0]:
                parsed = urlparse(row[0])
                domain = parsed.netloc
                # Strip www. prefix for cleaner display
                if domain.startswith("www."):
                    domain = domain[4:]
                return domain
        finally:
            conn.close()
    except Exception as e:
        log.debug("browser_domain_error", browser=normalized, error=str(e))

    return ""
