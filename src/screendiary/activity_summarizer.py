"""Activity summarizer: session merging, break detection, categorization, AI summary."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import datetime

import structlog
from openai import AsyncOpenAI

from .config import Config

log = structlog.get_logger()

# --- Category mapping ---

CATEGORY_MAP: dict[str, str] = {}

_CATEGORY_KEYWORDS: dict[str, list[str]] = {
    "coding": [
        "code", "codium", "vscodium", "neovim", "nvim", "vim", "kate", "zed",
        "jetbrains", "pycharm", "webstorm", "intellij", "clion", "goland",
        "rider", "phpstorm", "rustrover", "sublime", "atom", "gedit",
    ],
    "terminal": [
        "konsole", "alacritty", "kitty", "wezterm", "foot", "gnome-terminal",
        "xterm", "terminator", "tilix", "yakuake",
    ],
    "browser": [
        "firefox", "librewolf", "chromium", "google-chrome", "brave",
        "vivaldi", "opera", "epiphany", "midori", "zen",
    ],
    "communication": [
        "thunderbird", "discord", "telegram", "signal", "slack", "element",
        "teams", "zoom", "skype", "matrix", "nheko",
    ],
    "media": [
        "mpv", "vlc", "spotify", "gwenview", "elisa", "audacious",
        "celluloid", "totem", "rhythmbox", "eog", "loupe",
    ],
    "files": [
        "dolphin", "nautilus", "thunar", "nemo", "pcmanfm", "ranger",
    ],
    "office": [
        "libreoffice", "okular", "evince", "zathura", "calibre", "xournalpp",
    ],
}

for _cat, _keywords in _CATEGORY_KEYWORDS.items():
    for _kw in _keywords:
        CATEGORY_MAP[_kw] = _cat


def categorize_app(app_class: str) -> str:
    """Categorize an app_class string into a category."""
    lower = app_class.lower()
    # Direct match
    if lower in CATEGORY_MAP:
        return CATEGORY_MAP[lower]
    # Substring match
    for keyword, category in CATEGORY_MAP.items():
        if keyword in lower:
            return category
    return "other"


# --- Data classes ---

@dataclass
class ActivitySession:
    app_class: str
    category: str
    start: datetime
    end: datetime
    window_titles: list[str] = field(default_factory=list)
    browser_domains: list[str] = field(default_factory=list)
    event_count: int = 0

    @property
    def duration_seconds(self) -> int:
        return int((self.end - self.start).total_seconds())

    def to_dict(self) -> dict:
        return {
            "app_class": self.app_class,
            "category": self.category,
            "start": self.start.isoformat(),
            "end": self.end.isoformat(),
            "duration_seconds": self.duration_seconds,
            "window_titles": self.window_titles,
            "browser_domains": self.browser_domains,
            "event_count": self.event_count,
        }


@dataclass
class Break:
    start: datetime
    end: datetime

    @property
    def duration_seconds(self) -> int:
        return int((self.end - self.start).total_seconds())

    def to_dict(self) -> dict:
        return {
            "start": self.start.isoformat(),
            "end": self.end.isoformat(),
            "duration_seconds": self.duration_seconds,
        }


@dataclass
class DayMetrics:
    total_active_seconds: int = 0
    first_activity: str = ""
    last_activity: str = ""
    total_break_seconds: int = 0
    break_count: int = 0
    category_seconds: dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "total_active_seconds": self.total_active_seconds,
            "first_activity": self.first_activity,
            "last_activity": self.last_activity,
            "total_break_seconds": self.total_break_seconds,
            "break_count": self.break_count,
            "category_seconds": self.category_seconds,
        }


# --- Core algorithms ---

def merge_sessions(events: list[dict], gap_threshold: int = 30) -> list[ActivitySession]:
    """Merge raw window events into contiguous activity sessions.

    Events must be sorted by timestamp ASC and have keys:
    timestamp, app_class, app_name, window_title, browser_domain
    """
    if not events:
        return []

    sessions: list[ActivitySession] = []
    current = events[0]
    current_ts = datetime.fromisoformat(current["timestamp"])
    session = ActivitySession(
        app_class=current["app_class"],
        category=categorize_app(current["app_class"]),
        start=current_ts,
        end=current_ts,
        window_titles=[current["window_title"]] if current["window_title"] else [],
        browser_domains=[current["browser_domain"]] if current["browser_domain"] else [],
        event_count=1,
    )

    for i in range(1, len(events)):
        ev = events[i]
        ev_ts = datetime.fromisoformat(ev["timestamp"])
        gap = (ev_ts - session.end).total_seconds()

        if ev["app_class"] == session.app_class and gap <= gap_threshold:
            # Extend current session
            session.end = ev_ts
            session.event_count += 1
            if ev["window_title"] and ev["window_title"] not in session.window_titles:
                if len(session.window_titles) < 10:
                    session.window_titles.append(ev["window_title"])
            if ev["browser_domain"] and ev["browser_domain"] not in session.browser_domains:
                session.browser_domains.append(ev["browser_domain"])
        else:
            # Finalize current session and start new one
            sessions.append(session)
            session = ActivitySession(
                app_class=ev["app_class"],
                category=categorize_app(ev["app_class"]),
                start=ev_ts,
                end=ev_ts,
                window_titles=[ev["window_title"]] if ev["window_title"] else [],
                browser_domains=[ev["browser_domain"]] if ev["browser_domain"] else [],
                event_count=1,
            )

    sessions.append(session)
    return sessions


def detect_breaks(sessions: list[ActivitySession], min_break_seconds: int = 300) -> list[Break]:
    """Detect breaks (gaps >5min) between sessions."""
    breaks: list[Break] = []
    for i in range(1, len(sessions)):
        gap = (sessions[i].start - sessions[i - 1].end).total_seconds()
        if gap >= min_break_seconds:
            breaks.append(Break(start=sessions[i - 1].end, end=sessions[i].start))
    return breaks


def compute_metrics(sessions: list[ActivitySession], breaks: list[Break]) -> DayMetrics:
    """Compute day-level metrics from sessions and breaks."""
    if not sessions:
        return DayMetrics()

    total_active = sum(s.duration_seconds for s in sessions)
    total_break = sum(b.duration_seconds for b in breaks)

    category_seconds: dict[str, int] = {}
    for s in sessions:
        category_seconds[s.category] = category_seconds.get(s.category, 0) + s.duration_seconds

    return DayMetrics(
        total_active_seconds=total_active,
        first_activity=sessions[0].start.isoformat(),
        last_activity=sessions[-1].end.isoformat(),
        total_break_seconds=total_break,
        break_count=len(breaks),
        category_seconds=category_seconds,
    )


# --- AI Summary ---

def _compact_sessions(sessions: list[ActivitySession]) -> list[ActivitySession]:
    """Merge adjacent sessions for a compact AI prompt.

    Two passes:
    1. Merge same-category neighbours (gap < 5min)
    2. Absorb micro-sessions (< 30s) into their neighbour

    Reduces 200+ micro-sessions to ~20-40 blocks.
    """
    if not sessions:
        return []

    def _clone(s: ActivitySession) -> ActivitySession:
        return ActivitySession(
            app_class=s.app_class, category=s.category,
            start=s.start, end=s.end,
            window_titles=list(s.window_titles),
            browser_domains=list(s.browser_domains),
            event_count=s.event_count,
        )

    def _absorb(dst: ActivitySession, src: ActivitySession) -> None:
        if src.end > dst.end:
            dst.end = src.end
        if src.start < dst.start:
            dst.start = src.start
        dst.event_count += src.event_count
        for t in src.window_titles:
            if t not in dst.window_titles and len(dst.window_titles) < 8:
                dst.window_titles.append(t)
        for d in src.browser_domains:
            if d not in dst.browser_domains:
                dst.browser_domains.append(d)

    # Pass 1: merge same-category neighbours
    merged: list[ActivitySession] = [_clone(sessions[0])]
    for s in sessions[1:]:
        cur = merged[-1]
        gap = (s.start - cur.end).total_seconds()
        if s.category == cur.category and gap < 300:
            _absorb(cur, s)
        else:
            merged.append(_clone(s))

    # Pass 2: absorb micro-sessions (< 30s) into the longer neighbour
    if len(merged) <= 1:
        return merged

    final: list[ActivitySession] = []
    for s in merged:
        if s.duration_seconds < 30 and final:
            # Absorb into previous
            _absorb(final[-1], s)
        else:
            final.append(s)

    # Also absorb trailing micro-sessions that couldn't go left
    cleaned: list[ActivitySession] = []
    for i, s in enumerate(final):
        if s.duration_seconds < 30 and cleaned:
            _absorb(cleaned[-1], s)
        elif s.duration_seconds < 30 and i + 1 < len(final):
            _absorb(final[i + 1], s)
        else:
            cleaned.append(s)

    return cleaned


def _build_ai_prompt(sessions: list[ActivitySession], metrics: DayMetrics) -> str:
    """Build the prompt for AI day summary."""
    # Compact sessions to reduce prompt size for local LLMs
    compact = _compact_sessions(sessions)

    session_lines = []
    for s in compact:
        titles = ", ".join(s.window_titles[:5]) if s.window_titles else "keine Titel"
        domains = ", ".join(s.browser_domains[:5]) if s.browser_domains else ""
        dur_min = s.duration_seconds // 60
        start_t = s.start.strftime("%H:%M")
        end_t = s.end.strftime("%H:%M")
        line = f"- {start_t}-{end_t} [{s.category}] {s.app_class} ({dur_min}min): {titles}"
        if domains:
            line += f" | Domains: {domains}"
        session_lines.append(line)

    sessions_text = "\n".join(session_lines)

    cat_lines = []
    for cat, secs in sorted(metrics.category_seconds.items(), key=lambda x: -x[1]):
        h = secs // 3600
        m = (secs % 3600) // 60
        cat_lines.append(f"  {cat}: {h}h {m}m")
    cat_text = "\n".join(cat_lines)

    active_h = metrics.total_active_seconds // 3600
    active_m = (metrics.total_active_seconds % 3600) // 60

    return f"""Du bist ein Zeiterfassungs-Assistent. Erstelle aus den folgenden Rohdaten eine professionelle Zeiterfassung fuer den Tag.

