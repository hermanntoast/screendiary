"""Search API routes: FTS5 text search, AI semantic search, AI chat."""

from __future__ import annotations

import json
import re
from datetime import date as date_cls, datetime, timedelta

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
from openai import AsyncOpenAI

_STOP_WORDS = frozenset(
    "ich du er sie es wir ihr mir dir was wer wie wo wann warum wieso weshalb welche welcher welches "
    "habe hat hatte haben bin ist sind war waren wird werden wurde "
    "mein meine dein deine sein seine unser eure ihre "
    "der die das den dem des ein eine einer einem einen "
    "und oder aber denn nicht kein keine noch auch schon nur "
    "im in an auf am um aus bei von zu mit nach ueber fuer durch "
    "heute morgen gestern morgens abends mal eben gerade zeig zeige "
    "the a an is are was were has have had do does did "
    "i me my you your he she it we they this that".split()
)


def _extract_keywords(text: str) -> str:
    """Extract content words from a natural-language query for FTS5 search."""
    words = re.findall(r"[a-zA-ZäöüßÄÖÜ]{3,}", text.lower())
    keywords = [w for w in words if w not in _STOP_WORDS]
    return " ".join(keywords)


def _parse_time_range(text: str) -> tuple[str | None, str | None]:
    """Extract a time range (ts_from, ts_to) from natural language.

    Understands: heute morgen, heute nachmittag, gestern, heute,
    vorhin, letzte stunde, etc.
    """
    low = text.lower()
    today = date_cls.today()
    yesterday = today - timedelta(days=1)

    ts_from: str | None = None
    ts_to: str | None = None

    # Explicit date patterns like "am 20.02" or "am 20.02.2026"
    m = re.search(r"am\s+(\d{1,2})\.(\d{1,2})(?:\.(\d{2,4}))?", low)
    if m:
        day, month = int(m.group(1)), int(m.group(2))
        year = int(m.group(3)) if m.group(3) else today.year
        if year < 100:
            year += 2000
        try:
            d = date_cls(year, month, day)
            ts_from = f"{d.isoformat()}T00:00:00"
            ts_to = f"{d.isoformat()}T23:59:59"
        except ValueError:
            pass

    # "gestern" / "yesterday"
    elif "gestern" in low:
        base = yesterday
        ts_from = f"{base.isoformat()}T00:00:00"
        ts_to = f"{base.isoformat()}T23:59:59"
        if "morgen" in low or "frueh" in low or "früh" in low:
            ts_from = f"{base.isoformat()}T05:00:00"
            ts_to = f"{base.isoformat()}T12:00:00"
        elif "nachmittag" in low:
            ts_from = f"{base.isoformat()}T12:00:00"
            ts_to = f"{base.isoformat()}T18:00:00"
        elif "abend" in low:
            ts_from = f"{base.isoformat()}T18:00:00"
            ts_to = f"{base.isoformat()}T23:59:59"

    # "heute" / "today" (or implicit if "morgen"/"nachmittag" without "gestern")
    elif "heute" in low or "morgens" in low or "nachmittag" in low or "abend" in low or "vorhin" in low:
        base = today
        ts_from = f"{base.isoformat()}T00:00:00"
        ts_to = datetime.now().isoformat()
        if any(w in low for w in ("morgen", "morgens", "frueh", "früh")):
            ts_from = f"{base.isoformat()}T05:00:00"
            ts_to = f"{base.isoformat()}T12:00:00"
        elif "nachmittag" in low:
            ts_from = f"{base.isoformat()}T12:00:00"
            ts_to = f"{base.isoformat()}T18:00:00"
        elif "abend" in low:
            ts_from = f"{base.isoformat()}T18:00:00"
            ts_to = datetime.now().isoformat()

    # "letzte stunde"
    elif "letzte stunde" in low or "letzten stunde" in low:
        ts_from = (datetime.now() - timedelta(hours=1)).isoformat()
        ts_to = datetime.now().isoformat()

    # "letzte X minuten"
    elif m := re.search(r"letzten?\s+(\d+)\s+min", low):
        mins = int(m.group(1))
        ts_from = (datetime.now() - timedelta(minutes=mins)).isoformat()
        ts_to = datetime.now().isoformat()

    return ts_from, ts_to

