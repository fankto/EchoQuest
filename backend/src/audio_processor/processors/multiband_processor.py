# src/audio_processor/processors/multiband_processor.py
import torch
import torchaudio
from .base_processor import BaseProcessor
from ..config import settings

class MultibandProcessor(BaseProcessor):
    def __init__(self):
        super().__init__()
        self.min_bands = settings.MIN_BANDS
        self.max_bands = settings.MAX_BANDS
        self.multiband_chunk_duration = settings.MULTIBAND_CHUNK_DURATION

    def process(self, waveform: torch.Tensor) -> torch.Tensor:
        chunk_size = int(self.sample_rate * self.multiband_chunk_duration)
        num_chunks = (waveform.shape[1] + chunk_size - 1) // chunk_size

        result_waveform = torch.zeros_like(waveform)

        for chunk_idx in range(num_chunks):
            start = chunk_idx * chunk_size
            end = min((chunk_idx + 1) * chunk_size, waveform.shape[1])
            chunk = waveform[:, start:end]

            bands = self._analyze_frequency_content(chunk)
            compressed_bands = []

            for low, high in bands:
                band = self._process_band(chunk, low, high)
                compressed_bands.append(band)

            compressed_chunk = torch.sum(torch.stack(compressed_bands), dim=0)
            result_waveform[:, start:end] = torch.clamp(compressed_chunk, -1, 1)

        return torch.clamp(result_waveform, -1, 1)

    def _analyze_frequency_content(self, waveform: torch.Tensor):
        fft = torch.fft.rfft(waveform, dim=-1)
        freqs = torch.fft.rfftfreq(waveform.size(-1), 1/self.sample_rate).to(self.device)
        magnitude = torch.abs(fft)

        cumsum = torch.cumsum(magnitude, dim=-1)
        total_energy = cumsum[:, -1]
        num_bands = int(torch.clamp(total_energy.log10().int(),
                                    self.min_bands, self.max_bands).item())
        energy_per_band = total_energy / num_bands

        bands = []
        start_freq = freqs[0].item()

        for i in range(num_bands):
            target_energy = (i + 1) * energy_per_band
            target_energy = target_energy.unsqueeze(-1)
            end_idx = torch.searchsorted(cumsum, target_energy)
            end_idx = torch.clamp(end_idx, max=cumsum.size(1) - 1)
            end_freq = freqs[end_idx.item()].item()
            bands.append((start_freq, end_freq))
            start_freq = end_freq

        return bands

    def _process_band(self, waveform: torch.Tensor, low: float, high: float) -> torch.Tensor:
        filtered = torchaudio.functional.bandpass_biquad(
            waveform, self.sample_rate, (low + high) / 2, Q=1.0)
        filtered = torch.clamp(filtered, -1, 1)

        from .dynamics_processor import DynamicsProcessor
        dynamics = DynamicsProcessor()
        compressed = dynamics.process(filtered)

        return torch.clamp(compressed, -1, 1)