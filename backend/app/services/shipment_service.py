"""Dispatch and delivery.

The delivery step is the project's SECOND ACID transaction. It must
atomically:
    1. reduce qty_on_hand      (stock physically leaves)
    2. reduce qty_reserved     (the reservation is discharged)
    3. mark the allocation DELIVERED
    4. update the parent request status

Doing 1 without 2 would leave a phantom reservation forever; doing 2
without 1 would make delivered stock reappear as available.
"""
import logging

from sqlalchemy import text
from sqlalchemy.orm import Session

logger = logging.getLogger("medsupply.shipment")


class ShipmentError(Exception):
    """Business-rule failure. Triggers rollback."""


def create_shipment(db: Session, allocation_id: int,
                    vehicle_number: str | None = None,
                    driver_name: str | None = None,
                    expected_at=None,
                    actor_user_id: int | None = None) -> dict:
    db.execute(text("SET LOCAL lock_timeout = '5000ms'"))

    alloc = db.execute(text("""
        SELECT allocation_id, request_id, batch_id, qty_allocated,
               allocation_status
        FROM allocation WHERE allocation_id = :aid FOR UPDATE
    """), {"aid": allocation_id}).mappings().one_or_none()

    if alloc is None:
        raise ShipmentError(f"Allocation {allocation_id} not found")
    if alloc["allocation_status"] != "RESERVED":
        raise ShipmentError(
            f"Allocation is {alloc['allocation_status']}; "
            "only RESERVED allocations can be shipped")

    existing = db.execute(text(
        "SELECT shipment_id FROM shipment WHERE allocation_id = :aid"
    ), {"aid": allocation_id}).scalar_one_or_none()
    if existing:
        raise ShipmentError(
            f"Allocation {allocation_id} already has shipment {existing}")

    shipment_id = db.execute(text("""
        INSERT INTO shipment (allocation_id, vehicle_number, driver_name,
                              expected_at, delivery_status)
        VALUES (:aid, :veh, :drv, :exp, 'PREPARING')
        RETURNING shipment_id
    """), {"aid": allocation_id, "veh": vehicle_number,
           "drv": driver_name, "exp": expected_at}).scalar_one()

    db.execute(text("""
        INSERT INTO allocation_event (request_id, batch_id, event_type,
                                      txn_note, actor_user_id, actor_type)
        VALUES (:rid, :bid, 'SHIPMENT_CREATED',
                'Shipment prepared for dispatch', :uid,
                CASE WHEN :uid IS NULL THEN 'SYSTEM' ELSE 'USER' END)
    """), {"rid": alloc["request_id"], "bid": alloc["batch_id"],
           "uid": actor_user_id})

    return {"shipment_id": shipment_id, "allocation_id": allocation_id,
            "delivery_status": "PREPARING",
            "message": f"Shipment {shipment_id} created"}


def dispatch_shipment(db: Session, shipment_id: int,
                      actor_user_id: int | None = None) -> dict:
    """Mark in transit. No inventory movement — stock is still physically
    in the warehouse until delivery is confirmed."""
    db.execute(text("SET LOCAL lock_timeout = '5000ms'"))

    ship = db.execute(text("""
        SELECT s.shipment_id, s.allocation_id, s.delivery_status,
               a.request_id, a.batch_id
        FROM shipment s
        JOIN allocation a ON a.allocation_id = s.allocation_id
        WHERE s.shipment_id = :sid
        FOR UPDATE OF s
    """), {"sid": shipment_id}).mappings().one_or_none()

    if ship is None:
        raise ShipmentError(f"Shipment {shipment_id} not found")
    if ship["delivery_status"] != "PREPARING":
        raise ShipmentError(
            f"Shipment is {ship['delivery_status']}; only PREPARING "
            "shipments can be dispatched")

    db.execute(text("""
        UPDATE shipment
        SET delivery_status = 'IN_TRANSIT', dispatched_at = NOW()
        WHERE shipment_id = :sid
    """), {"sid": shipment_id})

    db.execute(text("""
        UPDATE allocation SET allocation_status = 'DISPATCHED'
        WHERE allocation_id = :aid
    """), {"aid": ship["allocation_id"]})

    db.execute(text("""
        UPDATE emergency_request SET request_status = 'DISPATCHED'
        WHERE request_id = :rid AND request_status IN ('ALLOCATED', 'PARTIAL')
    """), {"rid": ship["request_id"]})

    db.execute(text("""
        INSERT INTO allocation_event (request_id, batch_id, event_type,
                                      txn_note, actor_user_id, actor_type)
        VALUES (:rid, :bid, 'DISPATCHED',
                'In transit; inventory not yet decremented', :uid,
                CASE WHEN :uid IS NULL THEN 'SYSTEM' ELSE 'USER' END)
    """), {"rid": ship["request_id"], "bid": ship["batch_id"],
           "uid": actor_user_id})

    return {"shipment_id": shipment_id, "delivery_status": "IN_TRANSIT",
            "message": "Shipment dispatched"}


