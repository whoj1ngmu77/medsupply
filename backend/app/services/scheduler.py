"""Background scheduler for automatic replenishment.

This is what makes the feature AUTOMATIC rather than button-driven. No
user action triggers a scan; the loop runs for as long as the API is up.

Two independent loops:
    scan loop     -- looks for policies below threshold, raises orders
    gateway loop  -- advances simulated orders through their lifecycle

Both use short intervals so the behaviour is observable during a demo.
Production values would be minutes or hours, set via environment:
    REPLENISH_SCAN_INTERVAL     seconds between scans      (default 120)
    REPLENISH_GATEWAY_INTERVAL  seconds between advances   (default 15)
    REPLENISH_SCHEDULER         'off' disables both loops

SQLAlchemy sessions here are synchronous, so each cycle runs in a worker
thread via asyncio.to_thread and never blocks the event loop.
"""
import asyncio
import logging
import os
from datetime import datetime, timezone

from app.db.postgres import SessionLocal
from app.services import replenishment_service as rs
from app.services import supplier_gateway as gw

logger = logging.getLogger("medsupply.scheduler")

SCAN_INTERVAL = int(os.getenv("REPLENISH_SCAN_INTERVAL", "120"))
GATEWAY_INTERVAL = int(os.getenv("REPLENISH_GATEWAY_INTERVAL", "15"))
ENABLED = os.getenv("REPLENISH_SCHEDULER", "on").lower() != "off"

STATE = {
    "enabled": ENABLED,
    "scan_interval": SCAN_INTERVAL,
    "gateway_interval": GATEWAY_INTERVAL,
    "last_scan_at": None,
    "last_scan_orders": 0,
    "total_auto_orders": 0,
    "last_gateway_at": None,
    "last_gateway_advanced": 0,
    "errors": 0,
}

_tasks: list[asyncio.Task] = []


def _scan_once() -> int:
    db = SessionLocal()
    try:
        result = rs.run_scan(db, actor_user_id=None, limit=50,
                             triggered_by="AUTO")
        db.commit()
        return result["orders_created"]
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def _advance_once() -> int:
    db = SessionLocal()
    try:
        result = gw.advance_due_orders(db, limit=100)
        db.commit()
        return result["advanced"]
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


async def _scan_loop() -> None:
    await asyncio.sleep(10)          # let the app finish starting
    while True:
        try:
            n = await asyncio.to_thread(_scan_once)
            STATE["last_scan_at"] = datetime.now(timezone.utc).isoformat()
            STATE["last_scan_orders"] = n
            STATE["total_auto_orders"] += n
            if n:
                logger.info("auto scan raised %d purchase order(s)", n)
        except asyncio.CancelledError:
            raise
        except Exception:
            STATE["errors"] += 1
            logger.exception("auto scan failed")
        await asyncio.sleep(STATE["scan_interval"])


async def _gateway_loop() -> None:
    await asyncio.sleep(15)
    while True:
        try:
            n = await asyncio.to_thread(_advance_once)
            STATE["last_gateway_at"] = datetime.now(timezone.utc).isoformat()
            STATE["last_gateway_advanced"] = n
        except asyncio.CancelledError:
            raise
        except Exception:
            STATE["errors"] += 1
            logger.exception("gateway advance failed")
        await asyncio.sleep(STATE["gateway_interval"])


async def start() -> None:
    """Must be awaited from an async startup hook.

    Creating tasks from a SYNC startup handler does not work: FastAPI
    runs those in a threadpool where there is no running event loop, so
    the tasks are created against a loop that never runs them.
    """
    if not STATE["enabled"]:
        logger.info("replenishment scheduler disabled (REPLENISH_SCHEDULER=off)")
        return
    _tasks.append(asyncio.create_task(_scan_loop()))
    _tasks.append(asyncio.create_task(_gateway_loop()))
    logger.info("replenishment scheduler started (scan %ds, gateway %ds)",
                STATE["scan_interval"], STATE["gateway_interval"])


async def stop() -> None:
    for t in _tasks:
        t.cancel()
    for t in _tasks:
        try:
            await t
        except (asyncio.CancelledError, Exception):       # noqa: BLE001
            pass
    _tasks.clear()
    logger.info("replenishment scheduler stopped")
