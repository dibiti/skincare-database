--
-- Table: brands
--
CREATE TABLE brands (
    brand_id SERIAL PRIMARY KEY,
    brand_name VARCHAR(255) NOT NULL UNIQUE,
    origin_country VARCHAR(50)
);

--
-- Table: products
--
CREATE TABLE products (
    product_id SERIAL PRIMARY KEY,
    product_name VARCHAR(255) NOT NULL,
    brand_id INT REFERENCES brands(brand_id),
    product_type VARCHAR(50),
    price DECIMAL(10, 2),
    price_currency VARCHAR(3),
    size_ml DECIMAL(10, 2),
    description TEXT,
    image_url VARCHAR(255),
    -- UPSERT conflict target: a product name is unique within its brand
    CONSTRAINT uq_products_name_brand UNIQUE (product_name, brand_id)
);

--
-- Table: ingredients
--
CREATE TABLE ingredients (
    ingredient_id SERIAL PRIMARY KEY,
    ingredient_name VARCHAR(255) NOT NULL UNIQUE,
    ingredient_description TEXT,
    ingredient_function VARCHAR(255),
    cosmetic_classification VARCHAR(50),
    -- CosIng enrichment (see loader/enrich_ingredients.py)
    -- 255, not 50: polymer families like CARBOMER carry several CAS numbers
    cas_no VARCHAR(255),
    ec_no VARCHAR(255),
    annex_max_concentration VARCHAR(100),  -- legal max for annex-listed ingredients
    cosing_status VARCHAR(20),      -- NULL = never queried | 'matched' | 'not_found'
    cosing_checked_at TIMESTAMPTZ
);

--
-- Table: product_ingredients
--
CREATE TABLE product_ingredients (
    product_id INT REFERENCES products(product_id),
    ingredient_id INT REFERENCES ingredients(ingredient_id),
    concentration_percent DECIMAL(5, 2),
    -- position on the label's ingredient list (1 = first); lists are ordered
    -- by concentration, so the rank powers "hero ingredient buried at #14" analyses
    ingredient_rank INT,
    PRIMARY KEY (product_id, ingredient_id)
);

--
-- Table: skin_types
--
CREATE TABLE skin_types (
    skin_type_id SERIAL PRIMARY KEY,
    skin_type_name VARCHAR(50) NOT NULL UNIQUE
);

--
-- Table: product_skin_types
--
CREATE TABLE product_skin_types (
    product_id INT REFERENCES products(product_id),
    skin_type_id INT REFERENCES skin_types(skin_type_id),
    PRIMARY KEY (product_id, skin_type_id)
);

--
-- Table: reviews
--
CREATE TABLE reviews (
    review_id SERIAL PRIMARY KEY,
    product_id INT REFERENCES products(product_id),
    rating INT,
    review_text TEXT,
    review_date DATE,
    review_source VARCHAR(100)
);