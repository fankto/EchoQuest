FROM python:3.11-slim

WORKDIR /app

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

# Install system dependencies
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential \
        libpq-dev \
        ffmpeg \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Install Poetry
RUN pip install --upgrade pip \
    && pip install poetry==1.7.1 aiofiles

# Copy only requirements to cache them in docker layer
COPY pyproject.toml /app/

# Configure poetry to not use a virtual environment and install dependencies
RUN poetry config virtualenvs.create false \
    && poetry lock --no-update \
    && poetry install --no-interaction --no-ansi --no-root --only main

# Copy application code
COPY . /app/

# Create data directories
RUN mkdir -p /app/data/uploads /app/data/processed

# Expose port
EXPOSE 8000

# Run the application
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]