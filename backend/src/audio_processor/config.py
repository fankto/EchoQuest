# src/audio_processor/config.py
import os
from typing import List

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    MAX_SEGMENT_DURATION: int = 30
    SAMPLE_RATE: int = 48000
    SUPPORTED_FORMATS: List[str] = ['mp3', 'wav', 'ogg', 'flac', 'm4a']
    MAX_WORKERS: int = 6
    TEMP_DIR: str = os.path.join(os.path.dirname(__file__), "temp")
    UPLOAD_DIRECTORY: str = os.path.join(os.path.dirname(__file__), "uploads")

    N_FFT: int = 4096
    HOP_LENGTH: int = 1024
    NOISE_REDUCTION_FACTOR: float = 0.03
    VAD_THRESHOLD: float = 0.1
    COMP_THRESHOLD: float = -30
    COMP_RATIO: float = 3
    COMP_ATTACK_TIME: float = 3
    COMP_RELEASE_TIME: float = 100
    MIN_BANDS: int = 4
    MAX_BANDS: int = 10
    MULTIBAND_CHUNK_DURATION: float = 5.0  # in seconds
    EQUALIZER_BANDS: List[int] = [60, 170, 310, 600, 1000, 3000, 6000, 12000, 14000, 16000]
    EQUALIZER_GAINS: List[float] = [2, 1, 0, -0.5, 1, 2, 3, 2, 1, 0]
    DEESSING_THRESHOLD: float = -25
    DEESSING_RATIO: float = 2.5
    SILENCE_THRESHOLD_PERCENTILE: float = 0.1
    HARMONIC_EXCITER_FACTOR: float = 0.1

settings = Settings()

os.makedirs(settings.TEMP_DIR, exist_ok=True)
os.makedirs(settings.UPLOAD_DIRECTORY, exist_ok=True)
