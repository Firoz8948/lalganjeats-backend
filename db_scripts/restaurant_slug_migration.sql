-- Restaurant SEO slugs for public URLs (/restaurants/{slug})
-- Run on EC2:
--   psql "$DATABASE_URL" -f db_scripts/restaurant_slug_migration.sql

ALTER TABLE restaurants
    ADD COLUMN IF NOT EXISTS slug VARCHAR(180);

-- Backfill from name (lowercase, non-alnum -> hyphen)
UPDATE restaurants
SET slug = TRIM(BOTH '-' FROM REGEXP_REPLACE(LOWER(COALESCE(name, '')), '[^a-z0-9]+', '-', 'g'))
WHERE slug IS NULL OR BTRIM(slug) = '';

-- Empty names / empty slugify results
UPDATE restaurants
SET slug = 'restaurant-' || id::text
WHERE slug IS NULL OR BTRIM(slug) = '';

-- Deduplicate collisions: keep lowest id as-is, append -id for others
WITH ranked AS (
    SELECT
        id,
        slug,
        ROW_NUMBER() OVER (PARTITION BY slug ORDER BY id) AS rn
    FROM restaurants
    WHERE slug IS NOT NULL
)
UPDATE restaurants r
SET slug = r.slug || '-' || r.id::text
FROM ranked x
WHERE r.id = x.id
  AND x.rn > 1;

CREATE UNIQUE INDEX IF NOT EXISTS uq_restaurants_slug ON restaurants (slug);

ALTER TABLE restaurants
    ALTER COLUMN slug SET NOT NULL;
