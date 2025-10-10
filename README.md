# Skincare Database Project 🧴✨

This is a sample project for creating a comprehensive skincare products database using PostgreSQL. The goal is to collect, normalize, and analyze product, brand, and ingredient data.

---

When I started setting up the database, I realized I needed a strategy to load the initial reference data, but one that wouldn't make me pull my hair out later! So, I chose the method that made the most sense for the type of data I was dealing with:

1. Direct SQL for the Small, Fixed Lists
The skin_types table is populated directly with a few SQL INSERT lines in the 01_seed_reference.sql file.

Why this choice? This list is tiny, and I know it won't change (it's always going to be 'Dry,' 'Oily,' 'Normal,' etc.). Since it's so small, writing the lines of code directly is the fastest way to get these essential categories into the database and start linking things up. It helps me move forward quickly.

2. CSV Files for the Big, Growing Lists
The brands and, especially, the ingredients tables are loaded using CSV files (seed_files/).

Why this choice? I expect these lists to grow huge! If I had to write SQL code for hundreds of ingredients, I would never finish. It's much easier and faster to manage this data in an Excel.

--NOT YET! The system uses a smart synchronization script (the UPSERT method) to safely load the CSV data. This means if I fix a typo in the ingredient description in the CSV, I can run one quick command, and the database updates itself. It lets me focus on the data, not the code.

---
I’m still determining the best approach for handling the upcoming tables and data, but I’ve decided to create a separate script for each brand to ensure data integrity and accuracy in the products and ingredients.

## Repository Contents

The project is structured to separate the database configuration, fixed data files, and scraping scripts.

- **`db_config/`**: Contains all SQL files for database setup and synchronization.
    - **`00_schema.sql`**: The file containing the database schema and table creation (`CREATE TABLE` statements).
    - **`01_seed_reference.sql`**: SQL script for populating small, fixed reference tables (e.g., `skin_types`).
    -- NOT YET - **`02_sync_brands.sql`**: SQL script for importing and performing **UPSERT** (Update or Insert) operations on the `brands` table, using the `brands.csv` file. 
- **`seed_files/`**: Stores the **initial fixed data** used for populating the database. These are maintained manually.
    - **`brands.csv`**: CSV file containing the list of brands and their country of origin.
    - **`ingredients.csv`**: CSV file containing the list of ingredients, descriptions, and functions.
- **`data/`**: (Ignored by Git) Folder for data files generated during the process.
    - **`raw/`**: Raw data extracted from web scraping (e.g., JSON files).
    - **`processed/`**: Cleaned and structured data (e.g., CSV) ready for database ingestion.
- **`scraping_scripts/`**: Python scripts used for web scraping and data extraction.
    - **`the_ordinary_scraper.py/`**: Basic request to the website so far!!
- **`.gitignore`**: A file to ignore files and folders that should not be included in Git (like the `data/` folder).

---

## Technologies Used

- **PostgreSQL**: Database management system for data storage and normalization.
- **Git & GitHub**: Version control and repository hosting.
- **Python**: Used for writing the web scraping and data processing scripts.

---

## How to Use

Follow these steps to set up and populate the database from scratch.

### 1. Database Setup

1.  **Install PostgreSQL** and ensure it's running on your system.
2.  **Create a database** named `skincare_db` (or a name of your choice).
3.  **Run the schema** to create all necessary tables:

    ```bash
    psql -U your-username -d skincare_db -f db_config/schema.sql
    ```

### 2. Initial Data Seeding

The database needs initial reference data (`skin_types`, `brands`, `ingredients`) before any product data can be added.

1.  **Populate Small Reference Tables (`skin_types`):**

    ```bash
    psql -U your-username -d skincare_db -f db_config/01_seed_reference.sql
    ```

2.  **Import Brands (Using CSV and UPSERT):** -- NOT YET

    This command uses the `02_sync_brands.sql` script to load data from `seed_files/brands.csv` into a temporary table and then perform a **safe synchronization** (UPSERT) with the main `brands` table.

    ```bash
    psql -U your-username -d skincare_db -f db_config/02_sync_brands.sql
    ```

3.  **Import Ingredients (CSV):** -- NOT YET, SAME LOGIC AS THE BRANDS TABLE

    Ingredients are imported directly from the CSV. **Note:** If the ingredients list is large, consider creating a synchronization script (like the one for brands) for safer updates.


### 3. Data Collection

Product data is collected and processed using Python scripts:

1.  Install the required Python libraries:

    ```bash
    pip install -r requirements.txt
    ```

2.  Run the scraping scripts in the `scraping_scripts/` folder to populate the `data/raw` and `data/processed` folders.

---

## Maintenance Notes
-- NOT YET
- To **update** brand information (e.g., change a country of origin or add new brands), simply edit `seed_files/brands.csv` and re-run the synchronization script: `psql -U your-username -d skincare_db -f db_config/02_sync_brands.sql`.
