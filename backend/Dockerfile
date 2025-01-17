# Use CUDA-enabled base image
FROM nvidia/cuda:12.2.2-cudnn8-runtime-ubuntu22.04

# Set environment variables
ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    POETRY_HOME=/opt/poetry \
    POETRY_VERSION=1.7.1 \
    POETRY_VIRTUALENVS_CREATE=false \
    PATH="/opt/poetry/bin:$PATH" \
    PYTHONPATH="/app:${PYTHONPATH}" \
    HF_HOME=/root/.cache/huggingface \
    TRANSFORMERS_CACHE=/root/.cache/huggingface \
    TORCH_HOME=/root/.cache/torch \
    XDG_CACHE_HOME=/root/.cache \
    PYTORCH_CUDA_ALLOC_CONF=max_split_size_mb:1024

# Model configuration environment variables
ENV MODEL_ASR_MODEL="openai/whisper-large-v3" \
    MODEL_DIARIZATION_MODEL="pyannote/speaker-diarization-3.1" \
    MODEL_ASR_BATCH_SIZE=1 \
    MODEL_ASR_RETURN_TIMESTAMPS=true \
    MODEL_TORCH_DTYPE=float16 \
    MODEL_DEVICE_MAP=auto \
    OLLAMA_HOST="http://ollama:11434" \
    OLLAMA_EXTRACT_MODEL="llama3.2" \
    OLLAMA_ANSWER_MODEL="llama3.2"

# Create and set permissions for cache directories
RUN mkdir -p /root/.cache/huggingface \
    /root/.cache/torch \
    /root/.cache/transformers \
    && chmod -R 777 /root/.cache

# Install system dependencies
RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    python3-venv \
    python-is-python3 \
    ffmpeg \
    libavcodec-extra \
    libsndfile1 \
    libportaudio2 \
    sox \
    libsox-dev \
    libsox-fmt-all \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install poetry
RUN curl -sSL https://install.python-poetry.org | python3 - --version ${POETRY_VERSION}

# Copy dependency files
COPY pyproject.toml poetry.lock ./

# Configure poetry and install dependencies
RUN poetry config installer.max-workers 10 && \
    poetry config installer.parallel true && \
    poetry config virtualenvs.create false && \
    poetry config http-basic.default-timeout 600 && \
    poetry install --no-interaction --no-ansi --no-root \
        || (sleep 5 && poetry install --no-interaction --no-ansi --no-root) \
        || (sleep 10 && poetry install --no-interaction --no-ansi --no-root)

# Copy the rest of the application
COPY . .

# Install the project
RUN poetry install --no-interaction --no-ansi

# Define volumes for caching
VOLUME [ "/root/.cache/huggingface", "/root/.cache/torch", "/root/.cache/transformers" ]

EXPOSE 8000

CMD ["poetry", "run", "uvicorn", "src.main:app", "--host", "0.0.0.0", "--reload"]