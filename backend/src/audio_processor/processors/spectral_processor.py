# src/audio_processor/processors/spectral_processor.py
import torch
from .base_processor import BaseProcessor
from ..config import settings

class SpectralProcessor(BaseProcessor):
    def __init__(self):
        super().__init__()
        self.equalizer_bands = torch.tensor(settings.EQUALIZER_BANDS, device=self.device)
        self.equalizer_gains = torch.tensor(settings.EQUALIZER_GAINS, device=self.device)
        self.deessing_threshold = settings.DEESSING_THRESHOLD
        self.deessing_ratio = settings.DEESSING_RATIO
        self.harmonic_exciter_factor = settings.HARMONIC_EXCITER_FACTOR

    def apply_equalization(self, waveform: torch.Tensor) -> torch.Tensor:
        freq_bins = torch.fft.rfftfreq(self.n_fft, d=1/self.sample_rate).to(self.device)
        eq_curve = torch.ones(freq_bins.shape[0], device=self.device)

        for freq, gain in zip(self.equalizer_bands, self.equalizer_gains):
            eq_curve += gain * torch.exp(-((freq_bins - freq) ** 2) / (2 * (freq / 5) ** 2))

        stft = torch.stft(waveform, n_fft=self.n_fft, hop_length=self.hop_length,
                          window=self.window, return_complex=True)
        eq_stft = stft * eq_curve.unsqueeze(0).unsqueeze(-1)

        return torch.istft(eq_stft, n_fft=self.n_fft, hop_length=self.hop_length,
                           window=self.window, length=waveform.shape[1])

    def apply_deessing(self, waveform: torch.Tensor) -> torch.Tensor:
        stft = torch.stft(waveform, n_fft=self.n_fft, hop_length=self.hop_length,
                          window=self.window, return_complex=True)
        mag_spec = torch.abs(stft)

        freq_bins = torch.fft.rfftfreq(self.n_fft, d=1/self.sample_rate).to(self.device)
        deess_filter = torch.ones_like(freq_bins)
        deess_filter[(freq_bins > 5000) & (freq_bins < 8000)] = self.deessing_ratio

        deessed_spec = torch.where(mag_spec > self.deessing_threshold,
                                   mag_spec / deess_filter.unsqueeze(0).unsqueeze(-1),
                                   mag_spec)

        deessed_stft = deessed_spec * (stft / (mag_spec + 1e-8))
        return torch.istft(deessed_stft, n_fft=self.n_fft, hop_length=self.hop_length,
                           window=self.window, length=waveform.shape[1])

    def apply_harmonic_exciter(self, waveform: torch.Tensor) -> torch.Tensor:
        stft = torch.stft(waveform, n_fft=self.n_fft, hop_length=self.hop_length,
                          window=self.window, return_complex=True)
        mag_spec = torch.abs(stft)
        phase_spec = torch.angle(stft)

        harmonic_spec = torch.zeros_like(mag_spec)
        harmonic_spec[:, 1:] = mag_spec[:, :-1]

        mixed_spec = mag_spec + self.harmonic_exciter_factor * harmonic_spec
        excited_stft = mixed_spec * torch.exp(1j * phase_spec)

        return torch.istft(excited_stft, n_fft=self.n_fft, hop_length=self.hop_length,
                           window=self.window, length=waveform.shape[1])
