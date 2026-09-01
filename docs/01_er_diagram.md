# ER / EER Model — MedSupply

## Entity Types

**Strong entities:** Hospital, Warehouse, Medicine, MedicineCategory, Manufacturer, Supplier, UserAccount, EmergencyRequest

**Weak entity:** InventoryBatch — identified by `batch_number` only within a warehouse. Partial key: `batch_number`. Full identification: `(warehouse_id, batch_number)`. Implemented with surrogate `batch_id` plus a UNIQUE constraint preserving weak-entity semantics.

**Associative entities:**
- Allocation — resolves M:N between EmergencyRequest and InventoryBatch, carrying `qty_allocated`
- SupplyConsignment — resolves M:N between Supplier and Medicine

**Dependent entities:** Shipment (1:1 with Allocation), AllocationEvent (audit log)

## EER Extensions

**Specialization:** UserAccount specializes into HospitalStaff, WarehouseStaff, SupplierUser, EmergencyCoordinator, Admin.

- Disjoint (d): a user holds exactly one role
- Total: every user has a role

**Mapping choice:** single table with `role` discriminator plus three nullable FKs (`hospital_id`, `warehouse_id`, `supplier_id`), constrained so exactly one is non-null for role-bound users.

Rejected alternative: table-per-subclass. Every authentication query would need a 5-way UNION, and subclasses differ by only one attribute each.

**Union type (category):** AllocationEvent.actor may be a UserAccount or the automated allocation engine. Modelled as nullable `actor_user_id` + `actor_type` enum, since PostgreSQL has no native category support.

## ER Diagram

```mermaid
erDiagram
    MANUFACTURER ||--o{ MEDICINE : manufactures
    MEDICINE_CATEGORY ||--o{ MEDICINE : classifies
    MEDICINE ||--o{ INVENTORY_BATCH : stocked_as
    WAREHOUSE ||--o{ INVENTORY_BATCH : stores
    HOSPITAL ||--o{ EMERGENCY_REQUEST : raises
    MEDICINE ||--o{ EMERGENCY_REQUEST : requested_in
    EMERGENCY_REQUEST ||--o{ ALLOCATION : fulfilled_by
    INVENTORY_BATCH ||--o{ ALLOCATION : sourced_from
    ALLOCATION ||--o| SHIPMENT : dispatched_as
    SUPPLIER ||--o{ SUPPLY_CONSIGNMENT : supplies
    MEDICINE ||--o{ SUPPLY_CONSIGNMENT : supplied_as
    WAREHOUSE ||--o{ SUPPLY_CONSIGNMENT : received_at
    SUPPLY_CONSIGNMENT ||--|| INVENTORY_BATCH : creates
    USER_ACCOUNT ||--o{ EMERGENCY_REQUEST : raised_by
    USER_ACCOUNT ||--o{ ALLOCATION : allocated_by
    HOSPITAL ||--o{ USER_ACCOUNT : employs
    WAREHOUSE ||--o{ USER_ACCOUNT : employs
    SUPPLIER ||--o{ USER_ACCOUNT : employs
    EMERGENCY_REQUEST ||--o{ ALLOCATION_EVENT : logged_in

    HOSPITAL {
        int hospital_id PK
        string name
        string reg_number UK
        string city
        int bed_capacity
        string emergency_level
    }
    WAREHOUSE {
        int warehouse_id PK
        string name
        string city
        int storage_capacity
    }
    MEDICINE {
        int medicine_id PK
        string name
        int category_id FK
        int manufacturer_id FK
        string unit
        string criticality
    }
    INVENTORY_BATCH {
        int batch_id PK
        int warehouse_id FK
        int medicine_id FK
        string batch_number
        int qty_on_hand
        int qty_reserved
        date expiry_date
    }
    EMERGENCY_REQUEST {
        int request_id PK
        int hospital_id FK
        int medicine_id FK
        int qty_requested
        string priority
        string status
        timestamp requested_at
    }
    ALLOCATION {
        int allocation_id PK
        int request_id FK
        int batch_id FK
        int qty_allocated
        timestamp allocated_at
    }
```

## Cardinality and Participation

| Relationship | Cardinality | Participation |
|---|---|---|
| Hospital-EmergencyRequest | 1:N | Hospital partial, Request total |
| Medicine-InventoryBatch | 1:N | Medicine partial, Batch total |
| Warehouse-InventoryBatch | 1:N | Warehouse partial, Batch total |
| EmergencyRequest-InventoryBatch | M:N via Allocation | both partial |
| Allocation-Shipment | 1:1 | Allocation partial, Shipment total |
| Supplier-Medicine | M:N via SupplyConsignment | both partial |

**Why Allocation is M:N, not 1:N:** a request for 500 units may draw 200 from a batch expiring next month and 300 from another. Modelling it 1:N would force partial fulfilment into a single batch and eliminate the FEFO logic, multi-row locking, and most of the concurrency interest.
