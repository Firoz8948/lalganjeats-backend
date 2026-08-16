-- Curated subcategory row shown below home banners.
-- Safe to run more than once.

ALTER TABLE catalog_subcategories
  ADD COLUMN IF NOT EXISTS is_featured BOOLEAN NOT NULL DEFAULT FALSE;

CREATE INDEX IF NOT EXISTS idx_catalog_subcategories_featured
  ON catalog_subcategories (category_id, sort_order)
  WHERE is_active = TRUE AND is_featured = TRUE;
