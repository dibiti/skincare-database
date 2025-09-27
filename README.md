# Skincare Database Project

This is a sample project for creating a skincare products database using PostgreSQL.

## Repository Contents

- **`schema.sql`**: The file containing the database schema and table creation.
- **`.gitignore`**: A file to ignore files and folders that should not be included in Git.

## Technologies Used

- **PostgreSQL**: Database management system.
- **Git & GitHub**: Version control and repository hosting.

## How to Use

1.  **Install PostgreSQL** and create a database named `skincare_db`.
2.  **Run the database schema** to create the tables:
    ```bash
    psql -U your-username -d skincare_db -f schema.sql
    ```