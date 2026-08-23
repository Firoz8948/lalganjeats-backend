-- Order status + payment method alignment for partner / delivery flow
-- psql "$DATABASE_URL" -f db_scripts/order_status_flow_migration.sql
--
-- Adds:
--   status: assigned (delivery partner accepted offer)
--   payment_method: online, split (doorstep collection)

DO $$
DECLARE
  r RECORD;
BEGIN
  FOR r IN
    SELECT con.conname
    FROM pg_constraint con
    JOIN pg_class rel ON rel.oid = con.conrelid
    JOIN pg_namespace nsp ON nsp.oid = rel.relnamespace
    WHERE rel.relname = 'orders'
      AND nsp.nspname = 'public'
      AND con.contype = 'c'
      AND pg_get_constraintdef(con.oid) ILIKE '%status%'
  LOOP
    EXECUTE format('ALTER TABLE orders DROP CONSTRAINT %I', r.conname);
  END LOOP;

  FOR r IN
    SELECT con.conname
    FROM pg_constraint con
    JOIN pg_class rel ON rel.oid = con.conrelid
    JOIN pg_namespace nsp ON nsp.oid = rel.relnamespace
    WHERE rel.relname = 'orders'
      AND nsp.nspname = 'public'
      AND con.contype = 'c'
      AND pg_get_constraintdef(con.oid) ILIKE '%payment_method%'
  LOOP
    EXECUTE format('ALTER TABLE orders DROP CONSTRAINT %I', r.conname);
  END LOOP;
END $$;

ALTER TABLE orders
  ADD CONSTRAINT orders_status_check CHECK (
    status IN (
      'pending',
      'confirmed',
      'preparing',
      'ready_for_pickup',
      'assigned',
      'picked_up',
      'on_the_way',
      'delivered',
      'cancelled'
    )
  );

ALTER TABLE orders
  ADD CONSTRAINT orders_payment_method_check CHECK (
    payment_method IN ('cash', 'upi', 'online', 'split')
  );
