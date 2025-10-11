#!/bin/bash

# =========================================================================
# SCRIPT: sync_brands.sh
# PURPOSE: Automates the core UPSERT (Update or Insert) process for the 
#          'brands' table using data from 'seed_files/brands.csv'.
# =========================================================================

# --- Configuration ---
DB_USER="postgres"
DB_NAME="skincare_db"
CSV_PATH="seed_files/brands.csv"

echo "Starting simplified brands synchronization on $DB_NAME..."

psql -d $DB_NAME -U $DB_USER <<EOF
BEGIN;

-- 1. Create the temporary table to hold the CSV data
CREATE TEMP TABLE temp_brands (
    brand_name VARCHAR(255) UNIQUE,
    origin_country VARCHAR(50)
);

-- 2. Copy data from CSV into the temporary table.
\copy temp_brands (brand_name, origin_country) FROM '$CSV_PATH' DELIMITER ',' CSV HEADER;

-- 3. Execute the UPSERT (Update or Insert) logic
-- Inserts new brands or updates the origin_country for existing brands based on brand_name.
INSERT INTO brands (brand_name, origin_country)
SELECT brand_name, origin_country
FROM temp_brands
ON CONFLICT (brand_name) DO UPDATE
    SET 
        origin_country = EXCLUDED.origin_country;

-- 4. Commit the transaction
COMMIT;

EOF

echo "Brands synchronization complete."