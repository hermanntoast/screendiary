"""REST API routes: Screenshots, Stats, Status."""

from __future__ import annotations

from fastapi import APIRouter, Request

router = APIRouter(tags=["api"])


@router.get("/screenshots")
async def list_screenshots(
    request: Request,
    date: str | None = None,
    page: int = 1,
):
    db = request.app.state.db
    config = request.app.state.config
    limit = config.web.page_size
    offset = (page - 1) * limit

    screenshots = db.get_screenshots(date=date, offset=offset, limit=limit)
    total = db.get_screenshot_count(date=date)

    return {
        "screenshots": [
            {
                "id": s.id,
                "timestamp": s.timestamp.isoformat(),
                "date": s.date,
                "width": s.width,
                "height": s.height,
                "file_size": s.file_size,
                "storage_type": s.storage_type,
                "thumb_url": f"/screenshots/{s.id}/image?thumb=true",
            }
            for s in screenshots
        ],
        "total": total,
        "page": page,
        "pages": (total + limit - 1) // limit if limit else 1,
    }


@router.get("/screenshots/{screenshot_id}")
async def get_screenshot(request: Request, screenshot_id: int):
    db = request.app.state.db
    s = db.get_screenshot(screenshot_id)
    if not s:
        return {"error": "not found"}, 404

    monitors = db.get_monitor_captures(screenshot_id)
    ocr_text = db.get_ocr_text(screenshot_id)

    return {
        "id": s.id,
        "timestamp": s.timestamp.isoformat(),
        "date": s.date,
        "width": s.width,
        "height": s.height,
        "file_size": s.file_size,
        "storage_type": s.storage_type,
        "monitors": [
            {
                "id": mc.id,
                "monitor_name": mc.monitor_name,
                "monitor_index": mc.monitor_index,
                "width": mc.width,
                "height": mc.height,
                "image_url": f"/screenshots/{screenshot_id}/image?monitor={mc.monitor_index}",
            }
            for mc in monitors
        ],
        "ocr_text": ocr_text,
    }


@router.get("/screenshots/{screenshot_id}/ocr-words")
async def get_ocr_words(request: Request, screenshot_id: int, q: str = ""):
    db = request.app.state.db
    grouped = db.get_ocr_words_for_screenshot(screenshot_id)
    monitors = db.get_monitor_captures(screenshot_id)
    q_lower = q.lower().strip()

    result = []
    for mc in monitors:
        words = grouped.get(mc.id, [])
        word_list = []
        for w in words:
            matched = bool(q_lower and q_lower in w["word"].lower())
            word_list.append({**w, "matched": matched})
        result.append({
            "monitor_capture_id": mc.id,
            "monitor_index": mc.monitor_index,
            "monitor_name": mc.monitor_name,
            "words": word_list,
        })
    return {"screenshot_id": screenshot_id, "query": q, "monitors": result}


@router.get("/timeline")
async def timeline(request: Request, date: str = ""):
    db = request.app.state.db
    if not date:
        return {"error": "date parameter required"}, 400
    entries = db.get_timeline(date)
    return {"date": date, "entries": entries, "count": len(entries)}


@router.get("/stats")
async def stats(request: Request):
    db = request.app.state.db
    config = request.app.state.config
    data = db.get_stats()
    data["max_storage_gb"] = config.storage.max_storage_gb
    db_path = config.storage.db_path
    data["db_size_bytes"] = db_path.stat().st_size if db_path.exists() else 0
    return data


@router.get("/dates")
async def dates(request: Request):
    db = request.app.state.db
    return db.get_dates()


@router.get("/status")
async def status(request: Request):
    return {"status": "ok", "service": "screendiary-web"}
