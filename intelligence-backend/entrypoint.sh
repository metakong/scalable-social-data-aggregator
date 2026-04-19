#!/bin/sh
set -e

# This entrypoint script ensures the database is ready and migrations are
# applied before the main web application starts. This prevents race
# conditions and guarantees the database schema is correct.

DB_HOST="db"
DB_USER="$POSTGRES_USER"
DB_NAME="$POSTGRES_DB"

# 1. Wait for the database to be fully available.
echo "Waiting for PostgreSQL database to be ready at ${DB_HOST}:5432..."
until pg_isready -h "$DB_HOST" -U "$DB_USER" -d "$DB_NAME" -q; do
  >&2 echo "Postgres is unavailable - sleeping"
  sleep 2
done
>&2 echo "PostgreSQL is ready."

# 2. Run database migrations.
echo "Running database migrations..."
flask db upgrade
>&2 echo "Database migrations complete."

# 3. Execute the main command (e.g., start Gunicorn).
echo "Executing main command: $@"
exec "$@"