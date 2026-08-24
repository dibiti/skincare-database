#!/bin/bash

# =========================================================================
# SCRIPT: sync_brands.sh
# PURPOSE: Automates the core UPSERT (Update or Insert) process for the
#          'brands' table using data from 'seed_files/brands.csv'.
#
# The database runs in Docker (see docker-compose.yml), so psql is executed
# INSIDE the container. seed_files/ is mounted at /seed_files there, which
# is why the \copy path below is /seed_files and not a Windows path.
# Run from the repository root: ./db_config/sync_brands.sh
# =========================================================================

set -e  # stop immediately if any command fails

# --- Configuration (credentials come from .env, same source as Docker) ---
source .env
CSV_PATH="/seed_files/brands.csv"

echo "Starting brands synchronization on $POSTGRES_DB..."

docker compose exec -T postgres psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" <<EOF
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
