"""FastAPI application factory."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from ..config import Config
from ..db import Database
from ..search import SearchEngine
from ..storage.manager import StorageManager
from .routes import activity, api, screenshots, search

_WEB_DIR = Path(__file__).parent


def create_app(config: Config) -> FastAPI:
    db = Database(config)
    db.init()

    storage = StorageManager(config, db)
    search_engine = SearchEngine(config, db)
    templates = Jinja2Templates(directory=str(_WEB_DIR / "templates"))

    app = FastAPI(title="ScreenDiary", version="0.1.0")

    # Store shared state
    app.state.config = config
    app.state.db = db
    app.state.storage = storage
    app.state.search_engine = search_engine
    app.state.templates = templates

    # Static files
    app.mount("/static", StaticFiles(directory=str(_WEB_DIR / "static")), name="static")

    # React frontend build output
    frontend_dist = _WEB_DIR / "frontend_dist"
    if frontend_dist.is_dir():
        app.mount(
            "/assets",
            StaticFiles(directory=str(frontend_dist / "assets")),
            name="frontend-assets",
        )

    # Serve static files from frontend_dist root (logo, favicons, etc.)
    if frontend_dist.is_dir():
        _dist_static = {
            f.name: f for f in frontend_dist.iterdir()
            if f.is_file() and f.suffix in (".png", ".svg", ".ico", ".webmanifest")
        }
        for _fname, _fpath in _dist_static.items():
            _p = _fpath  # capture for closure

            @app.get(f"/{_fname}", name=f"static-{_fname}")
            async def _serve_static(_p=_p):
                return FileResponse(_p)

    # Include routers
    app.include_router(api.router, prefix="/api")
    app.include_router(activity.router, prefix="/api")
    app.include_router(search.router, prefix="/api/search")
    app.include_router(screenshots.router)

    # Page routes
    if frontend_dist.is_dir():
        _index_html = (frontend_dist / "index.html").read_text()

        @app.get("/", response_class=HTMLResponse)
        async def index(request: Request):
            return HTMLResponse(_index_html)

        @app.get("/player", response_class=HTMLResponse)
        async def player(request: Request):
            return HTMLResponse(_index_html)

        @app.get("/activity", response_class=HTMLResponse)
        async def activity_page(request: Request):
            return HTMLResponse(_index_html)

        @app.get("/timeline", response_class=HTMLResponse)
        async def timeline(request: Request):
            return templates.TemplateResponse("timeline.html", {
                "request": request,
                "config": config,
            })

        @app.get("/screenshot/{screenshot_id}", response_class=HTMLResponse)
        async def detail(request: Request, screenshot_id: int):
            s = db.get_screenshot(screenshot_id)
            if not s:
                return HTMLResponse("Not found", status_code=404)
            monitors = db.get_monitor_captures(screenshot_id)
            ocr_text = db.get_ocr_text(screenshot_id)
            return templates.TemplateResponse("detail.html", {
                "request": request,
                "screenshot": s,
                "monitors": monitors,
                "ocr_text": ocr_text,
                "config": config,
            })

        @app.get("/search", response_class=HTMLResponse)
        async def search_page(request: Request):
            return templates.TemplateResponse("search.html", {
                "request": request,
                "config": config,
            })
    else:
        # Fallback to Jinja2 templates when no React build present
        @app.get("/", response_class=HTMLResponse)
        async def index(request: Request):
            return templates.TemplateResponse("timeline.html", {
                "request": request,
                "config": config,
            })

        @app.get("/timeline", response_class=HTMLResponse)
        async def timeline(request: Request):
            return templates.TemplateResponse("timeline.html", {
                "request": request,
                "config": config,
            })

        @app.get("/screenshot/{screenshot_id}", response_class=HTMLResponse)
        async def detail(request: Request, screenshot_id: int):
            s = db.get_screenshot(screenshot_id)
            if not s:
                return HTMLResponse("Not found", status_code=404)
            monitors = db.get_monitor_captures(screenshot_id)
            ocr_text = db.get_ocr_text(screenshot_id)
            return templates.TemplateResponse("detail.html", {
                "request": request,
                "screenshot": s,
                "monitors": monitors,
                "ocr_text": ocr_text,
                "config": config,
            })

        @app.get("/player", response_class=HTMLResponse)
        async def player(request: Request):
            return templates.TemplateResponse("player.html", {
                "request": request,
                "config": config,
            })

        @app.get("/search", response_class=HTMLResponse)
        async def search_page(request: Request):
            return templates.TemplateResponse("search.html", {
                "request": request,
                "config": config,
            })

    @app.on_event("shutdown")
    async def shutdown():
        db.close()

    return app
