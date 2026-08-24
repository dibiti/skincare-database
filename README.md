# Skincare Database Project 🧴✨

This is a sample project for creating a comprehensive skincare products database using PostgreSQL. The goal is to collect, normalize, and analyze product, brand, and ingredient data.

## Development Approach

I build this project sprint by sprint using AI-assisted development (Claude Code) as a pair-programming mentor: I own the architecture decisions, review every change, and verify all scraped data against the sources. The "why" behind each technical choice is documented throughout this README.

---

When I started setting up the database, I realized I needed a strategy to load the initial reference data, but one that wouldn't make me pull my hair out later! So, I chose the method that made the most sense for the type of data I was dealing with:

1. Direct SQL for the Small, Fixed Lists
The **`skin_types`** table is populated directly with a few SQL INSERT lines in the 01_seed_reference.sql file.

Why this choice? This list is tiny, and I know it won't change (it's always going to be 'Dry,' 'Oily,' 'Normal,' etc.). Since it's so small, writing the lines of code directly is the fastest way to get these essential categories into the database and start linking things up. It helps me move forward quickly.

2. CSV Files for the Big, Growing Lists
The brands and, especially, the ingredients tables are loaded using CSV files (seed_files/).

 **Why this choice?** I expect these lists to **grow huge**! It's much **easier and faster** to manage this data in an Excel or Google Sheets file than writing hundreds of SQL lines. The system uses a smart **synchronization script** (the UPSERT method) to safely load the CSV data. This means if I fix a typo or add a new brand, I can run one quick command, and the database updates itself and resets the sequence. It lets me **focus on the data, not the code**.

---
I’m still determining the best approach for handling the upcoming tables and data, but I’ve decided to create a separate script for each brand to ensure data integrity and accuracy in the products and ingredients.

## Repository Contents

The project is structured to separate the database configuration, fixed data files, and scraping scripts.

- **`db_config/`**: Contains all SQL files for database setup and synchronization.
    - **`schema.sql`**: The file containing the database schema and table creation (`CREATE TABLE` statements) — the canonical definition for fresh databases.
    - **`migrations/`**: Numbered migration scripts (`V002__...`) applied to already-existing databases when the schema evolves.
    - **`01_seed_reference.sql`**: SQL script for populating small, fixed reference tables (e.g., `skin_types`).
    - **`sync_brands.sh`**: **Bash script** for performing the full **UPSERT** synchronization of the `brands` table, including CSV import
    - **`sync_ingredients.sh`**: **Bash script** for performing the full **UPSERT** synchronization of the `ingredients` table, including CSV import
- **`seed_files/`**: Stores the **initial fixed data** used for populating the database. These are maintained manually.
    - **`brands.csv`**: CSV file containing the list of brands and their country of origin.
    - **`ingredients.csv`**: CSV file containing the list of ingredients, descriptions, and functions.
- **`data/`**: (Ignored by Git) Folder for data files generated during the process.
    - **`raw/`**: Raw data extracted from web scraping (e.g., JSON files).
    - **`processed/`**: Cleaned and structured data (e.g., CSV) ready for database ingestion.
- **`loader/`**: Python script that upserts the scraped JSON files into PostgreSQL (see "Loading Products into the Database" below).
- **`scraping_scripts/`**: Python scripts used for web scraping and data extraction.
    - **`the_ordinary_scraper.py/`**: The needed information of all products of the brand, saved in .json file.
    - **`scrape_ingredients_haruharuwonder.py`**: I have notice that the brand haruharu wonder has a page dedicated a ingredients they use in their products, I decided to make a script to get that information about ingredientes to start populate my table, they are 97 total.
    - **` haruharuwonder_scraper`**: The needed information of all products of the brand, saved in .json file.
    - **` cerave_scraper`**: The needed information of all products of the brand, saved in .json file.
    - **` vt_cosmetics_scraper`**: The needed information of all products of the brand, saved in .json file.
