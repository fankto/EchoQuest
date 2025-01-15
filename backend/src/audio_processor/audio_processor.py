# src/audio_processor/audio_processor.py
import logging
from typing import List

import torch
import torchaudio

from .config import settings
from .processors.base_processor import BaseProcessor
from .processors.chunk_processor import ChunkProcessor
from .processors.dynamics_processor import DynamicsProcessor
from .processors.noise_processor import NoiseProcessor
from .processors.silence_processor import SilenceProcessor
from .processors.spectral_processor import SpectralProcessor

logger = logging.getLogger(__name__)


class AudioProcessor:
    def __init__(self):
        # Configure CUDA memory management
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
            # Set environment variable for memory management
            import os
            os.environ['PYTORCH_CUDA_ALLOC_CONF'] = 'expandable_segments:True'

        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.sample_rate = settings.SAMPLE_RATE
        self.processors: List[BaseProcessor] = [
            NoiseProcessor(),
            SilenceProcessor(),
            DynamicsProcessor(),
            SpectralProcessor(),
        ]
        self.chunk_processor = ChunkProcessor(self)

    def process_chunk(self, waveform: torch.Tensor) -> torch.Tensor:
        """
        Process a single chunk of audio.
        """
        try:
            waveform = waveform.to(self.device)

            for processor in self.processors:
                waveform = processor.process(waveform)
                logger.debug(f"Chunk shape after {processor.__class__.__name__}: {waveform.shape}")

            return waveform

        except Exception as e:
            logger.error(f"Error processing chunk: {str(e)}")
            return waveform.cpu()

    def process(self, waveform: torch.Tensor, original_sample_rate: int) -> torch.Tensor:
        """
        Main processing method that uses chunk processing for large files.
        """
        try:
            # Calculate file duration in seconds
            duration = waveform.shape[-1] / original_sample_rate

            # Force chunked processing for files longer than 30 seconds
            if duration > 30:
                logger.info(f"Large file detected ({duration:.1f} seconds), using chunked processing")
                return self.chunk_processor.process_chunked(waveform, original_sample_rate)
            else:
                logger.info(f"Short file detected ({duration:.1f} seconds), processing entire file")
                return self._process_full(waveform, original_sample_rate)
        except Exception as e:
            logger.error(f"Error in audio processing: {str(e)}")
            return waveform.cpu()

    def _process_full(self, waveform: torch.Tensor, original_sample_rate: int) -> torch.Tensor:
        """
        Process the entire audio file at once (original method).
        """
        waveform = waveform.to(self.device)

        if original_sample_rate != self.sample_rate:
            waveform = torchaudio.functional.resample(
                waveform, original_sample_rate, self.sample_rate)

        if waveform.shape[0] > 1:
            waveform = torch.mean(waveform, dim=0, keepdim=True)

        for processor in self.processors:
            waveform = processor.process(waveform)

        max_val = torch.max(torch.abs(waveform))
        if max_val > 0:
            waveform = waveform / max_val * 0.99

        return waveform.cpu()

    def save_processed_audio(self, waveform: torch.Tensor, output_path: str):
        logger.debug(f"Saving processed audio to {output_path}")
        try:
            torchaudio.save(output_path, waveform.cpu(), self.sample_rate)
        except Exception as e:
            logger.warning(f"Error saving audio: {str(e)}")
