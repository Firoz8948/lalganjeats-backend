-- Restaurant packing charge: optional fee shown on that restaurant's checkout.
-- Customer total += packing; hotel transfer += packing. Admin P/L unchanged.
-- Safe to run more than once.

ALTER TABLE restaurants ADD COLUMN IF NOT EXISTS show_packing_charge BOOLEAN DEFAULT FALSE;
ALTER TABLE restaurants ADD COLUMN IF NOT EXISTS packing_charge NUMERIC(10,2) DEFAULT 0;
ALTER TABLE orders ADD COLUMN IF NOT EXISTS packing_charge NUMERIC(10,2) DEFAULT 0;
