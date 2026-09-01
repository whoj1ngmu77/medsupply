# Functional Dependencies — MedSupply

## The Unnormalized Relation (UNF)

A flat "allocation log" of the kind a hospital might keep in a spreadsheet:

EMERGENCY_SUPPLY_LOG (
request_id, hospital_id, hospital_name, hospital_city,
hospital_bed_capacity, hospital_emergency_level,
medicine_id, medicine_name, category_id, category_name,
manufacturer_id, manufacturer_name, manufacturer_country,
unit, criticality, qty_requested, priority, requested_at,
required_by, request_status,
{ batch_id, batch_number, warehouse_id, warehouse_name,
warehouse_city, warehouse_capacity, qty_on_hand,
expiry_date, qty_allocated, allocated_at },
{ supplier_id, supplier_name, supplied_on }
)


Braces mark repeating groups. One request row holds many batch allocations and many supplier records — this is UNF.

## Functional Dependencies

FD1 request_id -> hospital_id, medicine_id, qty_requested, priority,
requested_at, required_by, request_status

FD2 hospital_id -> hospital_name, hospital_city,
hospital_bed_capacity, hospital_emergency_level

FD3 medicine_id -> medicine_name, category_id, manufacturer_id,
unit, criticality

FD4 category_id -> category_name

FD5 manufacturer_id -> manufacturer_name, manufacturer_country

FD6 batch_id -> warehouse_id, medicine_id, batch_number,
qty_on_hand, qty_reserved, expiry_date

FD7 warehouse_id -> warehouse_name, warehouse_city, warehouse_capacity

FD8 (warehouse_id, batch_number) -> batch_id

FD9 (request_id, batch_id) -> qty_allocated, allocated_at,
allocation_status

FD10 supplier_id -> supplier_name

FD11 consignment_id -> supplier_id, medicine_id, warehouse_id,
batch_id, qty_supplied, supplied_on


FD8 is the weak-entity identification dependency — it justifies the UNIQUE(warehouse_id, batch_number) constraint on INVENTORY_BATCH.

## Closure Computation

To verify `(request_id, batch_id)` is the candidate key of the 1NF relation:

{request_id, batch_id}+
= {request_id, batch_id}

FD1: hospital_id, medicine_id, qty_requested, priority,
requested_at, required_by, request_status
FD2: hospital_name, hospital_city, hospital_bed_capacity,
hospital_emergency_level
FD3: medicine_name, category_id, manufacturer_id, unit, criticality
FD4: category_name
FD5: manufacturer_name, manufacturer_country
FD6: warehouse_id, batch_number, qty_on_hand, qty_reserved,
expiry_date
FD7: warehouse_name, warehouse_city, warehouse_capacity
FD9: qty_allocated, allocated_at, allocation_status
= all attributes of R1NF

Neither `{request_id}+` nor `{batch_id}+` yields all attributes, so the key is minimal.
