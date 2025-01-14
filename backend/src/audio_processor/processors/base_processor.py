# src/audio_processor/processors/base_processor.py
import torch
from ..config import settings

class BaseProcessor:
    def __init__(self):
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.sample_rate = settings.SAMPLE_RATE
        self.n_fft = settings.N_FFT
        self.hop_length = settings.HOP_LENGTH
        self.window = torch.hann_window(self.n_fft).to(self.device)

    def process(self, waveform: torch.Tensor) -> torch.Tensor:
        raise NotImplementedError