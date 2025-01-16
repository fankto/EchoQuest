# Use CUDA-enabled base image
FROM nvidia/cuda:12.2.2-cudnn8-runtime-ubuntu22.04

# Set environment variables to make installation less interactive
ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1
ENV POETRY_HOME=/opt/poetry
ENV POETRY_VERSION=1.7.1
ENV POETRY_VIRTUALENVS_CREATE=false
ENV PATH="/opt/poetry/bin:$PATH"

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

# Install poetry with curl to avoid pip timeout issues
RUN curl -sSL https://install.python-poetry.org | python3 - --version ${POETRY_VERSION}

# Copy just the poetry files first
COPY pyproject.toml poetry.lock ./

# Configure poetry and install dependencies with increased timeout
RUN poetry config installer.max-workers 10 && \
    poetry config installer.parallel true && \
    poetry config virtualenvs.create false && \
    poetry config http-basic.default-timeout 600 && \
    poetry install --no-interaction --no-ansi --no-root \
        || (sleep 5 && poetry install --no-interaction --no-ansi --no-root) \
        || (sleep 10 && poetry install --no-interaction --no-ansi --no-root)

# Copy the rest of the application
COPY . .

# Install the project itself
RUN poetry install --no-interaction --no-ansi

# Set environment variables
ENV PYTHONPATH="/app:${PYTHONPATH}"
ENV HF_HOME=/root/.cache/huggingface
ENV PYTORCH_CUDA_ALLOC_CONF=max_split_size_mb:1024

# Model configuration environment variables
ENV MODEL_ASR_MODEL="openai/whisper-large-v3"
ENV MODEL_DIARIZATION_MODEL="pyannote/speaker-diarization-3.1"
ENV MODEL_ASR_BATCH_SIZE=4
ENV MODEL_ASR_CHUNK_LENGTH=30
ENV MODEL_ASR_RETURN_TIMESTAMPS=true
ENV MODEL_TORCH_DTYPE=float16
ENV MODEL_DEVICE_MAP=auto

# Ollama configuration
ENV OLLAMA_HOST="http://ollama:11434"
ENV OLLAMA_EXTRACT_MODEL="llama3.2"
ENV OLLAMA_ANSWER_MODEL="llama3.2"

# Create directory for model cache
RUN mkdir -p /root/.cache/huggingface

EXPOSE 8000

CMD ["poetry", "run", "uvicorn", "src.main:app", "--host", "0.0.0.0", "--reload"]