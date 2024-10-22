# Use CUDA-enabled base image
FROM nvidia/cuda:12.2.2-cudnn8-runtime-ubuntu22.04

# Install Python and other dependencies
RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    ffmpeg \
    libavcodec-extra \
    libsndfile1 \
    libportaudio2 \
    sox \
    libsox-dev \
    libsox-fmt-all \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install poetry
RUN pip3 install poetry

# Copy poetry files
COPY pyproject.toml poetry.lock* ./

# Create necessary directory structure
RUN mkdir -p /app/src/audio_processor /root/.cache/huggingface

# Copy the rest of the application
COPY . .

# Copy .env file
COPY .env .

# Install dependencies
RUN poetry config virtualenvs.create false \
    && poetry install --no-interaction --no-ansi

# Set environment variables
ENV $(cat .env | xargs)
ENV TRANSFORMERS_CACHE=/root/.cache/huggingface

# Expose the port the app runs on
EXPOSE 8000

# Command to run the application
CMD ["poetry", "run", "uvicorn", "src.main:app", "--host", "0.0.0.0", "--reload"]