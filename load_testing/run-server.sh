#!/usr/bin/env bash

DB_TYPE=${1:-sqlite}  # Default to sqlite if no argument provided
NO_SERVICES=${2:-false}  # Default to false if no argument provided

# Function to start postgres container
start_postgres() {
    local version=$1
    local container_name="prefect-postgres"
    local volume_name="prefectdb"

    # Check if container exists
    if docker ps -a --format '{{.Names}}' | grep -q "^${container_name}$"; then
        echo "Found existing PostgreSQL container..."
        
        # Get current version from running container
        local current_version
        current_version=$(docker exec ${container_name} postgres --version 2>/dev/null | grep -oE '[0-9]+' | head -1 || echo "0")
        
        if [ "$current_version" != "${version%%.*}" ]; then
            echo "Version mismatch: existing=${current_version}, requested=${version%%.*}"
            echo "Removing container and volume for clean start..."
            docker rm -f ${container_name} >/dev/null 2>&1
            docker volume rm ${volume_name} >/dev/null 2>&1
        else
            echo "Version matches, reusing existing container..."
            if ! docker start ${container_name} >/dev/null 2>&1; then
                echo "Failed to start existing container, recreating..."
                docker rm -f ${container_name} >/dev/null 2>&1
                docker volume rm ${volume_name} >/dev/null 2>&1
            fi
        fi
    fi

    # Start container if it doesn't exist or was removed
    if ! docker ps --format '{{.Names}}' | grep -q "^${container_name}$"; then
        echo "Starting PostgreSQL ${version} container..."
        docker run -d --name ${container_name} \
            -v ${volume_name}:/var/lib/postgresql/data \
            -p 5432:5432 \
            -e POSTGRES_USER=postgres \
            -e POSTGRES_PASSWORD=yourTopSecretPassword \
            -e POSTGRES_DB=prefect \
            postgres:${version}
    fi

    echo "Waiting for PostgreSQL to be ready..."
    local retries=0
    local max_retries=30
    while ! docker exec ${container_name} pg_isready -U postgres > /dev/null 2>&1; do
        ((retries++))
        if [ $retries -gt $max_retries ]; then
            echo " Failed to start PostgreSQL after ${max_retries} seconds"
            docker logs ${container_name}
            exit 1
        fi
        echo -n "."
        sleep 1
    done
    echo " PostgreSQL is ready!"
}

# Set database URL based on type
if [[ $DB_TYPE == sqlite ]]; then
    : # Use default SQLite configuration
elif [[ $DB_TYPE == postgres:* ]]; then
    PG_VERSION=${DB_TYPE#postgres:}
    start_postgres $PG_VERSION
    prefect config set PREFECT_API_DATABASE_CONNECTION_URL="postgresql+asyncpg://postgres:yourTopSecretPassword@localhost:5432/prefect"
else
    echo "Invalid database type. Use 'sqlite' or 'postgres:<version>'"
    exit 1
fi

PREFECT_API_URL=http://localhost:4200/api \
PREFECT__SERVER_WEBSERVER_ONLY=$NO_SERVICES \
OTEL_SERVICE_NAME=prefect-server \
OTEL_TRACES_EXPORTER=otlp \
OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317 \
OTEL_EXPORTER_OTLP_PROTOCOL=grpc \
OTEL_LOG_LEVEL=debug \
PYTHONPATH=src \
  opentelemetry-instrument \
  uvicorn \
  --app-dir src \
  --factory prefect.server.api.server:create_app \
  --host 127.0.0.1 \
  --port 4200 \
  --timeout-keep-alive 5