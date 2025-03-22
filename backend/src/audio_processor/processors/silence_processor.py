# src/audio_processor/processors/silence_processor.py
import torch
from .base_processor import BaseProcessor
from ..config import settings

class SilenceProcessor(BaseProcessor):
    def __init__(self):
        super().__init__()
        self.silence_threshold_percentile = settings.SILENCE_THRESHOLD_PERCENTILE

    def process(self, waveform: torch.Tensor, frame_length: int = 1024,
                hop_length: int = 512) -> torch.Tensor:
        if waveform.dim() == 1:
            waveform = waveform.unsqueeze(0)

        window = torch.hann_window(frame_length, device=self.device)
        stft = torch.stft(waveform, n_fft=frame_length, hop_length=hop_length,
                          window=window, return_complex=True)
        rms = stft.abs().mean(dim=1)

        sorted_rms, _ = torch.sort(rms.flatten())
        threshold = sorted_rms[int(sorted_rms.numel() * self.silence_threshold_percentile)]
        mask = (rms > threshold).float()

        kernel_size = 5
        smoothing_kernel = torch.ones(1, 1, kernel_size, device=self.device) / kernel_size
        mask_3d = mask.unsqueeze(0)
        if mask_3d.dim() == 2:
            mask_3d = mask_3d.unsqueeze(0)

        smoothed_mask = torch.nn.functional.conv1d(
            mask_3d, smoothing_kernel, padding=kernel_size // 2).squeeze(0)
        interpolated_mask = torch.nn.functional.interpolate(
            smoothed_mask.unsqueeze(0), size=waveform.shape[-1],
            mode='linear', align_corners=False).squeeze(0)

        return waveform * interpolated_mask