- **`.gitignore`**: A file to ignore files and folders that should not be included in Git (like the `data/` folder).

---

## Technologies Used

- **PostgreSQL**: Database management system for data storage and normalization.
- **Git & GitHub**: Version control and repository hosting.
- **Python**: Used for writing the web scraping and data processing scripts.
- **Git Bash / WSL**: Required on Windows for executing the `.sh` automation scripts.

---

## How to Use

Follow these steps to set up and populate the database from scratch.

### 1. Database Setup (Docker)

The database runs in Docker, so there is nothing to install besides [Docker Desktop](https://www.docker.com/products/docker-desktop/). The whole database is **regenerable**: schema, seeds, and scraped data can rebuild it from scratch at any time.

1.  **Create your local configuration** (never committed to Git):

    ```bash
    cp .env.example .env
    ```

2.  **Start PostgreSQL** (port 5433, so it can coexist with other local instances):

    ```bash
    docker compose up -d
    ```

    On the first boot, the container automatically runs `db_config/schema.sql` (all tables) and `db_config/01_seed_reference.sql` (skin types) — nothing else to do.

3.  **Schema changes** after the first boot are applied as numbered migrations (the initdb scripts only run on an empty volume):

    ```bash
    docker exec -i skincare-postgres psql -U skincare -d skincare_db < db_config/migrations/V002__loader_prep.sql
    ```

### 2. Initial Data Seeding

The database needs initial reference data (`brands`, `ingredients`) before any product data can be added. `skin_types` is already seeded automatically by Docker (see above).

1.  **Prepare and Run the Automation Script (Brands):**

    This script handles the CSV import, UPSERT logic.

    a. **Make the script executable (only required once):**
    ```bash
    chmod +x db_config/sync_brands.sh
    ```

    b. **Run the synchronization:**
    ```bash
    ./db_config/sync_brands.sh
    ```

2.  **Prepare and Run the Automation Script (Ingredients):**

    This script handles the CSV import, UPSERT logic.

    a. **Make the script executable (only required once):**
    ```bash
    chmod +x db_config/sync_ingredients.sh
    ```

    b. **Run the synchronization:** 
    ```bash
    ./db_config/sync_ingredients.sh
    ```

### 3. Data Collection

Product data is collected and processed using Python scripts:

1.  Install the required Python libraries:

    ```bash
    pip install -r requirements.txt
    ```

2.  Run the scraping scripts in the `scraping_scripts/` folder to populate the `data/raw` and `data/processed` folders.

### 4. Loading Products into the Database

The loader takes every scraped JSON in `data/raw/` and upserts it into PostgreSQL:

```bash
python loader/load_products.py
```

Design choices worth knowing:

- **Idempotent**: every write is an `INSERT ... ON CONFLICT` (UPSERT), so re-running the loader after a fresh scrape is always safe — existing products are updated, never duplicated.
- **Fail loudly**: a source file with 0 products aborts the whole run. A scraper that silently returns nothing is a broken scraper, not an empty catalog.
- **Ingredient normalization**: INCI names are stored in UPPERCASE (`Water` and `WATER` are the same substance), and chemical names containing commas (`1,2-Hexanediol`) survive the parsing.
- **`ingredient_rank`**: the position of each ingredient on the label is stored. Ingredient lists are ordered by concentration, so the rank reveals whether an advertised "hero ingredient" is actually near the top of the formula — one of the core questions of this project.
- **Multi-currency prices**: scraped prices arrive in USD and EUR depending on the brand, so products store `price` + `price_currency` instead of assuming a single currency.

---

## Maintenance Notes

-   To **update** brand information (e.g., change a country of origin or add new brands), simply edit **`seed_files/brands.csv`** and re-run the synchronization script:
    ```GIT bash
    ./db_config/sync_brands.sh
    ```

-   To **update** ingredients information (e.g., change some field), simply edit **`seed_files/ingredients.csv`** and re-run the synchronization script:
    ```GIT bash
    ./db_config/sync_ingredients.sh
    ```