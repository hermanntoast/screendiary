"""Screenshot image serving - transparent WebP/Video extraction."""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import Response

router = APIRouter(tags=["screenshots"])


@router.get("/screenshots/{screenshot_id}/image")
async def get_image(
    request: Request,
    screenshot_id: int,
    monitor: int = 0,
    thumb: bool = False,
):
    storage = request.app.state.storage

    if thumb:
        data = storage.get_thumbnail(screenshot_id)
        if data:
            return Response(content=data, media_type="image/webp")
        return Response(status_code=404)

    data = storage.get_screenshot_frame(screenshot_id, monitor_index=monitor)
    if data:
        return Response(content=data, media_type="image/webp")
    return Response(status_code=404)
