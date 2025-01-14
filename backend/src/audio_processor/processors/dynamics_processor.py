# src/audio_processor/processors/dynamics_processor.py
import math
import torch
from .base_processor import BaseProcessor
from ..config import settings

class DynamicsProcessor(BaseProcessor):
    def __init__(self):
        super().__init__()
        self.comp_threshold = settings.COMP_THRESHOLD
        self.comp_ratio = settings.COMP_RATIO
        self.comp_attack_time = settings.COMP_ATTACK_TIME
        self.comp_release_time = settings.COMP_RELEASE_TIME

    def process(self, waveform: torch.Tensor) -> torch.Tensor:
        threshold = 10 ** (self.comp_threshold / 20)
        attack_time_constant = -1.0 / (self.sample_rate * self.comp_attack_time / 1000)
        release_time_constant = -1.0 / (self.sample_rate * self.comp_release_time / 1000)

        attack_coeff = torch.tensor(math.exp(attack_time_constant), device=self.device)
        release_coeff = torch.tensor(math.exp(release_time_constant), device=self.device)

        envelope = torch.abs(waveform)
        smoothed_envelope = torch.zeros_like(envelope)
        smoothed_envelope[:, 0] = envelope[:, 0]

        for t in range(1, envelope.shape[1]):
            coeff = torch.where(
                envelope[:, t] > smoothed_envelope[:, t - 1],
                attack_coeff,
                release_coeff
            )
            smoothed_envelope[:, t] = coeff * smoothed_envelope[:, t - 1] + \
                                      (1 - coeff) * envelope[:, t]

        gain_reduction = torch.where(
            smoothed_envelope > threshold,
            (threshold / (smoothed_envelope + 1e-8)) ** (self.comp_ratio - 1),
            torch.ones_like(smoothed_envelope)
        )

        return waveform * gain_reduction