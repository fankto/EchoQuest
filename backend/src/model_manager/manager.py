# src/model_manager/manager.py
import gc
import logging
import os
from typing import Dict, Optional

import torch
from pyannote.audio import Pipeline as DiarizationPipeline
from transformers import pipeline

from .ollama_client import OllamaClient, OllamaSettings

logger = logging.getLogger(__name__)

from pydantic_settings import BaseSettings


class ModelSettings(BaseSettings):
    ASR_MODEL: str = "openai/whisper-large-v3"
    DIARIZATION_MODEL: str = "pyannote/speaker-diarization-3.1"

    # ASR settings optimized for full-file processing
    ASR_BATCH_SIZE: int = 1  # Keep batch size at 1 for full file processing
    ASR_RETURN_TIMESTAMPS: bool = True

    # Memory optimization
    TORCH_DTYPE: str = "float16"
    DEVICE_MAP: str = "auto"

    # GPU optimization settings
    TORCH_COMPILE: bool = True
    NUM_WORKERS: int = 2
    MAX_MEMORY: Dict[str, str] = {
        "cuda:0": "9GB",
    }

    # Diarization settings
    DIARIZATION_MIN_SPEAKERS: int = 1
    DIARIZATION_MAX_SPEAKERS: int = 5

    model_config = {
        "env_prefix": "MODEL_"
    }


settings = ModelSettings()


