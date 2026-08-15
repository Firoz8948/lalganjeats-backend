-- Business category and menu subcategory catalog
-- Safe to run more than once.

CREATE TABLE IF NOT EXISTS catalog_categories (
  id SERIAL PRIMARY KEY,
  name VARCHAR(100) NOT NULL UNIQUE,
  slug VARCHAR(100) NOT NULL UNIQUE,
  sort_order INTEGER DEFAULT 0,
  is_active BOOLEAN DEFAULT TRUE,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS catalog_subcategories (
  id SERIAL PRIMARY KEY,
  category_id INTEGER NOT NULL REFERENCES catalog_categories(id) ON DELETE CASCADE,
  name VARCHAR(120) NOT NULL,
  slug VARCHAR(120) NOT NULL,
  sort_order INTEGER DEFAULT 0,
  is_active BOOLEAN DEFAULT TRUE,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  CONSTRAINT uq_catalog_subcategory_slug UNIQUE (category_id, slug)
);

INSERT INTO catalog_categories (name, slug, sort_order, is_active) VALUES
  ('Restaurant', 'restaurant', 1, TRUE),
  ('Grocery', 'grocery', 2, TRUE)
ON CONFLICT (slug) DO NOTHING;

INSERT INTO catalog_subcategories (category_id, name, slug, sort_order, is_active) VALUES
  ((SELECT id FROM catalog_categories WHERE slug = 'restaurant'), 'Fast Food', 'fast-food', 1, TRUE),
  ((SELECT id FROM catalog_categories WHERE slug = 'restaurant'), 'Burgers', 'burgers', 2, TRUE),
  ((SELECT id FROM catalog_categories WHERE slug = 'restaurant'), 'Pizza', 'pizza', 3, TRUE),
  ((SELECT id FROM catalog_categories WHERE slug = 'restaurant'), 'Sandwiches', 'sandwiches', 4, TRUE),
  ((SELECT id FROM catalog_categories WHERE slug = 'restaurant'), 'Wraps & Rolls', 'wraps-and-rolls', 5, TRUE),
  ((SELECT id FROM catalog_categories WHERE slug = 'restaurant'), 'Momos', 'momos', 6, TRUE),
  ((SELECT id FROM catalog_categories WHERE slug = 'restaurant'), 'Pasta', 'pasta', 7, TRUE),
  ((SELECT id FROM catalog_categories WHERE slug = 'restaurant'), 'Noodles', 'noodles', 8, TRUE),
  ((SELECT id FROM catalog_categories WHERE slug = 'restaurant'), 'Chowmein', 'chowmein', 9, TRUE),
  ((SELECT id FROM catalog_categories WHERE slug = 'restaurant'), 'Manchurian', 'manchurian', 10, TRUE),
  ((SELECT id FROM catalog_categories WHERE slug = 'restaurant'), 'Spring Rolls', 'spring-rolls', 11, TRUE),
  ((SELECT id FROM catalog_categories WHERE slug = 'restaurant'), 'French Fries', 'french-fries', 12, TRUE),
  ((SELECT id FROM catalog_categories WHERE slug = 'restaurant'), 'Snacks', 'snacks', 13, TRUE),
  ((SELECT id FROM catalog_categories WHERE slug = 'restaurant'), 'Samosa', 'samosa', 14, TRUE),
  ((SELECT id FROM catalog_categories WHERE slug = 'restaurant'), 'Kachori', 'kachori', 15, TRUE),
  ((SELECT id FROM catalog_categories WHERE slug = 'restaurant'), 'Pakora', 'pakora', 16, TRUE),
  ((SELECT id FROM catalog_categories WHERE slug = 'restaurant'), 'Chaat', 'chaat', 17, TRUE),
  ((SELECT id FROM catalog_categories WHERE slug = 'restaurant'), 'Golgappa / Pani Puri', 'golgappa-pani-puri', 18, TRUE),
  ((SELECT id FROM catalog_categories WHERE slug = 'restaurant'), 'Aloo Tikki', 'aloo-tikki', 19, TRUE),
  ((SELECT id FROM catalog_categories WHERE slug = 'restaurant'), 'Dahi Bhalla', 'dahi-bhalla', 20, TRUE),
  ((SELECT id FROM catalog_categories WHERE slug = 'restaurant'), 'Pav Bhaji', 'pav-bhaji', 21, TRUE),
  ((SELECT id FROM catalog_categories WHERE slug = 'restaurant'), 'Vada Pav', 'vada-pav', 22, TRUE),
  ((SELECT id FROM catalog_categories WHERE slug = 'restaurant'), 'Dosa', 'dosa', 23, TRUE),
  ((SELECT id FROM catalog_categories WHERE slug = 'restaurant'), 'Idli', 'idli', 24, TRUE),
  ((SELECT id FROM catalog_categories WHERE slug = 'restaurant'), 'Uttapam', 'uttapam', 25, TRUE),
  ((SELECT id FROM catalog_categories WHERE slug = 'restaurant'), 'South Indian', 'south-indian', 26, TRUE),
  ((SELECT id FROM catalog_categories WHERE slug = 'restaurant'), 'North Indian', 'north-indian', 27, TRUE),
  ((SELECT id FROM catalog_categories WHERE slug = 'restaurant'), 'Thali', 'thali', 28, TRUE),
  ((SELECT id FROM catalog_categories WHERE slug = 'restaurant'), 'Biryani', 'biryani', 29, TRUE),
  ((SELECT id FROM catalog_categories WHERE slug = 'restaurant'), 'Pulao', 'pulao', 30, TRUE),
  ((SELECT id FROM catalog_categories WHERE slug = 'restaurant'), 'Rice', 'rice', 31, TRUE),
  ((SELECT id FROM catalog_categories WHERE slug = 'restaurant'), 'Fried Rice', 'fried-rice', 32, TRUE),
  ((SELECT id FROM catalog_categories WHERE slug = 'restaurant'), 'Dal', 'dal', 33, TRUE),
  ((SELECT id FROM catalog_categories WHERE slug = 'restaurant'), 'Roti & Naan', 'roti-and-naan', 34, TRUE),
  ((SELECT id FROM catalog_categories WHERE slug = 'restaurant'), 'Paratha', 'paratha', 35, TRUE),
  ((SELECT id FROM catalog_categories WHERE slug = 'restaurant'), 'Paneer Dishes', 'paneer-dishes', 36, TRUE),
  ((SELECT id FROM catalog_categories WHERE slug = 'restaurant'), 'Chicken Dishes', 'chicken-dishes', 37, TRUE),
  ((SELECT id FROM catalog_categories WHERE slug = 'restaurant'), 'Mutton Dishes', 'mutton-dishes', 38, TRUE),
  ((SELECT id FROM catalog_categories WHERE slug = 'restaurant'), 'Fish & Seafood', 'fish-and-seafood', 39, TRUE),
  ((SELECT id FROM catalog_categories WHERE slug = 'restaurant'), 'Tandoori', 'tandoori', 40, TRUE),
  ((SELECT id FROM catalog_categories WHERE slug = 'restaurant'), 'Kebab', 'kebab', 41, TRUE),
  ((SELECT id FROM catalog_categories WHERE slug = 'restaurant'), 'Tikka', 'tikka', 42, TRUE),
  ((SELECT id FROM catalog_categories WHERE slug = 'restaurant'), 'Korma', 'korma', 43, TRUE),
  ((SELECT id FROM catalog_categories WHERE slug = 'restaurant'), 'Curry', 'curry', 44, TRUE),
  ((SELECT id FROM catalog_categories WHERE slug = 'restaurant'), 'Chinese', 'chinese', 45, TRUE),
  ((SELECT id FROM catalog_categories WHERE slug = 'restaurant'), 'Indian Chinese', 'indian-chinese', 46, TRUE),
  ((SELECT id FROM catalog_categories WHERE slug = 'restaurant'), 'Mughlai', 'mughlai', 47, TRUE),
  ((SELECT id FROM catalog_categories WHERE slug = 'restaurant'), 'Punjabi', 'punjabi', 48, TRUE),
  ((SELECT id FROM catalog_categories WHERE slug = 'restaurant'), 'Awadhi', 'awadhi', 49, TRUE),
  ((SELECT id FROM catalog_categories WHERE slug = 'restaurant'), 'Street Food', 'street-food', 50, TRUE),
  ((SELECT id FROM catalog_categories WHERE slug = 'restaurant'), 'Bakery', 'bakery', 51, TRUE),
  ((SELECT id FROM catalog_categories WHERE slug = 'restaurant'), 'Cakes', 'cakes', 52, TRUE),
  ((SELECT id FROM catalog_categories WHERE slug = 'restaurant'), 'Pastries', 'pastries', 53, TRUE),
  ((SELECT id FROM catalog_categories WHERE slug = 'restaurant'), 'Donuts', 'donuts', 54, TRUE),
  ((SELECT id FROM catalog_categories WHERE slug = 'restaurant'), 'Cookies', 'cookies', 55, TRUE),
  ((SELECT id FROM catalog_categories WHERE slug = 'restaurant'), 'Ice Cream', 'ice-cream', 56, TRUE),
  ((SELECT id FROM catalog_categories WHERE slug = 'restaurant'), 'Kulfi', 'kulfi', 57, TRUE),
  ((SELECT id FROM catalog_categories WHERE slug = 'restaurant'), 'Desserts', 'desserts', 58, TRUE),
  ((SELECT id FROM catalog_categories WHERE slug = 'restaurant'), 'Mithai / Sweets', 'mithai-sweets', 59, TRUE),
  ((SELECT id FROM catalog_categories WHERE slug = 'restaurant'), 'Gulab Jamun', 'gulab-jamun', 60, TRUE),
  ((SELECT id FROM catalog_categories WHERE slug = 'restaurant'), 'Jalebi', 'jalebi', 61, TRUE),
  ((SELECT id FROM catalog_categories WHERE slug = 'restaurant'), 'Rasmalai', 'rasmalai', 62, TRUE),
  ((SELECT id FROM catalog_categories WHERE slug = 'restaurant'), 'Halwa', 'halwa', 63, TRUE),
  ((SELECT id FROM catalog_categories WHERE slug = 'restaurant'), 'Fruit Desserts', 'fruit-desserts', 64, TRUE),
  ((SELECT id FROM catalog_categories WHERE slug = 'restaurant'), 'Lassi', 'lassi', 65, TRUE),
  ((SELECT id FROM catalog_categories WHERE slug = 'restaurant'), 'Milkshakes', 'milkshakes', 66, TRUE),
  ((SELECT id FROM catalog_categories WHERE slug = 'restaurant'), 'Smoothies', 'smoothies', 67, TRUE),
  ((SELECT id FROM catalog_categories WHERE slug = 'restaurant'), 'Fresh Juice', 'fresh-juice', 68, TRUE),
  ((SELECT id FROM catalog_categories WHERE slug = 'restaurant'), 'Fruit Juice', 'fruit-juice', 69, TRUE),
  ((SELECT id FROM catalog_categories WHERE slug = 'restaurant'), 'Mocktails', 'mocktails', 70, TRUE),
  ((SELECT id FROM catalog_categories WHERE slug = 'restaurant'), 'Cold Drinks', 'cold-drinks', 71, TRUE),
  ((SELECT id FROM catalog_categories WHERE slug = 'restaurant'), 'Soft Drinks', 'soft-drinks', 72, TRUE),
  ((SELECT id FROM catalog_categories WHERE slug = 'restaurant'), 'Soda', 'soda', 73, TRUE),
  ((SELECT id FROM catalog_categories WHERE slug = 'restaurant'), 'Lemonade', 'lemonade', 74, TRUE),
  ((SELECT id FROM catalog_categories WHERE slug = 'restaurant'), 'Shikanji', 'shikanji', 75, TRUE),
  ((SELECT id FROM catalog_categories WHERE slug = 'restaurant'), 'Tea', 'tea', 76, TRUE),
  ((SELECT id FROM catalog_categories WHERE slug = 'restaurant'), 'Coffee', 'coffee', 77, TRUE),
  ((SELECT id FROM catalog_categories WHERE slug = 'restaurant'), 'Cold Coffee', 'cold-coffee', 78, TRUE),
  ((SELECT id FROM catalog_categories WHERE slug = 'restaurant'), 'Hot Beverages', 'hot-beverages', 79, TRUE),
  ((SELECT id FROM catalog_categories WHERE slug = 'restaurant'), 'Packaged Beverages', 'packaged-beverages', 80, TRUE),
  ((SELECT id FROM catalog_categories WHERE slug = 'restaurant'), 'Beverages', 'beverages', 81, TRUE),
  ((SELECT id FROM catalog_categories WHERE slug = 'restaurant'), 'Combos', 'combos', 82, TRUE),
  ((SELECT id FROM catalog_categories WHERE slug = 'restaurant'), 'Meal Combos', 'meal-combos', 83, TRUE),
  ((SELECT id FROM catalog_categories WHERE slug = 'restaurant'), 'Family Combos', 'family-combos', 84, TRUE),
  ((SELECT id FROM catalog_categories WHERE slug = 'restaurant'), 'Party Combos', 'party-combos', 85, TRUE),
  ((SELECT id FROM catalog_categories WHERE slug = 'restaurant'), 'Burger Combos', 'burger-combos', 86, TRUE),
  ((SELECT id FROM catalog_categories WHERE slug = 'restaurant'), 'Pizza Combos', 'pizza-combos', 87, TRUE),
  ((SELECT id FROM catalog_categories WHERE slug = 'restaurant'), 'Biryani Combos', 'biryani-combos', 88, TRUE),
  ((SELECT id FROM catalog_categories WHERE slug = 'restaurant'), 'Chinese Combos', 'chinese-combos', 89, TRUE),
  ((SELECT id FROM catalog_categories WHERE slug = 'restaurant'), 'Breakfast Combos', 'breakfast-combos', 90, TRUE),
  ((SELECT id FROM catalog_categories WHERE slug = 'restaurant'), 'Lunch Combos', 'lunch-combos', 91, TRUE),
  ((SELECT id FROM catalog_categories WHERE slug = 'restaurant'), 'Dinner Combos', 'dinner-combos', 92, TRUE),
  ((SELECT id FROM catalog_categories WHERE slug = 'restaurant'), 'Kids Meals', 'kids-meals', 93, TRUE),
  ((SELECT id FROM catalog_categories WHERE slug = 'restaurant'), 'Family Meals', 'family-meals', 94, TRUE),
  ((SELECT id FROM catalog_categories WHERE slug = 'restaurant'), 'Sharing Platters', 'sharing-platters', 95, TRUE),
  ((SELECT id FROM catalog_categories WHERE slug = 'restaurant'), 'Snacks & Beverages', 'snacks-and-beverages', 96, TRUE),
  ((SELECT id FROM catalog_categories WHERE slug = 'restaurant'), 'Veg Specials', 'veg-specials', 97, TRUE),
  ((SELECT id FROM catalog_categories WHERE slug = 'restaurant'), 'Non-Veg Specials', 'non-veg-specials', 98, TRUE),
  ((SELECT id FROM catalog_categories WHERE slug = 'restaurant'), 'Jain Food', 'jain-food', 99, TRUE),
  ((SELECT id FROM catalog_categories WHERE slug = 'restaurant'), 'Healthy Food', 'healthy-food', 100, TRUE),
  ((SELECT id FROM catalog_categories WHERE slug = 'restaurant'), 'Diet Food', 'diet-food', 101, TRUE)
ON CONFLICT (category_id, slug) DO NOTHING;

ALTER TABLE restaurants
  ADD COLUMN IF NOT EXISTS business_category_id INTEGER REFERENCES catalog_categories(id) ON DELETE SET NULL;

ALTER TABLE menu_items
  ADD COLUMN IF NOT EXISTS business_subcategory_id INTEGER REFERENCES catalog_subcategories(id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS idx_restaurants_business_category
  ON restaurants(business_category_id);
CREATE INDEX IF NOT EXISTS idx_menu_items_business_subcategory
  ON menu_items(business_subcategory_id);

UPDATE restaurants
SET business_category_id = (SELECT id FROM catalog_categories WHERE slug = 'restaurant')
WHERE business_category_id IS NULL;
