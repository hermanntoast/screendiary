"""Search API routes: FTS5 text search, AI semantic search, AI chat."""

from __future__ import annotations

import json

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
from openai import AsyncOpenAI

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


@router.post("/ai/chat")
async def ai_chat(request: Request):
    """AI chat with screenshot context. Streams response via SSE."""
    config = request.app.state.config
    engine = request.app.state.search_engine

    body = await request.json()
    query = body.get("query", "")
    history = body.get("history", [])

    if not config.ai.enabled or not config.ai.api_key:
        return {"error": "AI not configured"}

    # Find relevant screenshots
    results = await engine.ai_search(query, limit=5)

    # Build context
    context_parts = []
    for r in results:
        ts = r.screenshot.timestamp.strftime("%Y-%m-%d %H:%M:%S")
        text_preview = r.ocr_text[:500] if r.ocr_text else "(no text)"
        context_parts.append(f"[{ts}] Screenshot #{r.screenshot.id}:\n{text_preview}")

    context = "\n\n---\n\n".join(context_parts)

    system_prompt = (
        "Du bist ein Assistent, der dem Benutzer hilft, seine Desktop-Aktivitaeten zu durchsuchen. "
        "Dir werden Screenshots mit OCR-Text und Zeitstempeln als Kontext gegeben. "
        "Beantworte die Fragen basierend auf diesem Kontext. "
        "Wenn du auf bestimmte Screenshots verweist, nenne den Zeitstempel und die Screenshot-ID.\n\n"
        f"Kontext (relevante Screenshots):\n{context}"
    )

    messages = [{"role": "system", "content": system_prompt}]
    for msg in history[-10:]:
        messages.append({"role": msg.get("role", "user"), "content": msg.get("content", "")})
    messages.append({"role": "user", "content": query})

    client = AsyncOpenAI(
        base_url=config.ai.api_base,
        api_key=config.ai.api_key or "unused",
    )

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