## Rohdaten (automatisch erfasste Sessions):
{sessions_text}

## Metriken:
- Aktive Zeit: {active_h}h {active_m}m
- Pausen: {metrics.break_count} ({metrics.total_break_seconds // 60}min gesamt)

## Kategorien:
{cat_text}

## Regeln:
1. **Gruppiere nach TAETIGKEIT, nicht nach App-Kategorie.** "E-Mails pruefen" ist ein Block, "Am Projekt X arbeiten" ist ein Block, "Amazon-Recherche" ist ein Block — auch wenn alles im Browser war.
2. **Keine Ueberlappungen.** Jeder Block beginnt nach dem Ende des vorherigen.
3. **Jeder Block mindestens 15 Minuten.** Sehr kurze Taetigkeiten (<5min) zum passenden Nachbar-Block dazunehmen.
4. **duration_minutes**: Durch 15 teilbar. Auf naechstes 15er-Vielfaches runden (23min->30, 49min->45, 8min->15).
5. **Uhrzeiten minutengenau** (z.B. "06:46-07:12").
6. **Pausen >15min** als eigenen Block mit category "pause".
7. **Beschreibung**: Konkret was getan wurde. Nenne besuchte Websites, bearbeitete Projekte, konkrete Tools.
8. **Typisch 4-10 Bloecke pro Tag.** Nicht alles in einen Block packen, aber auch nicht jede Minute einzeln.

## Beispiel:
Aus diesen Sessions:
  06:46-06:48 firefox (ScreenDiary, NI-Toolbox)
  06:48-06:51 evolution (E-Mails)
  06:51-07:03 firefox (GitHub, Telegram Web, NI-Toolbox)
  07:03-07:14 firefox (Amazon.de)
  07:14-07:25 codium (screendiary/app.py)
  07:25-07:32 konsole (git, npm)

Werden diese Bloecke (gruppiert nach Taetigkeit):
  06:46-06:48 "Tagesbeginn" — ScreenDiary und NI-Toolbox geoeffnet (15min)
  06:48-06:51 "E-Mails" — E-Mail-Pruefung in Evolution (15min)
  06:51-07:03 "Web: interne Tools" — GitHub PRs, Telegram Nachrichten, NI-Toolbox (15min)
  07:03-07:14 "Recherche Amazon" — Produktrecherche auf Amazon.de (15min)
  07:14-07:32 "ScreenDiary Entwicklung" — Coding in codium (app.py), Terminal: git, npm build (30min)

Erstelle eine JSON-Antwort:
{{
  "summary": "Kurze Zusammenfassung des Tages (2-3 Saetze, Deutsch).",
  "blocks": [
    {{
      "time_range": "07:14-07:32",
      "duration_minutes": 30,
      "label": "ScreenDiary Entwicklung",
      "description": "Coding in codium an app.py, danach git-Befehle und npm build im Terminal.",
      "category": "coding"
    }}
  ]
}}

Antworte NUR mit dem JSON, kein anderer Text."""


def _round_15(minutes: int) -> int:
    """Round to nearest multiple of 15. Minimum 15."""
    if minutes <= 0:
        return 15
    rounded = round(minutes / 15) * 15
    return max(rounded, 15)


def _parse_time_range(tr: str) -> tuple[int, int] | None:
    """Parse 'HH:MM-HH:MM' into (start_minutes, end_minutes). Returns None on failure."""
    parts = re.split(r"[-–]", tr)
    if len(parts) != 2:
        return None
    try:
        sh, sm = map(int, parts[0].strip().split(":"))
        eh, em = map(int, parts[1].strip().split(":"))
        return sh * 60 + sm, eh * 60 + em
    except (ValueError, IndexError):
        return None


def _format_time_range(start_min: int, end_min: int) -> str:
    return f"{start_min // 60:02d}:{start_min % 60:02d}-{end_min // 60:02d}:{end_min % 60:02d}"


def _postprocess_blocks(result: dict) -> dict:
    """Post-process AI blocks: merge overlapping same-category, enforce 15-min durations."""
    blocks = result.get("blocks")
    if not blocks:
        return result

    # Step 1: Parse all blocks, assign start/end minutes
    parsed = []
    for block in blocks:
        times = _parse_time_range(block.get("time_range", ""))
        if times:
            parsed.append({**block, "_start": times[0], "_end": times[1]})
        else:
            parsed.append(block)

    # Step 2: Merge overlapping blocks with same category (only truly overlapping/adjacent)
    merged: list[dict] = []
    for block in parsed:
        if "_start" not in block:
            merged.append(block)
            continue

        if merged and "_start" in merged[-1] and merged[-1].get("category") == block.get("category"):
            prev = merged[-1]
            gap = block["_start"] - prev["_end"]
            if gap <= 2:
                prev["_end"] = max(prev["_end"], block["_end"])
                prev["time_range"] = _format_time_range(prev["_start"], prev["_end"])
                # Combine descriptions, dedup fragments
                prev_desc = prev.get("description", "")
                new_desc = block.get("description", "")
                if new_desc and new_desc not in prev_desc:
                    prev_clean = prev_desc.rstrip(". ")
                    new_clean = new_desc.rstrip(". ")
                    prev["description"] = f"{prev_clean}. {new_clean}."
                continue

        merged.append(block)

    # Step 3: Round durations to 15-min multiples
    for block in merged:
        if "_start" in block and "_end" in block:
            raw = block["_end"] - block["_start"]
            block["duration_minutes"] = _round_15(raw)
            block["time_range"] = _format_time_range(block["_start"], block["_end"])
        else:
            dur = block.get("duration_minutes")
            if isinstance(dur, (int, float)):
                block["duration_minutes"] = _round_15(int(dur))
            else:
                block["duration_minutes"] = 15

    # Clean internal keys
    for block in merged:
        block.pop("_start", None)
        block.pop("_end", None)

    result["blocks"] = merged
    return result


async def _call_ai_json(config: Config, prompt: str) -> dict | None:
    """Call AI API and parse JSON response. Shared by summary and MOTD."""
    client = AsyncOpenAI(
        base_url=config.ai.api_base,
        api_key=config.ai.api_key or "unused",
    )

    try:
        try:
            response = await client.chat.completions.create(
                model=config.ai.chat_model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                response_format={"type": "json_object"},
            )
        except Exception:
            response = await client.chat.completions.create(
                model=config.ai.chat_model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
            )

        content = response.choices[0].message.content or ""

        try:
            return json.loads(content)
        except json.JSONDecodeError:
            pass

        match = re.search(r'\{[\s\S]*\}', content)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                pass

        log.warning("ai_parse_failed", content=content[:200])
        return None

    except Exception as e:
        log.error("ai_call_failed", error=str(e))
        return None


async def generate_ai_summary(
    config: Config,
    sessions: list[ActivitySession],
    metrics: DayMetrics,
) -> dict | None:
    """Generate AI summary for the day. Returns dict with summary+blocks or None."""
    if not config.ai.enabled or not config.ai.api_key:
        return None

    prompt = _build_ai_prompt(sessions, metrics)
    result = await _call_ai_json(config, prompt)

    if result and "blocks" in result:
        result = _postprocess_blocks(result)

    return result


# --- MOTD (Message of the Day) ---

def _build_motd_prompt(
    ai_summary_text: str | None,
    today_date: str,
) -> str:
    """Build prompt for MOTD generation based on the AI day summary."""
    from datetime import datetime as _dt
    hour = _dt.now().hour
    if hour < 12:
        greeting = "Guten Morgen"
    elif hour < 17:
        greeting = "Guten Tag"
    else:
        greeting = "Guten Abend"

    context = ai_summary_text if ai_summary_text else "Keine Zusammenfassung vorhanden."

    return f"""Erstelle eine kurze, motivierende Tagesnachricht basierend auf der Zusammenfassung des Arbeitstages.

Datum: {today_date}
Tageszeit-Gruss: {greeting}

## Zusammenfassung des Tages:
{context}

## Regeln:
- Maximal 1-2 Saetze
- Beginne mit "{greeting}!"
- Beziehe dich inhaltlich auf die Taetigkeiten (z.B. Projekte, Themen), NICHT auf Uhrzeiten oder Dauern
- Nenne KEINE Zeiten, Stunden, Minuten oder Dauern
- Freundlich, knapp, motivierend
- Auf Deutsch

Erstelle eine JSON-Antwort:
{{
  "motd": "Die Tagesnachricht hier"
}}

Antworte NUR mit dem JSON."""


async def generate_motd(
    config: Config,
    ai_summary_text: str | None,
    today_date: str,
) -> str | None:
    """Generate Message of the Day based on the AI day summary. Returns string or None."""
    if not config.ai.enabled or not config.ai.api_key:
        return None

    prompt = _build_motd_prompt(ai_summary_text, today_date)
    result = await _call_ai_json(config, prompt)

    if result and "motd" in result:
        return result["motd"]
    return None
