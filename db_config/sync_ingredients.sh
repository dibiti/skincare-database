#!/bin/bash

# =========================================================================
# SCRIPT: sync_ingredients.sh
# PURPOSE: Automates the entire UPSERT process for the 'ingredients' table
#          using data from 'seed_files/ingredients.csv'.
# =========================================================================

# --- Configuration ---
DB_USER="postgres"
DB_NAME="skincare_db"
CSV_PATH="seed_files/ingredients.csv"

echo "Starting ingredients synchronization on $DB_NAME..."

psql -d $DB_NAME -U $DB_USER <<EOF
BEGIN;

-- 1. Create the temporary table to hold the CSV data
-- NOTE: We assume your CSV contains these four columns.
CREATE TEMP TABLE temp_ingredients (
    ingredient_name VARCHAR(255) UNIQUE,
    ingredient_description TEXT,
    ingredient_function VARCHAR(255),
    cosmetic_classification VARCHAR(100)
);

-- 2. Copy data from CSV into the temporary table.
-- The column order in the CSV must match the order here!
\copy temp_ingredients (ingredient_name, ingredient_description, ingredient_function, cosmetic_classification) FROM '$CSV_PATH' DELIMITER ',' CSV HEADER;

-- 3. Execute the UPSERT (Update or Insert) logic
-- We use ingredient_name as the conflict key, ensuring:
-- - New ingredients are INSERTED.
-- - Existing ingredients have their description/function UPDATED if the data changed in the CSV.
INSERT INTO ingredients (ingredient_name, ingredient_description, ingredient_function, cosmetic_classification)
SELECT ingredient_name, ingredient_description, ingredient_function, cosmetic_classification
FROM temp_ingredients
ON CONFLICT (ingredient_name) DO UPDATE
    SET 
        ingredient_description = EXCLUDED.ingredient_description,
        ingredient_function = EXCLUDED.ingredient_function,
        cosmetic_classification = EXCLUDED.cosmetic_classification;

-- 4. Commit the transaction
COMMIT;

EOF

echo "Ingredients synchronization complete."