router = APIRouter(tags=["search"])


@router.get("/text")
async def text_search(request: Request, q: str = "", limit: int = 50):
    engine = request.app.state.search_engine
    results = engine.text_search(q, limit=limit)
    return {
        "query": q,
        "results": [
            {
                "screenshot_id": r.screenshot.id,
                "timestamp": r.screenshot.timestamp.isoformat(),
                "date": r.screenshot.date,
                "score": round(r.score, 4),
                "highlights": r.highlights,
                "ocr_text": r.ocr_text[:300],
                "thumb_url": f"/screenshots/{r.screenshot.id}/image?thumb=true",
            }
            for r in results
        ],
        "total": len(results),
    }


@router.get("/ai")
async def ai_search(request: Request, q: str = "", limit: int = 20):
    engine = request.app.state.search_engine
    results = await engine.ai_search(q, limit=limit)
    return {
        "query": q,
        "results": [
            {
                "screenshot_id": r.screenshot.id,
                "timestamp": r.screenshot.timestamp.isoformat(),
                "date": r.screenshot.date,
                "score": round(r.score, 4),
                "ocr_text": r.ocr_text[:300],
                "thumb_url": f"/screenshots/{r.screenshot.id}/image?thumb=true",
            }
            for r in results
        ],
        "total": len(results),
    }


def _build_activity_context(events: list[dict], max_lines: int = 60) -> str:
    """Compact window events into a readable context block.

    Groups consecutive events with same app+title to avoid repetition.
    """
    if not events:
        return "(keine Aktivitaetsdaten im Zeitraum)"

    lines: list[str] = []
    prev_key = ""
    block_start = ""
    block_end = ""
    block_domains: list[str] = []

    def flush():
        if not block_start:
            return
        ts = block_start
        if block_start != block_end:
            ts = f"{block_start} - {block_end}"
        domain_str = f"  [{', '.join(block_domains)}]" if block_domains else ""
        lines.append(f"{ts} | {prev_key}{domain_str}")

    for ev in events:
        ts_short = ev["timestamp"][11:19] if len(ev["timestamp"]) > 11 else ev["timestamp"]
        key = f"{ev['app_class']}: {ev['window_title']}" if ev["window_title"] else ev["app_class"]
        domain = ev.get("browser_domain", "")

        if key == prev_key:
            block_end = ts_short
            if domain and domain not in block_domains:
                block_domains.append(domain)
        else:
            flush()
            prev_key = key
            block_start = ts_short
            block_end = ts_short
            block_domains = [domain] if domain else []

    flush()

    # Truncate if too long
    if len(lines) > max_lines:
        lines = lines[:max_lines] + [f"... ({len(lines) - max_lines} weitere Eintraege)"]

    return "\n".join(lines)


def _build_ocr_context(results: list, max_results: int = 5) -> str:
    """Build context from OCR search results."""
    if not results:
        return ""
    parts = []
    for r in results[:max_results]:
        ts = r.screenshot.timestamp.strftime("%Y-%m-%d %H:%M:%S")
        text = r.ocr_text[:400] if r.ocr_text else ""
        if text:
            parts.append(f"[{ts}] Screenshot #{r.screenshot.id}:\n{text}")
    return "\n\n---\n\n".join(parts)


