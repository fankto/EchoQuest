# src/model_manager/manager.py
import os
import gc
import logging
import threading
from typing import Dict, Optional
import torch
from functools import lru_cache
from transformers import (
    AutoTokenizer,
    AutoModelForCausalLM,
    BitsAndBytesConfig,
    pipeline
)
from pyannote.audio import Pipeline as DiarizationPipeline

logger = logging.getLogger(__name__)

from pydantic_settings import BaseSettings

class ModelSettings(BaseSettings):
    LLM_MODEL: str = "meta-llama/Llama-3.1-8B-Instruct"
    ASR_MODEL: str = "openai/whisper-large-v3-turbo"
    DIARIZATION_MODEL: str = "pyannote/speaker-diarization-3.1"

    # Can be overridden by environment variables:
    # MODEL_MAX_NEW_TOKENS, MODEL_TEMPERATURE, etc.
    MAX_NEW_TOKENS: int = 8192
    DO_SAMPLE: bool = True
    TEMPERATURE: float = 0.5
    NUM_RETURN_SEQUENCES: int = 1

    ASR_BATCH_SIZE: int = 4
    ASR_CHUNK_LENGTH: int = 30
    ASR_RETURN_TIMESTAMPS: bool = True

    TORCH_DTYPE: str = "float16"  # Will be converted to torch.dtype
    DEVICE_MAP: str = "auto"

    class Config:
        env_prefix = "MODEL_"  # Will look for MODEL_LLM_MODEL, etc.

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
            # Enable TF32 for better performance
            torch.backends.cuda.matmul.allow_tf32 = True
            torch.backends.cudnn.allow_tf32 = True
            # Set memory allocator settings
            torch.cuda.set_per_process_memory_fraction(0.9)  # Use up to 90% of available memory

        self.models: Dict[str, any] = {}
        self.tokenizers: Dict[str, any] = {}
        self.pipelines: Dict[str, any] = {}

        # Define model configurations
        self.model_configs = {
            'llm': {
                'name': ModelSettings.LLM_MODEL,
                'type': 'causal_lm',
                'quantization': {
                    'load_in_8bit': True,
                    'compute_dtype': ModelSettings.TORCH_DTYPE,
                }
            },
            'asr': {
                'name': ModelSettings.ASR_MODEL,
                'type': 'asr',
                'quantization': {
                    'torch_dtype': ModelSettings.TORCH_DTYPE,
                    'batch_size': ModelSettings.ASR_BATCH_SIZE,
                }
            },
            'diarization': {
                'name': ModelSettings.DIARIZATION_MODEL,
                'type': 'diarization',
                'requires_auth': True
            }
        }

    @lru_cache(maxsize=None)
    def get_tokenizer(self, model_key: str) -> Optional[AutoTokenizer]:
        """Get or load tokenizer for specified model"""
        if model_key not in self.tokenizers:
            config = self.model_configs.get(model_key)
            if not config:
                raise ValueError(f"Unknown model key: {model_key}")

            self.tokenizers[model_key] = AutoTokenizer.from_pretrained(
                config['name'],
                cache_dir=os.getenv("TRANSFORMERS_CACHE")
            )
        return self.tokenizers[model_key]

    def get_model(self, model_key: str) -> Optional[any]:
        """Get or load model for specified key"""
        with self._lock:
            if model_key not in self.models:
                config = self.model_configs.get(model_key)
                if not config:
                    raise ValueError(f"Unknown model key: {model_key}")

                # Clear CUDA cache before loading new model
                if torch.cuda.is_available():
                    torch.cuda.empty_cache()

                if config['type'] == 'causal_lm':
                    self.models[model_key] = self._load_causal_lm(config)
                elif config['type'] == 'asr':
                    self.models[model_key] = self._load_asr(config)
                elif config['type'] == 'diarization':
                    self.models[model_key] = self._load_diarization(config)

            return self.models[model_key]

    def get_pipeline(self, pipeline_key: str) -> Optional[any]:
        """Get or create pipeline for specified key"""
        with self._lock:
            if pipeline_key not in self.pipelines:
                config = self.model_configs.get(pipeline_key)
                if not config:
                    raise ValueError(f"Unknown pipeline key: {pipeline_key}")

                if config['type'] == 'causal_lm':
                    self.pipelines[pipeline_key] = pipeline(
                        "text-generation",
                        model=self.get_model(pipeline_key),
                        tokenizer=self.get_tokenizer(pipeline_key),
                        device_map=ModelSettings.DEVICE_MAP,
                        max_new_tokens=ModelSettings.MAX_NEW_TOKENS,
                        do_sample=ModelSettings.DO_SAMPLE,
                        temperature=ModelSettings.TEMPERATURE,
                        num_return_sequences=ModelSettings.NUM_RETURN_SEQUENCES,
                    )
                elif config['type'] == 'asr':
                    self.pipelines[pipeline_key] = pipeline(
                        "automatic-speech-recognition",
                        model=self.get_model(pipeline_key),
                        device=self.device,
                        torch_dtype=config['quantization']['torch_dtype'],
                        batch_size=config['quantization']['batch_size'],
                        return_timestamps=ModelSettings.ASR_RETURN_TIMESTAMPS,
                        chunk_length_s=ModelSettings.ASR_CHUNK_LENGTH,
                    )
                elif config['type'] == 'diarization':
                    self.pipelines[pipeline_key] = self.get_model(pipeline_key)

            return self.pipelines[pipeline_key]

    def _load_causal_lm(self, config: Dict) -> AutoModelForCausalLM:
        """Load causal language model with quantization"""
        quantization_config = BitsAndBytesConfig(
            load_in_8bit=True,
            llm_int8_enable_fp32_cpu_offload=True
        )

        return AutoModelForCausalLM.from_pretrained(
            config['name'],
            quantization_config=quantization_config,
            device_map=ModelSettings.DEVICE_MAP,
            torch_dtype=config['quantization']['compute_dtype'],
            low_cpu_mem_usage=True,
            cache_dir=os.getenv("TRANSFORMERS_CACHE")
        )

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
                self.get_tokenizer(model_key)
                self.get_pipeline(model_key)
        except Exception as e:
            logger.error(f"Error preloading models: {str(e)}")
            raise

    def unload_model(self, model_key: str):
        """Unload a specific model and clear its memory"""
        if model_key in self.models:
            del self.models[model_key]
        if model_key in self.pipelines:
            del self.pipelines[model_key]
        if model_key in self.tokenizers:
            del self.tokenizers[model_key]

        self._clear_gpu_memory()

    def unload_all(self):
        """Unload all models and clear memory"""
        logger.info("Unloading all models...")
        self.models.clear()
        self.tokenizers.clear()
        self.pipelines.clear()
        self._clear_gpu_memory()

    def _clear_gpu_memory(self):
        """Clear GPU memory and cache"""
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
            torch.cuda.ipc_collect()

model_manager = ModelManager()