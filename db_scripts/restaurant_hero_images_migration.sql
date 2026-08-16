-- Separate mobile/desktop restaurant menu heroes.
-- Safe to run more than once.

ALTER TABLE restaurants
  ADD COLUMN IF NOT EXISTS banner_mobile_url TEXT;

-- Existing single banner becomes the desktop hero by default.
UPDATE restaurants
SET banner_mobile_url = banner_url
WHERE banner_mobile_url IS NULL
  AND banner_url IS NOT NULL;