class ModelManager:
    _instance = None
    LANGUAGE_MODEL_MAPPING = {
        'gsw': 'nizarmichaud/whisper-large-v3-turbo-swissgerman',
        'default': 'openai/whisper-large-v3'
    }

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(ModelManager, cls).__new__(cls)
            cls._instance._initialize()
        return cls._instance

    def _initialize(self):
        """Initialize the model manager with CUDA optimizations"""
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        if torch.cuda.is_available():
            # Enable TF32 for better performance on Ampere GPUs
            torch.backends.cuda.matmul.allow_tf32 = True
            torch.backends.cudnn.allow_tf32 = True

            # Enable cudnn benchmark mode for optimized convolution algorithms
            torch.backends.cudnn.benchmark = True

            # Set autocast dtype
            torch.set_float32_matmul_precision('high')

            # Configure memory management
            torch.cuda.set_per_process_memory_fraction(0.95)
            os.environ['PYTORCH_CUDA_ALLOC_CONF'] = (
                'max_split_size_mb:512,'
                'garbage_collection_threshold:0.8,'
                'roundup_power2_divisions:4'
            )

        self.models: Dict[str, any] = {}
        self.pipelines: Dict[str, any] = {}
        self.processors: Dict[str, any] = {}

        # Initialize Ollama client
        self.ollama_settings = OllamaSettings()
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
                'requires_auth': True,
            }
        }

    def _load_asr(self, config: Dict) -> any:
        """Load ASR model with full-file processing configuration"""
        logger.info(f"Starting ASR model loading process for {config['name']}")
        try:
            from transformers import AutoModelForSpeechSeq2Seq, AutoProcessor
            import torch

            hf_token = os.getenv('HF_TOKEN')
            if not hf_token:
                logger.error("HF_TOKEN environment variable is not set")
                raise ValueError("HF_TOKEN is required but not set")

            # Verify token
            logger.info("Verifying HF_TOKEN...")
            from huggingface_hub import HfApi
            api = HfApi()
            try:
                api.whoami(token=hf_token)
                logger.info("HF_TOKEN verification successful")
            except Exception as e:
                logger.error(f"HF_TOKEN verification failed: {str(e)}")
                raise ValueError(f"Invalid HF_TOKEN: {str(e)}")

            cache_dir = os.getenv('TRANSFORMERS_CACHE', '/root/.cache/huggingface')
            os.makedirs(cache_dir, exist_ok=True)

            # Load processor
            logger.info(f"Loading processor for {config['name']}")
            try:
                processor = AutoProcessor.from_pretrained(
                    config['name'],
                    token=hf_token,  # Updated from use_auth_token
                    cache_dir=cache_dir,
                    trust_remote_code=True,
                )
                logger.info("Processor loaded successfully")
            except Exception as e:
                logger.error(f"Failed to load processor: {str(e)}")
                raise

            # Load model
            logger.info(f"Loading model {config['name']}")
            try:
                model = AutoModelForSpeechSeq2Seq.from_pretrained(
                    config['name'],
                    token=hf_token,
                    cache_dir=cache_dir,
                    trust_remote_code=True,
                    torch_dtype=config['quantization']['torch_dtype'],
                    device_map="auto",
                    low_cpu_mem_usage=True,
                )
                logger.info("Model loaded successfully")
            except Exception as e:
                logger.error(f"Failed to load model: {str(e)}")
                raise

            # Optimize model
            logger.info(f"Optimizing model for {self.device}")
            model = model.to(self.device)

            if settings.TORCH_COMPILE:
                logger.info("Compiling model")
                try:
                    model = torch.compile(model)
                    logger.info("Model compilation completed")
                except Exception as e:
                    logger.warning(f"Model compilation failed, continuing without compilation: {str(e)}")

            # Create pipeline
            logger.info("Creating ASR pipeline")
            asr_pipeline = pipeline(
                "automatic-speech-recognition",
                model=model,
                tokenizer=processor.tokenizer,
                feature_extractor=processor.feature_extractor,
                batch_size=config['quantization']['batch_size'],
                return_timestamps=settings.ASR_RETURN_TIMESTAMPS,
            )

            # Log memory usage
            if torch.cuda.is_available():
                memory_allocated = torch.cuda.memory_allocated() / 1024 ** 2
                memory_reserved = torch.cuda.memory_reserved() / 1024 ** 2
                logger.info(f"CUDA memory allocated: {memory_allocated:.2f} MB")
                logger.info(f"CUDA memory reserved: {memory_reserved:.2f} MB")

            self.processors[config['name']] = processor
            return asr_pipeline.model

        except Exception as e:
            logger.error(f"Error in ASR model loading: {str(e)}", exc_info=True)
            raise

    def _load_diarization(self, config: Dict) -> DiarizationPipeline:
        """Load diarization model with optimized settings"""
        logger.info(f"Loading diarization model with config: {config}")
        try:
            logger.info("Checking auth token")
            auth_token = os.getenv("HF_TOKEN")
            if not auth_token:
                error_msg = "HF_TOKEN environment variable not set"
                logger.error(error_msg)
                raise ValueError(error_msg)

            logger.info("Creating diarization pipeline")
            pipeline = DiarizationPipeline.from_pretrained(
                config['name'],
                cache_dir=os.getenv("TRANSFORMERS_CACHE"),
                use_auth_token=auth_token
            )

            # Move to device and apply settings
            pipeline = pipeline.to(self.device)

            logger.info("Diarization pipeline created and configured successfully")
            return pipeline

        except Exception as e:
            logger.error(f"Error loading diarization model: {str(e)}", exc_info=True)
            raise

    def get_model(self, model_key: str) -> Optional[any]:
        """Get or load model for specified key"""
        logger.info(f"Getting model for key: {model_key}")
        try:
            if model_key not in self.models:
                config = self.model_configs.get(model_key)
                if not config:
                    raise ValueError(f"Unknown model key: {model_key}")

                if torch.cuda.is_available():
                    torch.cuda.empty_cache()
                    memory_before = torch.cuda.memory_allocated()

                if config['type'] == 'asr':
                    self.models[model_key] = self._load_asr(config)
                elif config['type'] == 'diarization':
                    self.models[model_key] = self._load_diarization(config)

                if torch.cuda.is_available():
                    memory_after = torch.cuda.memory_allocated()
                    logger.info(f"Memory increase: {(memory_after - memory_before) / 1024 ** 2:.2f} MB")

            return self.models[model_key]
        except Exception as e:
            logger.error(f"Error in get_model for {model_key}: {str(e)}", exc_info=True)
            raise

    def _get_asr_model_name(self, language: Optional[str] = None) -> str:
        """Get the appropriate model name based on language"""
        if language == 'gsw':  # Swiss German
            return 'nizarmichaud/whisper-large-v3-turbo-swissgerman'
        return 'openai/whisper-large-v3'

    def get_pipeline(self, pipeline_key: str, language: Optional[str] = None) -> Optional[any]:
        """Get or create pipeline for specified key with language support"""
        logger.info(f"Getting pipeline for key: {pipeline_key}")
        try:
            if pipeline_key in ['llm_extract', 'llm_answer']:
                return self.ollama_client

            if pipeline_key == 'asr':
                model_name = self._get_asr_model_name(language)
                pipeline_key = f"{pipeline_key}_{language if language else 'default'}"

                if pipeline_key not in self.pipelines:
                    model_config = self.model_configs.get('asr')
                    if not model_config:
                        raise ValueError(f"Unknown pipeline key: {pipeline_key}")

                    # Update model name in config
                    model_config = {**model_config, 'name': model_name}

                    model = self._load_asr(model_config)
                    if model is None:
                        raise RuntimeError(f"Failed to load model for pipeline {pipeline_key}")

                    processor = self.processors[model_config['name']]
                    pipeline_kwargs = {
                        "model": model,
                        "tokenizer": processor.tokenizer,
                        "feature_extractor": processor.feature_extractor,
                        "chunk_length_s": 30,
                        "stride_length_s": 1,
                        "batch_size": 8,
                        "torch_dtype": torch.float16 if torch.cuda.is_available() else torch.float32,
                    }

                    self.pipelines[pipeline_key] = pipeline(
                        "automatic-speech-recognition",
                        **pipeline_kwargs
                    )

                return self.pipelines[pipeline_key]

            elif pipeline_key == 'diarization':
                model_config = self.model_configs.get('diarization')
                if not model_config:
                    raise ValueError(f"Unknown pipeline key: diarization")

                logger.info("Creating diarization pipeline")
                auth_token = os.getenv("HF_TOKEN")
                if not auth_token:
                    raise ValueError("HF_TOKEN environment variable not set")

                diarization_pipeline = DiarizationPipeline.from_pretrained(
                    model_config['name'],
                    use_auth_token=auth_token,
                    cache_dir=os.getenv("TRANSFORMERS_CACHE")
                )

                # Move pipeline to device
                self.pipelines[pipeline_key] = diarization_pipeline.to(self.device)
                logger.info("Diarization pipeline created successfully")
                return self.pipelines[pipeline_key]

            else:
                raise ValueError(f"Unknown pipeline key: {pipeline_key}")

        except Exception as e:
            logger.error(f"Error in get_pipeline for {pipeline_key}: {str(e)}", exc_info=True)
            raise

    def unload_model(self, model_key: str):
        """Unload a specific model and clear its memory"""
        logger.info(f"Unloading model: {model_key}")
        try:
            if model_key not in ['llm_extract', 'llm_answer']:
                if model_key in self.models:
                    if hasattr(self.models[model_key], 'cpu'):
                        self.models[model_key].cpu()
                    del self.models[model_key]

                if model_key in self.pipelines:
                    if hasattr(self.pipelines[model_key], 'cpu'):
                        self.pipelines[model_key].cpu()
                    del self.pipelines[model_key]

                self._clear_gpu_memory()

            logger.info(f"Successfully unloaded model: {model_key}")
        except Exception as e:
            logger.error(f"Error unloading model {model_key}: {str(e)}")
            raise

    def unload_all(self):
        """Unload all models and clear memory"""
        logger.info("Unloading all models...")
        try:
            self.models.clear()
            self.pipelines.clear()
            self._clear_gpu_memory()
            logger.info("Successfully unloaded all models")
        except Exception as e:
            logger.error(f"Error during unload_all: {str(e)}")
            raise

    def _clear_gpu_memory(self):
        """Clear GPU memory and cache"""
        gc.collect()
        if torch.cuda.is_available():
            with torch.cuda.device('cuda'):
                torch.cuda.empty_cache()
                torch.cuda.ipc_collect()
            torch.cuda.reset_peak_memory_stats()
            logger.info("GPU memory cleared")


# Create singleton instance
model_manager = ModelManager()
