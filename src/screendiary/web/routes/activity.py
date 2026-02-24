"""Activity tracking API routes."""

from __future__ import annotations

import json

from fastapi import APIRouter, Request

from datetime import date as date_type, timedelta

from ...activity_summarizer import (
    compute_metrics,
    detect_breaks,
    generate_ai_summary,
    generate_motd,
    merge_sessions,
)

router = APIRouter(tags=["activity"])


@router.get("/activity/summary")
async def activity_summary(request: Request, date: str = ""):
    if not date:
        return {"error": "date parameter required"}, 400

    db = request.app.state.db
    config = request.app.state.config
    interval = config.capture.interval

    event_count = db.get_window_event_count(date)
    total_seconds = event_count * interval

    top_apps = db.get_top_apps(date, limit=15)
    for app in top_apps:
        app["seconds"] = app["count"] * interval

    top_titles = db.get_top_window_titles(date, limit=15)
    for title in top_titles:
        title["seconds"] = title["count"] * interval

    top_domains = db.get_top_browser_domains(date, limit=15)
    for domain in top_domains:
        domain["seconds"] = domain["count"] * interval

    timeline = db.get_activity_timeline(date)

    return {
        "date": date,
        "total_seconds": total_seconds,
        "interval": interval,
        "top_apps": top_apps,
        "top_titles": top_titles,
        "top_domains": top_domains,
        "timeline": timeline,
    }


@router.get("/activity/day-summary")
async def day_summary(request: Request, date: str = "", regenerate: bool = False):
    if not date:
        return {"error": "date parameter required"}, 400

    db = request.app.state.db
    config = request.app.state.config

    # Get all window events for the day
    events = db.get_window_events_for_day(date)
    event_count = len(events)

    if not events:
        return {
            "date": date,
            "sessions": [],
            "metrics": {
                "total_active_seconds": 0,
                "first_activity": "",
                "last_activity": "",
                "total_break_seconds": 0,
                "break_count": 0,
                "category_seconds": {},
            },
            "breaks": [],
            "ai_summary": None,
        }

    # Deterministic analysis
    sessions = merge_sessions(events)
    breaks = detect_breaks(sessions)
    metrics = compute_metrics(sessions, breaks)

    # AI summary: only return cache unless explicitly requested
    ai_summary = None
    if config.ai.enabled and config.ai.api_key:
        cached = db.get_cached_day_summary(date)

        if cached and not regenerate:
            try:
                ai_summary = json.loads(cached["summary_text"])
            except (json.JSONDecodeError, TypeError):
                ai_summary = None

        # Only generate on explicit button click (regenerate=True)
        if regenerate or (ai_summary is None and regenerate):
            ai_result = await generate_ai_summary(config, sessions, metrics)
            if ai_result:
                ai_summary = ai_result
                db.save_day_summary(
                    date=date,
                    summary_text=json.dumps(ai_summary, ensure_ascii=False),
                    session_labels="",
                    model=config.ai.chat_model,
                    event_count=event_count,
                )

    return {
        "date": date,
        "sessions": [s.to_dict() for s in sessions],
        "metrics": metrics.to_dict(),
        "breaks": [b.to_dict() for b in breaks],
        "ai_summary": ai_summary,
    }


@router.get("/activity/motd")
async def motd(request: Request):
    """Get or generate Message of the Day."""
    db = request.app.state.db
    config = request.app.state.config
    today = date_type.today().isoformat()

    # Return cached MOTD if available
    cached = db.get_cached_motd(today)
    if cached:
        return {"motd": cached, "date": today}

    if not config.ai.enabled or not config.ai.api_key:
        return {"motd": None, "date": today}

    # Build metrics for today and yesterday
    yesterday = (date_type.today() - timedelta(days=1)).isoformat()

    today_metrics = None
    today_events = db.get_window_events_for_day(today)
    if today_events:
        today_sessions = merge_sessions(today_events)
        today_breaks = detect_breaks(today_sessions)
        today_metrics = compute_metrics(today_sessions, today_breaks)

    yesterday_metrics = None
    yesterday_events = db.get_window_events_for_day(yesterday)
    if yesterday_events:
        yesterday_sessions = merge_sessions(yesterday_events)
        yesterday_breaks = detect_breaks(yesterday_sessions)
        yesterday_metrics = compute_metrics(yesterday_sessions, yesterday_breaks)

    motd_text = await generate_motd(config, today_metrics, yesterday_metrics, today)

    if motd_text:
        db.save_motd(today, motd_text)

    return {"motd": motd_text, "date": today}
