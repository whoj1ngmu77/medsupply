import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from app.core.exceptions import (integrity_error_handler,
                                 sqlalchemy_error_handler)
from app.db.mongo import mongo_client, mongo_db
from app.db.postgres import engine
from app.routers import (auth, hospitals, inventory, medicines,
                         requests, suppliers, warehouses)

logging.basicConfig(level=logging.INFO)


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    mongo_client.close()
    engine.dispose()


app = FastAPI(
    title="MedSupply API",
    description="Emergency Medical Supply Management System - BCSE302L",
    version="0.4.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
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


@app.get("/")
def root():
    return {"service": "MedSupply API", "version": "0.4.0"}


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
