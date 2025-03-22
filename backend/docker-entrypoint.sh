#!/bin/sh
set -e

echo "Creating database tables..."
python create_tables.py || echo "Failed to create tables, they may already exist"

echo "Starting application..."
exec "$@" 