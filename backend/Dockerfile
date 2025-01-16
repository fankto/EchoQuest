# Use CUDA-enabled base image
FROM nvidia/cuda:12.2.2-cudnn8-runtime-ubuntu22.04

# Install Python and other dependencies
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
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install poetry
RUN pip3 install --no-cache-dir poetry

# Copy the entire project first
COPY . .

# Configure poetry and install dependencies
RUN poetry config virtualenvs.create false \
    && poetry install --no-interaction --no-ansi

# Set environment variables
ENV PYTHONPATH="/app:${PYTHONPATH}"
ENV HF_HOME=/root/.cache/huggingface
ENV PYTORCH_CUDA_ALLOC_CONF=max_split_size_mb:1024

# Model configuration environment variables
ENV MODEL_LLM_MODEL="meta-llama/Llama-2-7b-chat-hf"
ENV MODEL_ASR_MODEL="openai/whisper-large-v3"
ENV MODEL_DIARIZATION_MODEL="pyannote/speaker-diarization-3.1"
ENV MODEL_MAX_NEW_TOKENS=8192
ENV MODEL_TEMPERATURE=0.5
ENV MODEL_DO_SAMPLE=true
ENV MODEL_NUM_RETURN_SEQUENCES=1
ENV MODEL_ASR_BATCH_SIZE=4
ENV MODEL_ASR_CHUNK_LENGTH=30
ENV MODEL_ASR_RETURN_TIMESTAMPS=true
ENV MODEL_TORCH_DTYPE=float16
ENV MODEL_DEVICE_MAP=auto

# Create directory for model cache
RUN mkdir -p /root/.cache/huggingface

EXPOSE 8000

CMD ["poetry", "run", "uvicorn", "src.main:app", "--host", "0.0.0.0", "--reload"]