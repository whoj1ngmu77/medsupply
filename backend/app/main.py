import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from app.core.exceptions import (integrity_error_handler,
                                 sqlalchemy_error_handler)
from app.db.mongo import mongo_client, mongo_db
from app.db.postgres import engine
from app.routers import (analytics, auth, replenishment, dbms_concurrency,
                         dbms_demo,
                         hospitals, incidents, inventory,
                         nosql_demo,
                         medicines,
                         requests, shipments, suppliers,
                         warehouses)

logging.basicConfig(level=logging.INFO)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # The automatic replenishment loops start here. @app.on_event is
    # ignored by FastAPI whenever a lifespan handler is present, so the
    # scheduler must be started and stopped inside this function.
    from app.services import scheduler as _replen_scheduler
    await _replen_scheduler.start()
    yield
    await _replen_scheduler.stop()
    mongo_client.close()
    engine.dispose()


app = FastAPI(
    title="MedSupply API",
    description="Emergency Medical Supply Management System - BCSE302L",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        o.strip() for o in os.getenv(
            "ALLOWED_ORIGINS",
            "http://localhost:5173,http://localhost:3000"
        ).split(",") if o.strip()
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_exception_handler(IntegrityError, integrity_error_handler)
app.add_exception_handler(SQLAlchemyError, sqlalchemy_error_handler)

app.include_router(auth.router)
app.include_router(hospitals.router)
app.include_router(warehouses.router)
app.include_router(medicines.router)
app.include_router(suppliers.router)
app.include_router(inventory.router)
app.include_router(requests.router)
app.include_router(shipments.router)
app.include_router(dbms_demo.router)
app.include_router(dbms_concurrency.router)
app.include_router(incidents.router)
app.include_router(nosql_demo.router)
app.include_router(analytics.router)
app.include_router(replenishment.router)


@app.get("/")
def root():
    return {"service": "MedSupply API", "version": "1.0.0"}


@app.get("/health")
async def health():
    status = {"api": "ok", "postgres": "down", "mongodb": "down"}

    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        status["postgres"] = "ok"
    except Exception as exc:
        status["postgres"] = f"error: {type(exc).__name__}"

    try:
        await mongo_db.command("ping")
        status["mongodb"] = "ok"
    except Exception as exc:
        status["mongodb"] = f"error: {type(exc).__name__}"

    status["healthy"] = status["postgres"] == "ok" and status["mongodb"] == "ok"
    return status


# ---------------------------------------------------------------------
# Automatic replenishment scheduler
# ---------------------------------------------------------------------
from app.services import scheduler as _replen_scheduler    # noqa: E402


@app.get("/replenishment/scheduler", tags=["Auto Replenishment"])
def replenishment_scheduler_state() -> dict:
    """Proof the scans are running on their own, with no user action."""
    return _replen_scheduler.STATE
