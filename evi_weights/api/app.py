"""FastAPI application factory."""

from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from evi_weights.api.dependencies import init_db
from evi_weights.api.routers import (
    backtest,
    calculate,
    config_api,
    export,
    regions,
    runs,
    scenarios,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


def create_app() -> FastAPI:
    app = FastAPI(title="EVI Weights API", version="1.0.0", lifespan=lifespan)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(calculate.router, prefix="/api")
    app.include_router(regions.router, prefix="/api")
    app.include_router(runs.router, prefix="/api")
    app.include_router(scenarios.router, prefix="/api")
    app.include_router(backtest.router, prefix="/api")
    app.include_router(config_api.router, prefix="/api")
    app.include_router(export.router, prefix="/api")

    # Serve frontend static files if built
    frontend_dist = Path(__file__).parent.parent.parent / "frontend" / "dist"
    if frontend_dist.is_dir():
        app.mount("/", StaticFiles(directory=str(frontend_dist), html=True))

    return app


def run_server():
    import uvicorn
    uvicorn.run("evi_weights.api.app:create_app", factory=True, host="0.0.0.0", port=8000, reload=True)