_QUERY_ANALYSIS_PROMPT = """\
Du bist ein Query-Analyzer fuer eine Desktop-Aktivitaets-App (ScreenDiary).
Analysiere die Benutzeranfrage und extrahiere strukturierte Suchparameter.

Aktuelle Zeit: {now}
Heute: {today}
Gestern: {yesterday}

{history_context}

Benutzeranfrage: "{query}"

Antworte NUR mit JSON:
{{
  "ts_from": "YYYY-MM-DDTHH:MM:SS" oder null,
  "ts_to": "YYYY-MM-DDTHH:MM:SS" oder null,
  "activity_keywords": ["keyword1", "keyword2"],
  "ocr_keywords": ["keyword1", "keyword2"],
  "search_type": "activity" | "ocr" | "both"
}}

Regeln:
- activity_keywords: Begriffe fuer Fenstertitel, App-Namen, Domains (z.B. "London", "booking.com", "Firefox")
- ocr_keywords: Begriffe die im Bildschirmtext stehen koennten (z.B. "API Key", "sk-", "Passwort", konkreter Text)
- search_type: "activity" wenn nach Aktivitaeten/Websites gefragt wird, "ocr" wenn nach spezifischem Text, "both" wenn unklar
- Zeitangaben: "heute morgen" = {today}T05:00:00 bis {today}T12:00:00, "gestern abend" = {yesterday}T18:00:00 bis {yesterday}T23:59:59, etc.
- Bei Folgefragen: Nutze den Kontext der bisherigen Konversation, um fehlende Parameter zu ergaenzen
- Gib null bei ts_from/ts_to wenn kein Zeitraum erkennbar ist"""


async def _analyze_query(
    client: AsyncOpenAI, model: str, query: str, history: list[dict],
) -> dict:
    """Step 1: Use AI to analyze the user query into structured search params."""
    now = datetime.now()
    today = date_cls.today()
    yesterday = today - timedelta(days=1)

    # Build history context for follow-up awareness
    history_ctx = ""
    if history:
        recent = history[-6:]
        history_lines = []
        for m in recent:
            role = "User" if m.get("role") == "user" else "Assistant"
            content = m.get("content", "")[:200]
            history_lines.append(f"{role}: {content}")
        history_ctx = "Bisherige Konversation:\n" + "\n".join(history_lines)

    prompt = _QUERY_ANALYSIS_PROMPT.format(
        now=now.strftime("%Y-%m-%d %H:%M:%S"),
        today=today.isoformat(),
        yesterday=yesterday.isoformat(),
        query=query,
        history_context=history_ctx,
    )

    try:
        try:
            resp = await client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0,
                response_format={"type": "json_object"},
            )
        except Exception:
            resp = await client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0,
            )

        content = resp.choices[0].message.content or "{}"

        try:
            return json.loads(content)
        except json.JSONDecodeError:
            m = re.search(r"\{[\s\S]*\}", content)
            if m:
                return json.loads(m.group())
    except Exception:
        pass

    # Fallback: use regex-based parsing
    ts_from, ts_to = _parse_time_range(query)
    kw = _extract_keywords(query).split()
    return {
        "ts_from": ts_from,
        "ts_to": ts_to,
        "activity_keywords": kw,
        "ocr_keywords": kw,
        "search_type": "both",
    }


