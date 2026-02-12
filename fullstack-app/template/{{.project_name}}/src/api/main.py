from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager, suppress
from pathlib import Path
from typing import TYPE_CHECKING

from fastapi import APIRouter, FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from core.config import settings
from core.errors import AppError
from core.logging_config import configure_logging
from core.middleware import RequestContextMiddleware
from routers import health

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

logger = logging.getLogger(__name__)

# Static files directory (Next.js build output)
STATIC_DIR = Path(__file__).parent.parent / "static"


class ConnectionManager:
    """Manages WebSocket connections for real-time communication."""

    def __init__(self) -> None:
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket) -> None:
        self.active_connections.remove(websocket)

    async def send_personal_message(self, message: str, websocket: WebSocket) -> None:
        await websocket.send_text(message)

    async def broadcast(self, message: str) -> None:
        for connection in self.active_connections:
            await connection.send_text(message)


manager = ConnectionManager()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan handler with graceful shutdown."""
    # Startup
    configure_logging(level="DEBUG" if settings.debug else "INFO")
    logger.info("Application starting up...")

    # Start background token refresh if Lakebase is configured
    _service = None
    if settings.instance_name:
        from services import DatabricksService

        _service = DatabricksService()
        await _service.token_manager.start_background_refresh()
        logger.info("Background token refresh started for Lakebase instance: %s", settings.instance_name)

    yield

    # Stop background token refresh
    if _service is not None:
        await _service.token_manager.stop_background_refresh()
        logger.info("Background token refresh stopped")

    # Shutdown (Databricks Apps has 15s limit, so we use short timeouts)
    logger.info("Shutdown initiated...")
    for ws in manager.active_connections[:]:
        with suppress(Exception):
            await asyncio.wait_for(ws.close(1001, "Server shutting down"), timeout=2.0)
    manager.active_connections.clear()
    logger.info("Shutdown complete")


app = FastAPI(
    title=settings.api_title,
    version=settings.api_version,
    lifespan=lifespan,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add request context middleware (extracts X-Forwarded-Access-Token for per-user auth)
app.add_middleware(RequestContextMiddleware)


# Global exception handlers for consistent error responses
@app.exception_handler(AppError)
async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    """Handle structured application errors."""
    return JSONResponse(status_code=exc.status_code, content={"error": exc.to_dict()})


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    """Handle FastAPI HTTP exceptions with consistent format."""
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": {"code": exc.status_code, "message": exc.detail}},
    )


@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Handle unexpected exceptions with logging."""
    logger.exception("Unhandled exception: %s", exc)
    return JSONResponse(
        status_code=500,
        content={"error": {"code": 500, "message": "Internal server error"}},
    )


# API Router - all REST endpoints under /api
api_router = APIRouter(prefix="/api")
api_router.include_router(health.router)


@api_router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    """WebSocket endpoint at /api/ws for real-time communication."""
    await manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            await manager.send_personal_message(f"You sent: {data}", websocket)
            await manager.broadcast(f"Client says: {data}")
    except WebSocketDisconnect:
        manager.disconnect(websocket)
        await manager.broadcast("A client disconnected")


# Include API router
app.include_router(api_router)


# SPA fallback - serve static files and index.html for client-side routes
if STATIC_DIR.exists() and (STATIC_DIR / "index.html").exists():
    # Mount static assets (js, css, images, etc.)
    app.mount("/_next", StaticFiles(directory=STATIC_DIR / "_next"), name="next_static")

    @app.get("/{full_path:path}")
    async def serve_spa(request: Request, full_path: str) -> FileResponse:
        """Serve static files or fallback to index.html for SPA routing."""
        # Check if requesting a static file
        file_path = STATIC_DIR / full_path
        if file_path.is_file():
            return FileResponse(file_path)

        # Fallback to index.html for client-side routing
        return FileResponse(STATIC_DIR / "index.html")
