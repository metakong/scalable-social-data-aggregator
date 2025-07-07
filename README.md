# Veiled Vector Space - Latent Demand Discovery Engine

This project is the foundational data sourcing and analysis engine for the Veiled Vector Space App Factory. It is designed to identify latent consumer demand by scraping and analyzing discussions on non-technical online communities.

## System Setup

### 1. Environment Configuration

The system is configured using environment variables.

1.  **Create the `.env` file:**
    ```bash
    cp .env.example .env
    ```
2.  **Populate the `.env` file:** Manually edit the `.env` file and fill in values for `POSTGRES_PASSWORD`, `SECRET_KEY`, `MUMSNET_USERNAME`, `MUMSNET_PASSWORD`, and `GOOGLE_API_KEY`.

### 2. Deployment Procedure

This is the definitive, correct sequence of commands.

1.  **Full System Reset (Ensures a clean state):**
    ```bash
    docker compose down -v
    ```
2.  **Build Fresh Docker Images:**
    ```bash
    docker compose build
    ```
3.  **Start All Services (Waits for healthchecks):**
    ```bash
    docker compose up -d
    ```
4.  **Run Database Migrations (On the running container):**
    ```bash
    docker compose exec web flask db migrate -m "Finalized application architecture"
    docker compose exec web flask db upgrade
    ```

### 3. Accessing the Application

* **Dashboard**: `http://localhost:8000`