@router.post("/ai/chat")
async def ai_chat(request: Request):
    """AI chat with two-step approach:

    Step 1: AI analyzes query → structured search params (time, keywords, type)
    Step 2: Backend searches with those params → builds context
    Step 3: AI answers with the found context
    """
    config = request.app.state.config
    engine = request.app.state.search_engine
    db = request.app.state.db

    body = await request.json()
    query = body.get("query", "")
    history = body.get("history", [])

    if not config.ai.enabled or not config.ai.api_key:
        return {"error": "AI not configured"}

    client = AsyncOpenAI(
        base_url=config.ai.api_base,
        api_key=config.ai.api_key or "unused",
    )

    # --- Step 1: AI analyzes the query ---
    params = await _analyze_query(client, config.ai.chat_model, query, history)

    ts_from = params.get("ts_from")
    ts_to = params.get("ts_to")
    activity_kw = params.get("activity_keywords") or []
    ocr_kw = params.get("ocr_keywords") or []
    search_type = params.get("search_type", "both")

    # --- Step 2: Search with structured params ---

    # Activity context
    activity_context = ""
    if search_type in ("activity", "both"):
        # Try each activity keyword, take the one with best results
        best_events: list[dict] = []
        for kw in activity_kw:
            events = db.search_window_events(
                ts_from=ts_from, ts_to=ts_to, keyword=kw, limit=200,
            )
            if len(events) > len(best_events):
                best_events = events

        # If no keyword matched enough, search without keyword filter
        if len(best_events) < 3 and (ts_from or ts_to):
            events = db.search_window_events(
                ts_from=ts_from, ts_to=ts_to, limit=200,
            )
            if len(events) > len(best_events):
                best_events = events

        activity_context = _build_activity_context(best_events)

    # OCR context
    ocr_context = ""
    if search_type in ("ocr", "both") and ocr_kw:
        ocr_query = " ".join(ocr_kw)
        ocr_results = await engine.ai_search(ocr_query, limit=5)
        if not ocr_results:
            fts_q = " ".join(f'"{w}"' for w in ocr_kw if w)
            if fts_q:
                try:
                    ocr_results = engine.text_search(fts_q, limit=5)
                except Exception:
                    ocr_results = []
        # Time-filter OCR results
        if ocr_results and ts_from:
            ocr_results = [
                r for r in ocr_results
                if ts_from <= r.screenshot.timestamp.isoformat() <= (ts_to or "9999")
            ]
        ocr_context = _build_ocr_context(ocr_results)

    # --- Step 3: Build prompt and stream answer ---
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    time_info = ""
    if ts_from and ts_to:
        time_info = f"\nAngefragter Zeitraum: {ts_from} bis {ts_to}\n"

    context_sections = [f"Aktuelle Zeit: {now}", time_info]

    if activity_context and activity_context != "(keine Aktivitaetsdaten im Zeitraum)":
        context_sections.append(
            f"## Aktivitaetsverlauf (Fenstertitel, Apps, Domains):\n{activity_context}"
        )

    if ocr_context:
        context_sections.append(
            f"## Bildschirminhalt (OCR-Text von Screenshots):\n{ocr_context}"
        )

    context_block = "\n\n".join(s for s in context_sections if s)

    system_prompt = (
        "Du bist der ScreenDiary-Assistent. Du hilfst dem Benutzer, seine aufgezeichneten "
        "Desktop-Aktivitaeten zu durchsuchen und zu verstehen.\n\n"
        "Dir stehen zwei Datenquellen zur Verfuegung:\n"
        "1. **Aktivitaetsverlauf**: Fenstertitel, App-Namen, Browser-Domains mit Zeitstempeln\n"
        "2. **OCR-Text**: Erkannter Text direkt vom Bildschirm (Screenshots)\n\n"
        "## Regeln:\n"
        "- Beantworte Fragen praezise basierend auf den Daten\n"
        "- Nenne konkrete Uhrzeiten, Websites, Fenstertitel wenn moeglich\n"
        "- Wenn du eine Website/Domain findest, gib sie als Link an\n"
        "- Verweise auf Screenshot-IDs mit dem Format `Screenshot #123`, damit der Benutzer sie ansehen kann\n"
        "- Wenn der Kontext keine Antwort hergibt, sag das ehrlich\n"
        "- Antworte auf Deutsch\n\n"
        f"{context_block}"
    )

    messages = [{"role": "system", "content": system_prompt}]
    for msg in history[-10:]:
        messages.append({"role": msg.get("role", "user"), "content": msg.get("content", "")})
    messages.append({"role": "user", "content": query})

    async def generate():
        try:
            stream = await client.chat.completions.create(
                model=config.ai.chat_model,
                messages=messages,
                stream=True,
            )
            async for chunk in stream:
                if chunk.choices and chunk.choices[0].delta.content:
                    data = json.dumps({"content": chunk.choices[0].delta.content})
                    yield f"data: {data}\n\n"
            yield "data: [DONE]\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)})}\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")
