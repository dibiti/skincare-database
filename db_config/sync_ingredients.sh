#!/bin/bash

# =========================================================================
# SCRIPT: sync_ingredients.sh
# PURPOSE: Automates the entire UPSERT process for the 'ingredients' table
#          using data from 'seed_files/ingredients.csv'.
#
# The database runs in Docker (see docker-compose.yml), so psql is executed
# INSIDE the container. seed_files/ is mounted at /seed_files there.
# Run from the repository root: ./db_config/sync_ingredients.sh
# =========================================================================

set -e  # stop immediately if any command fails

# --- Configuration (credentials come from .env, same source as Docker) ---
source .env
CSV_PATH="/seed_files/ingredients.csv"

echo "Starting ingredients synchronization on $POSTGRES_DB..."

docker compose exec -T postgres psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" <<EOF
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
-- Names are UPPERCASED on the way in: the loader stores INCI names in
-- uppercase ('HYALURONIC ACID'), so the CSV can stay human-friendly
-- ('Hyaluronic Acid') without creating duplicate rows for the same substance.
INSERT INTO ingredients (ingredient_name, ingredient_description, ingredient_function, cosmetic_classification)
SELECT UPPER(ingredient_name), ingredient_description, ingredient_function, cosmetic_classification
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
