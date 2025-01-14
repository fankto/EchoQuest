# src/audio_processor/audio_processor.py
import logging
import torch
import torchaudio
from typing import List

from .processors.base_processor import BaseProcessor
from .processors.noise_processor import NoiseProcessor
from .processors.silence_processor import SilenceProcessor
from .processors.dynamics_processor import DynamicsProcessor
from .processors.spectral_processor import SpectralProcessor
from .processors.multiband_processor import MultibandProcessor
from .config import settings

logger = logging.getLogger(__name__)

class AudioProcessor:
    def __init__(self):
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.sample_rate = settings.SAMPLE_RATE
        self.processors: List[BaseProcessor] = [
            NoiseProcessor(),
            SilenceProcessor(),
            DynamicsProcessor(),
            SpectralProcessor(),
            MultibandProcessor()
        ]

    def process(self, waveform: torch.Tensor, original_sample_rate: int) -> torch.Tensor:
        try:
            waveform = waveform.to(self.device)
            logger.debug(f"Starting audio processing. Input shape: {waveform.shape}")

            if original_sample_rate != self.sample_rate:
                waveform = torchaudio.functional.resample(
                    waveform, original_sample_rate, self.sample_rate)

            if waveform.shape[0] > 1:
                waveform = torch.mean(waveform, dim=0, keepdim=True)

            for processor in self.processors:
                waveform = processor.process(waveform)
                logger.debug(f"Waveform shape after {processor.__class__.__name__}: {waveform.shape}")

            # Final normalization
            max_val = torch.max(torch.abs(waveform))
            if max_val > 0:
                waveform = waveform / max_val * 0.99

            if waveform.dim() != 2:
                logger.warning(f"Unexpected waveform shape after processing: {waveform.shape}. Reshaping to 2D.")
                waveform = waveform.view(1, -1)

            return waveform.cpu()
        except Exception as e:
            logger.error(f"Error in audio processing: {str(e)}")
            return waveform.cpu()

    def save_processed_audio(self, waveform: torch.Tensor, output_path: str):
        logger.debug(f"Saving processed audio to {output_path}")
        try:
            torchaudio.save(output_path, waveform.cpu(), self.sample_rate)
        except Exception as e:
            logger.warning(f"Error saving audio: {str(e)}")