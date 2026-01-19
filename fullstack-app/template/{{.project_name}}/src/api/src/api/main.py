from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import APIRouter, FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .core.config import settings
from .core.middleware import RequestContextMiddleware
from .routers import health

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
    """Application lifespan handler."""
    # Startup
    yield
    # Shutdown
    manager.active_connections.clear()


app = FastAPI(
    title=settings.api_title,
    version=settings.api_version,
    lifespan=lifespan,
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
