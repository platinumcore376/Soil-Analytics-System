"""FastAPI application entrypoint (Phase 1 ingestion + Phase 2 analysis)."""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import init_db
from app.routers import analysis, farms, images, soil_records, auth, tts, advisory_bridge


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Verify the PostgreSQL connection and ensure tables exist.
    init_db()
    yield


app = FastAPI(
    title="Soil Health Assessment API",
    description=(
        "Phase 1 — Image & Soil Test Data Ingestion Pipeline · "
        "Phase 2 — ML Soil Classification & Analysis Engine"
    ),
    version="0.2.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(farms.router)
app.include_router(images.router)
app.include_router(soil_records.router)
app.include_router(analysis.router)
app.include_router(tts.router)
app.include_router(advisory_bridge.router)


@app.get("/", tags=["meta"])
def root() -> dict:
    return {
        "service": "Soil Health Assessment API",
        "phase": "1 - data ingestion, 2 - analysis engine",
        "docs": "/docs",
        "health": "/health",
    }


@app.get("/health", tags=["meta"])
def health() -> dict:
    return {"status": "ok", "phase": "1 - data ingestion, 2 - analysis engine"}