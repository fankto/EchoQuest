#!/bin/bash

# Function to check if a service is ready
check_service() {
    local host=$1
    local port=$2
    local service=$3
    echo "Waiting for $service..."
    until (echo > /dev/tcp/$host/$port) >/dev/null 2>&1; do
        sleep 1
    done
    echo "$service started"
}

# Wait for postgres to be ready
check_service postgres 5432 "PostgreSQL"

# Wait for redis to be ready
check_service redis 6379 "Redis"

# Wait for qdrant to be ready
check_service qdrant 6333 "Qdrant"

echo "Creating database tables..."
python create_tables.py || echo "Failed to create tables, they may already exist"

echo "Starting application..."
exec "$@" 