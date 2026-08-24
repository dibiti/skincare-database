-- db_config/migrations/V002__loader_prep.sql
--
-- Schema changes needed by the loader (Sprint 2).
-- Migrations are applied once to a live database; schema.sql stays the
-- canonical definition for FRESH databases and was updated to match.

-- 1. UPSERT needs a conflict target: the same product name can exist in two
--    different brands, but never twice within the same brand.
ALTER TABLE products
    ADD CONSTRAINT uq_products_name_brand UNIQUE (product_name, brand_id);

-- 2. Scraped prices come in USD (CeraVe, Haruharu, VT) and EUR (The Ordinary).
--    A column named price_euro holding dollars would silently corrupt every
--    future analysis, so the name stops lying and the currency is stored.
ALTER TABLE products RENAME COLUMN price_euro TO price;
ALTER TABLE products ADD COLUMN price_currency VARCHAR(3);

-- 3. Ingredient lists are ordered by concentration (highest first, by law in
--    the EU/US). Storing the position enables the core analyses of this
--    project, e.g. "advertised hero ingredient appears 14th on the list".
ALTER TABLE product_ingredients ADD COLUMN ingredient_rank INT;
