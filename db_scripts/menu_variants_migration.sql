-- Menu item variants (Half / Full / custom sizes)
-- Safe to run more than once.

CREATE TABLE IF NOT EXISTS menu_item_variants (
  id SERIAL PRIMARY KEY,
  menu_item_id INTEGER NOT NULL REFERENCES menu_items(id) ON DELETE CASCADE,
  label VARCHAR(40) NOT NULL,
  price NUMERIC(10, 2) NOT NULL,
  actual_price NUMERIC(10, 2) NOT NULL,
  original_price NUMERIC(10, 2),
  sort_order INTEGER DEFAULT 0,
  is_available BOOLEAN DEFAULT TRUE,
  is_deleted BOOLEAN DEFAULT FALSE,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ,
  CONSTRAINT uq_menu_item_variant_label UNIQUE (menu_item_id, label)
);

CREATE INDEX IF NOT EXISTS idx_menu_item_variants_item
  ON menu_item_variants(menu_item_id);

-- Backfill one Regular variant for existing items that have none
INSERT INTO menu_item_variants (
  menu_item_id, label, price, actual_price, original_price, sort_order, is_available, is_deleted
)
SELECT
  mi.id,
  'Regular',
  mi.price,
  COALESCE(mi.actual_price, mi.price),
  mi.original_price,
  0,
  COALESCE(mi.is_available, TRUE),
  FALSE
FROM menu_items mi
WHERE mi.is_deleted = FALSE
  AND NOT EXISTS (
    SELECT 1 FROM menu_item_variants v
    WHERE v.menu_item_id = mi.id AND v.is_deleted = FALSE
  )
ON CONFLICT (menu_item_id, label) DO NOTHING;

ALTER TABLE order_items
  ADD COLUMN IF NOT EXISTS variant_id INTEGER REFERENCES menu_item_variants(id) ON DELETE SET NULL;

ALTER TABLE order_items
  ADD COLUMN IF NOT EXISTS variant_label VARCHAR(40);

CREATE INDEX IF NOT EXISTS idx_order_items_variant
  ON order_items(variant_id);
