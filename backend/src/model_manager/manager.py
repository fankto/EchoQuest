# src/model_manager/manager.py
import gc
import logging
import os
import threading
from typing import Dict, Optional

import torch
from pyannote.audio import Pipeline as DiarizationPipeline
from transformers import pipeline

from .ollama_client import OllamaClient, OllamaSettings

logger = logging.getLogger(__name__)

from pydantic_settings import BaseSettings


class ModelSettings(BaseSettings):
    ASR_MODEL: str = "openai/whisper-large-v3-turbo"
    DIARIZATION_MODEL: str = "pyannote/speaker-diarization-3.1"

    ASR_BATCH_SIZE: int = 4
    ASR_CHUNK_LENGTH: int = 30
    ASR_RETURN_TIMESTAMPS: bool = True

    TORCH_DTYPE: str = "float16"
    DEVICE_MAP: str = "auto"

    model_config = {
        "env_prefix": "MODEL_"
    }


settings = ModelSettings()


class ModelManager:
    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super(ModelManager, cls).__new__(cls)
                    cls._instance._initialize()
        return cls._instance

    def _initialize(self):
        """Initialize the model manager with CUDA optimizations"""
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        if torch.cuda.is_available():
            torch.backends.cuda.matmul.allow_tf32 = True
            torch.backends.cudnn.allow_tf32 = True
            torch.cuda.set_per_process_memory_fraction(0.9)

        self.models: Dict[str, any] = {}
        self.pipelines: Dict[str, any] = {}

        # Initialize Ollama client
        self.ollama_settings = OllamaSettings()  # Changed from from_env() to direct instantiation
        self.ollama_client = OllamaClient(self.ollama_settings)

        # Define model configurations
        self.model_configs = {
            'asr': {
                'name': settings.ASR_MODEL,
                'type': 'asr',
                'quantization': {
                    'torch_dtype': settings.TORCH_DTYPE,
                    'batch_size': settings.ASR_BATCH_SIZE,
                }
            },
            'diarization': {
                'name': settings.DIARIZATION_MODEL,
                'type': 'diarization',
                'requires_auth': True
            }
        }

    def get_model(self, model_key: str) -> Optional[any]:
        """Get or load model for specified key"""
        with self._lock:
            if model_key not in self.models:
                config = self.model_configs.get(model_key)
                if not config:
                    raise ValueError(f"Unknown model key: {model_key}")

                if torch.cuda.is_available():
                    torch.cuda.empty_cache()

                if config['type'] == 'asr':
                    self.models[model_key] = self._load_asr(config)
                elif config['type'] == 'diarization':
                    self.models[model_key] = self._load_diarization(config)

            return self.models[model_key]

    def get_pipeline(self, pipeline_key: str) -> Optional[any]:
        """Get or create pipeline for specified key"""
        with self._lock:
            if pipeline_key == 'llm_extract' or pipeline_key == 'llm_answer':
                return self.ollama_client

            if pipeline_key not in self.pipelines:
                config = self.model_configs.get(pipeline_key)
                if not config:
                    raise ValueError(f"Unknown pipeline key: {pipeline_key}")

                if config['type'] == 'asr':
                    self.pipelines[pipeline_key] = pipeline(
                        "automatic-speech-recognition",
                        model=self.get_model(pipeline_key),
                        device=self.device,
                        torch_dtype=config['quantization']['torch_dtype'],
                        batch_size=config['quantization']['batch_size'],
                        return_timestamps=settings.ASR_RETURN_TIMESTAMPS,
                        chunk_length_s=settings.ASR_CHUNK_LENGTH,
                    )
                elif config['type'] == 'diarization':
                    self.pipelines[pipeline_key] = self.get_model(pipeline_key)

            return self.pipelines[pipeline_key]

    def _load_asr(self, config: Dict) -> any:
        """Load ASR model"""
        return pipeline(
            "automatic-speech-recognition",
            model=config['name'],
            device=self.device,
            torch_dtype=config['quantization']['torch_dtype'],
            batch_size=config['quantization']['batch_size']
        ).model

    def _load_diarization(self, config: Dict) -> DiarizationPipeline:
        """Load diarization model"""
        return DiarizationPipeline.from_pretrained(
            config['name'],
            use_auth_token=os.getenv("HF_TOKEN"),
            cache_dir=os.getenv("TRANSFORMERS_CACHE")
        ).to(self.device)

    def preload_all_models(self):
        """Preload all configured models"""
        logger.info("Preloading all models...")
        try:
            for model_key in self.model_configs.keys():
                logger.info(f"Loading model: {model_key}")
                self.get_model(model_key)
                self.get_pipeline(model_key)

            # Preload Ollama models
            self.ollama_client.load_model(self.ollama_settings.extract_model)
            self.ollama_client.load_model(self.ollama_settings.answer_model)
        except Exception as e:
            logger.error(f"Error preloading models: {str(e)}")
            raise

    def unload_model(self, model_key: str):
        """Unload a specific model and clear its memory"""
        logger.info(f"Unloading model: {model_key}")
        try:
            if model_key.startswith('llm_'):
                model_name = self.ollama_settings.extract_model if model_key == 'llm_extract' else self.ollama_settings.answer_model
                self.ollama_client.unload_model(model_name)

            if model_key in self.models:
                # Delete the model
                if hasattr(self.models[model_key], 'cpu'):
                    self.models[model_key].cpu()
                del self.models[model_key]

            if model_key in self.pipelines:
                # Clean up pipeline
                if hasattr(self.pipelines[model_key], 'cpu'):
                    self.pipelines[model_key].cpu()
                del self.pipelines[model_key]

            # Force CUDA memory cleanup
            self._clear_gpu_memory()

        except Exception as e:
            logger.error(f"Error unloading model {model_key}: {str(e)}")
            raise

    def _clear_gpu_memory(self):
        """Clear GPU memory and cache"""
        gc.collect()
        if torch.cuda.is_available():
            with torch.cuda.device('cuda'):
                torch.cuda.empty_cache()
                torch.cuda.ipc_collect()

            # Reset peak memory stats
            torch.cuda.reset_peak_memory_stats()

    def unload_all(self):
        """Unload all models and clear memory"""
        logger.info("Unloading all models...")
        self.models.clear()
        self.pipelines.clear()
        self.ollama_client.unload_model(self.ollama_settings.extract_model)
        self.ollama_client.unload_model(self.ollama_settings.answer_model)
        self._clear_gpu_memory()


# Create singleton instance
model_manager = ModelManager()
