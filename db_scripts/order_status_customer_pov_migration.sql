-- Remap legacy order statuses → customer POV statuses
-- pending | accepted | ready | picked_up | delivered | cancelled
--
-- IMPORTANT: drop CHECK before UPDATE (new values like "ready" are not in the old CHECK).
-- psql "$DATABASE_URL" -f db_scripts/order_status_customer_pov_migration.sql

ALTER TABLE orders DROP CONSTRAINT IF EXISTS orders_status_check;

UPDATE orders SET status = 'accepted'
WHERE status IN ('confirmed', 'preparing');

UPDATE orders SET status = 'ready'
WHERE status IN ('ready_for_pickup', 'assigned');

UPDATE orders SET status = 'picked_up'
WHERE status = 'on_the_way';

ALTER TABLE orders
    ADD CONSTRAINT orders_status_check
    CHECK (
        status IN (
            'pending',
            'accepted',
            'ready',
            'picked_up',
            'delivered',
            'cancelled'
        )
    );
