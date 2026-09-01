-- Isolated tables for concurrency/deadlock demonstrations.
-- Never touched by production operations.

DROP TABLE IF EXISTS demo_inventory CASCADE;
DROP TABLE IF EXISTS demo_account CASCADE;

CREATE TABLE demo_inventory (
    demo_id          SERIAL PRIMARY KEY,
    label            VARCHAR(60) NOT NULL,
    qty_on_hand      INTEGER NOT NULL CHECK (qty_on_hand >= 0),
    qty_reserved     INTEGER NOT NULL DEFAULT 0 CHECK (qty_reserved >= 0),
    CONSTRAINT chk_demo_reserved CHECK (qty_reserved <= qty_on_hand)
);

CREATE TABLE demo_account (
    account_id       SERIAL PRIMARY KEY,
    owner            VARCHAR(60) NOT NULL,
    balance          NUMERIC(12,2) NOT NULL CHECK (balance >= 0)
);

INSERT INTO demo_inventory (label, qty_on_hand, qty_reserved) VALUES
    ('Paracetamol-DEMO', 100, 0),
    ('Insulin-DEMO',     100, 0);

INSERT INTO demo_account (owner, balance) VALUES
    ('Warehouse-A', 5000.00),
    ('Warehouse-B', 5000.00);