def deliver_shipment(db: Session, shipment_id: int,
                     actor_user_id: int | None = None) -> dict:
    """Confirm delivery. THIS is where physical stock finally moves."""
    db.execute(text("SET LOCAL lock_timeout = '5000ms'"))

    ship = db.execute(text("""
        SELECT s.shipment_id, s.allocation_id, s.delivery_status,
               a.request_id, a.batch_id, a.qty_allocated
        FROM shipment s
        JOIN allocation a ON a.allocation_id = s.allocation_id
        WHERE s.shipment_id = :sid
        FOR UPDATE OF s
    """), {"sid": shipment_id}).mappings().one_or_none()

    if ship is None:
        raise ShipmentError(f"Shipment {shipment_id} not found")
    if ship["delivery_status"] != "IN_TRANSIT":
        raise ShipmentError(
            f"Shipment is {ship['delivery_status']}; only IN_TRANSIT "
            "shipments can be delivered")

    qty = ship["qty_allocated"]

    # Lock the batch before touching quantities.
    batch = db.execute(text("""
        SELECT batch_id, qty_on_hand, qty_reserved
        FROM inventory_batch WHERE batch_id = :bid FOR UPDATE
    """), {"bid": ship["batch_id"]}).mappings().one()

    if batch["qty_reserved"] < qty or batch["qty_on_hand"] < qty:
        raise ShipmentError(
            f"Inventory inconsistent for batch {ship['batch_id']}: "
            f"on_hand={batch['qty_on_hand']}, reserved={batch['qty_reserved']}, "
            f"needed={qty}")

    # Both columns decrement together. This is the whole point.
    db.execute(text("""
        UPDATE inventory_batch
        SET qty_on_hand  = qty_on_hand  - :qty,
            qty_reserved = qty_reserved - :qty
        WHERE batch_id = :bid
    """), {"qty": qty, "bid": ship["batch_id"]})

    db.execute(text("""
        UPDATE shipment
        SET delivery_status = 'DELIVERED', delivered_at = NOW()
        WHERE shipment_id = :sid
    """), {"sid": shipment_id})

    db.execute(text("""
        UPDATE allocation SET allocation_status = 'DELIVERED'
        WHERE allocation_id = :aid
    """), {"aid": ship["allocation_id"]})

    # The request is DELIVERED only when no allocation is still outstanding.
    db.execute(text("""
        UPDATE emergency_request r
        SET request_status = 'DELIVERED'
        WHERE r.request_id = :rid
          AND NOT EXISTS (
              SELECT 1 FROM allocation a
              WHERE a.request_id = r.request_id
                AND a.allocation_status IN ('RESERVED', 'DISPATCHED')
          )
    """), {"rid": ship["request_id"]})

    db.execute(text("""
        INSERT INTO allocation_event (request_id, batch_id, event_type,
                                      old_value, new_value, txn_note,
                                      actor_user_id, actor_type)
        VALUES (:rid, :bid, 'DELIVERED', :old, :new,
                'Stock physically removed from warehouse', :uid,
                CASE WHEN :uid IS NULL THEN 'SYSTEM' ELSE 'USER' END)
    """), {"rid": ship["request_id"], "bid": ship["batch_id"],
           "old": f"on_hand={batch['qty_on_hand']},reserved={batch['qty_reserved']}",
           "new": (f"on_hand={batch['qty_on_hand'] - qty},"
                   f"reserved={batch['qty_reserved'] - qty}"),
           "uid": actor_user_id})

    logger.info("Delivered %s units from batch %s", qty, ship["batch_id"])

    return {"shipment_id": shipment_id, "delivery_status": "DELIVERED",
            "qty_delivered": qty, "batch_id": ship["batch_id"],
            "message": f"Delivered {qty} units; inventory decremented"}


def receive_consignment(db: Session, payload: dict,
                        actor_user_id: int | None = None) -> dict:
    """Supplier delivers stock. Creates the batch and its provenance
    record in one transaction."""
    batch_id = db.execute(text("""
        INSERT INTO inventory_batch (warehouse_id, medicine_id, batch_number,
                                     qty_on_hand, qty_reserved, mfg_date,
                                     expiry_date, unit_cost)
        VALUES (:wid, :mid, :bn, :qty, 0, :mfg, :exp, :cost)
        RETURNING batch_id
    """), {"wid": payload["warehouse_id"], "mid": payload["medicine_id"],
           "bn": payload["batch_number"], "qty": payload["qty_supplied"],
           "mfg": payload.get("mfg_date"), "exp": payload["expiry_date"],
           "cost": payload.get("unit_price")}).scalar_one()

    consignment_id = db.execute(text("""
        INSERT INTO supply_consignment (supplier_id, medicine_id, warehouse_id,
                                        batch_id, qty_supplied, supplied_on,
                                        unit_price)
        VALUES (:sid, :mid, :wid, :bid, :qty,
                COALESCE(:son, CURRENT_DATE), :price)
        RETURNING consignment_id
    """), {"sid": payload["supplier_id"], "mid": payload["medicine_id"],
           "wid": payload["warehouse_id"], "bid": batch_id,
           "qty": payload["qty_supplied"], "son": payload.get("supplied_on"),
           "price": payload.get("unit_price")}).scalar_one()

    db.execute(text("""
        INSERT INTO allocation_event (batch_id, event_type, new_value,
                                      txn_note, actor_user_id, actor_type)
        VALUES (:bid, 'STOCK_RECEIVED', :qty,
                'Consignment received from supplier', :uid,
                CASE WHEN :uid IS NULL THEN 'SYSTEM' ELSE 'USER' END)
    """), {"bid": batch_id, "qty": str(payload["qty_supplied"]),
           "uid": actor_user_id})

    return {"consignment_id": consignment_id, "batch_id": batch_id,
            "qty_supplied": payload["qty_supplied"],
            "message": f"Received {payload['qty_supplied']} units into "
                       f"batch {batch_id}"}
