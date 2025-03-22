# src/audio_processor/processors/noise_processor.py
import torch
from .base_processor import BaseProcessor
from ..config import settings

class NoiseProcessor(BaseProcessor):
    def __init__(self):
        super().__init__()
        self.noise_reduction_factor = settings.NOISE_REDUCTION_FACTOR

    def process(self, waveform: torch.Tensor) -> torch.Tensor:
        stft = torch.stft(waveform, n_fft=self.n_fft, hop_length=self.hop_length,
                          window=self.window, return_complex=True)
        mag_spec = torch.abs(stft)

        noise_estimate = torch.mean(mag_spec[:, :, :10], dim=2, keepdim=True)
        cleaned_spec = torch.max(mag_spec - self.noise_reduction_factor * noise_estimate,
                                 torch.zeros_like(mag_spec))

        cleaned_stft = cleaned_spec * (stft / (mag_spec + 1e-8))
        return torch.istft(cleaned_stft, n_fft=self.n_fft, hop_length=self.hop_length,
                           window=self.window, length=waveform.shape[1])