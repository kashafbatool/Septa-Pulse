"""SEPTA Pulse FastAPI application."""

import os
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from src.api.routes.analytics import router as analytics_router
from src.api.routes.vehicles import router as vehicles_router

load_dotenv()

CORS_ORIGINS = os.getenv("CORS_ORIGINS", "*").split(",")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: verify DB connectivity
    from src.database.connection import engine
    from sqlalchemy import text

    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))
    yield
    # Shutdown: nothing to clean up (connection pool handles it)


app = FastAPI(
    title="SEPTA Pulse",
    description="Real-Time Transit Analytics API for SEPTA Philadelphia",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET"],
    allow_headers=["*"],
)

app.include_router(vehicles_router, prefix="/api/vehicles", tags=["vehicles"])
app.include_router(analytics_router, prefix="/api/analytics", tags=["analytics"])

# Serve the static dashboard
dashboard_path = os.path.join(os.path.dirname(__file__), "..", "..", "dashboard")
if os.path.isdir(dashboard_path):
    app.mount("/", StaticFiles(directory=dashboard_path, html=True), name="dashboard")


@app.get("/health", tags=["system"])
def health_check():
    return {"status": "ok", "service": "septa-pulse"}
