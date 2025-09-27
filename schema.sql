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
    price_euro DECIMAL(10, 2),
    size_ml DECIMAL(10, 2),
    description TEXT,
    image_url VARCHAR(255)
);

--
-- Table: ingredients
--
CREATE TABLE ingredients (
    ingredient_id SERIAL PRIMARY KEY,
    ingredient_name VARCHAR(255) NOT NULL UNIQUE,
    ingredient_description TEXT,
    ingredient_function VARCHAR(255),
    cosmetic_classification VARCHAR(50)
);

--
-- Table: product_ingredients
--
CREATE TABLE product_ingredients (
    product_id INT REFERENCES products(product_id),
    ingredient_id INT REFERENCES ingredients(ingredient_id),
    concentration_percent DECIMAL(5, 2),
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