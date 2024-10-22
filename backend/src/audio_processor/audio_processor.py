# src/audio_processor/audio_processor.py
import logging
import math

import torch
import torchaudio

from .config import settings

logger = logging.getLogger(__name__)


class AudioProcessor:
    def __init__(self):
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.sample_rate = settings.SAMPLE_RATE
        self.n_fft = settings.N_FFT
        self.hop_length = settings.HOP_LENGTH
        self.noise_reduction_factor = settings.NOISE_REDUCTION_FACTOR
        self.vad_threshold = settings.VAD_THRESHOLD
        self.comp_threshold = settings.COMP_THRESHOLD
        self.comp_ratio = settings.COMP_RATIO
        self.comp_attack_time = settings.COMP_ATTACK_TIME
        self.comp_release_time = settings.COMP_RELEASE_TIME
        self.min_bands = settings.MIN_BANDS
        self.max_bands = settings.MAX_BANDS
        self.multiband_chunk_duration = settings.MULTIBAND_CHUNK_DURATION
        self.equalizer_bands = torch.tensor(settings.EQUALIZER_BANDS, device=self.device)
        self.equalizer_gains = torch.tensor(settings.EQUALIZER_GAINS, device=self.device)
        self.deessing_threshold = settings.DEESSING_THRESHOLD
        self.deessing_ratio = settings.DEESSING_RATIO
        self.silence_threshold_percentile = settings.SILENCE_THRESHOLD_PERCENTILE
        self.harmonic_exciter_factor = settings.HARMONIC_EXCITER_FACTOR
        self.window = torch.hann_window(self.n_fft).to(self.device)

    def process(self, waveform: torch.Tensor, original_sample_rate: int) -> torch.Tensor:
        try:
            waveform = waveform.to(self.device)
            logger.debug(f"Starting audio processing. Input shape: {waveform.shape}")

            if original_sample_rate != self.sample_rate:
                waveform = torchaudio.functional.resample(waveform, original_sample_rate, self.sample_rate)

            if waveform.shape[0] > 1:
                waveform = torch.mean(waveform, dim=0, keepdim=True)

            waveform = self.spectral_subtraction(waveform)
            logger.debug(f"Waveform shape after spectral subtraction: {waveform.shape}")

            waveform = self.remove_silence(waveform)
            logger.debug(f"Waveform shape after silence removal: {waveform.shape}")

            waveform = self.apply_compression(waveform)
            logger.debug(f"Waveform shape after compression: {waveform.shape}")

            waveform = self.apply_equalization(waveform)
            logger.debug(f"Waveform shape after equalization: {waveform.shape}")

            waveform = self.apply_deessing(waveform)
            logger.debug(f"Waveform shape after de-essing: {waveform.shape}")

            # waveform = self.apply_multiband_compression(waveform)
            logger.debug(f"Waveform shape after multiband compression: {waveform.shape}")

            waveform = self.apply_harmonic_exciter(waveform)
            logger.debug(f"Waveform shape after harmonic exciter: {waveform.shape}")

            # Normalization
            max_val = torch.max(torch.abs(waveform))
            if max_val > 0:
                waveform = waveform / max_val * 0.99

            # Final shape check
            if waveform.dim() != 2:
                logger.warning(f"Unexpected waveform shape after processing: {waveform.shape}. Reshaping to 2D.")
                waveform = waveform.view(1, -1)

            return waveform.cpu()
        except Exception as e:
            logger.error(f"Error in audio processing: {str(e)}")
            return waveform.cpu()

    def spectral_subtraction(self, waveform: torch.Tensor) -> torch.Tensor:
        logger.debug(f"Starting spectral subtraction.")
        stft = torch.stft(waveform, n_fft=self.n_fft, hop_length=self.hop_length,
                          window=self.window, return_complex=True)
        mag_spec = torch.abs(stft)

        noise_estimate = torch.mean(mag_spec[:, :, :10], dim=2, keepdim=True)
        cleaned_spec = torch.max(mag_spec - self.noise_reduction_factor * noise_estimate, torch.zeros_like(mag_spec))

        cleaned_stft = cleaned_spec * (stft / (mag_spec + 1e-8))
        cleaned_waveform = torch.istft(cleaned_stft, n_fft=self.n_fft, hop_length=self.hop_length,
                                       window=self.window, length=waveform.shape[1])

        return cleaned_waveform

    def remove_silence(self, waveform: torch.Tensor, frame_length: int = 1024, hop_length: int = 512) -> torch.Tensor:
        logger.debug(f"Starting silence removal.")
        if waveform.dim() == 1:
            waveform = waveform.unsqueeze(0)

        window = torch.hann_window(frame_length, device=self.device)
        stft = torch.stft(waveform, n_fft=frame_length, hop_length=hop_length, window=window, return_complex=True)
        rms = stft.abs().mean(dim=1)

        sorted_rms, _ = torch.sort(rms.flatten())
        threshold = sorted_rms[int(sorted_rms.numel() * self.silence_threshold_percentile)]

        mask = (rms > threshold).float()

        kernel_size = 5
        smoothing_kernel = torch.ones(1, 1, kernel_size, device=self.device) / kernel_size

        mask_3d = mask.unsqueeze(0)
        if mask_3d.dim() == 2:
            mask_3d = mask_3d.unsqueeze(0)

        smoothed_mask = torch.nn.functional.conv1d(mask_3d, smoothing_kernel, padding=kernel_size // 2).squeeze(0)

        interpolated_mask = torch.nn.functional.interpolate(smoothed_mask.unsqueeze(0), size=waveform.shape[-1],
                                                            mode='linear', align_corners=False).squeeze(0)

        masked_waveform = waveform * interpolated_mask

        return masked_waveform

    def apply_compression(self, waveform: torch.Tensor) -> torch.Tensor:
        logger.debug(f"Starting compression.")
        threshold = 10 ** (self.comp_threshold / 20)
        ratio = self.comp_ratio

        # Compute time constants as floats
        attack_time_constant = -1.0 / (self.sample_rate * self.comp_attack_time / 1000)
        release_time_constant = -1.0 / (self.sample_rate * self.comp_release_time / 1000)

        # Compute coefficients using math.exp and create tensors
        attack_coeff_value = math.exp(attack_time_constant)
        release_coeff_value = math.exp(release_time_constant)

        # Convert coefficients to tensors on the correct device
        attack_coeff = torch.tensor(attack_coeff_value, device=self.device)
        release_coeff = torch.tensor(release_coeff_value, device=self.device)

        # Compute the signal envelope
        envelope = torch.abs(waveform)
        smoothed_envelope = torch.zeros_like(envelope)
        smoothed_envelope[:, 0] = envelope[:, 0]

        # Process per sample
        for t in range(1, envelope.shape[1]):
            coeff = torch.where(
                envelope[:, t] > smoothed_envelope[:, t - 1],
                attack_coeff,
                release_coeff
            )
            smoothed_envelope[:, t] = coeff * smoothed_envelope[:, t - 1] + (1 - coeff) * envelope[:, t]

        # Compute gain reduction
        gain_reduction = torch.where(
            smoothed_envelope > threshold,
            (threshold / (smoothed_envelope + 1e-8)) ** (ratio - 1),
            torch.ones_like(smoothed_envelope)
        )

        # Apply gain reduction
        waveform_compressed = waveform * gain_reduction
        return waveform_compressed

    def apply_equalization(self, waveform: torch.Tensor) -> torch.Tensor:
        logger.debug(f"Starting equalization.")
        freq_bins = torch.fft.rfftfreq(self.n_fft, d=1 / self.sample_rate).to(self.device)
        eq_curve = torch.ones(freq_bins.shape[0], device=self.device)

        for freq, gain in zip(self.equalizer_bands, self.equalizer_gains):
            eq_curve += gain * torch.exp(-((freq_bins - freq) ** 2) / (2 * (freq / 5) ** 2))

        window = torch.hann_window(self.n_fft, device=self.device)
        window = window / window.sum()

        stft = torch.stft(waveform, n_fft=self.n_fft, hop_length=self.hop_length, window=window, return_complex=True)

        eq_stft = stft * eq_curve.unsqueeze(0).unsqueeze(-1)

        eq_waveform = torch.istft(eq_stft, n_fft=self.n_fft, hop_length=self.hop_length, window=window,
                                  length=waveform.shape[1])

        return eq_waveform

    def apply_deessing(self, waveform: torch.Tensor) -> torch.Tensor:
        logger.debug(f"Starting de-essing.")
        stft = torch.stft(waveform, n_fft=self.n_fft, hop_length=self.hop_length,
                          window=self.window, return_complex=True)
        mag_spec = torch.abs(stft)

        freq_bins = torch.fft.rfftfreq(self.n_fft, d=1 / self.sample_rate).to(self.device)
        deess_filter = torch.ones_like(freq_bins)
        deess_filter[(freq_bins > 5000) & (freq_bins < 8000)] = self.deessing_ratio

        deessed_spec = torch.where(mag_spec > self.deessing_threshold,
                                   mag_spec / deess_filter.unsqueeze(0).unsqueeze(-1), mag_spec)

        deessed_stft = deessed_spec * (stft / (mag_spec + 1e-8))
        deessed_waveform = torch.istft(deessed_stft, n_fft=self.n_fft,
                                       hop_length=self.hop_length,
                                       window=self.window, length=waveform.shape[1])
        return deessed_waveform

    def apply_multiband_compression(self, waveform: torch.Tensor) -> torch.Tensor:
        logger.info(f"Starting GPU-accelerated multiband compression. Input shape: {waveform.shape}")

        chunk_size = int(self.sample_rate * self.multiband_chunk_duration)
        num_chunks = (waveform.shape[1] + chunk_size - 1) // chunk_size
        logger.info(f"Number of chunks: {num_chunks}, Chunk size: {chunk_size}")

        waveform = waveform.to(self.device)

        result_waveform = torch.zeros_like(waveform)

        for chunk_idx in range(num_chunks):
            start = chunk_idx * chunk_size
            end = min((chunk_idx + 1) * chunk_size, waveform.shape[1])
            chunk = waveform[:, start:end]  # Shape: [1, chunk_length]

            bands = self.analyze_frequency_content(chunk)

            compressed_bands = []
            for low, high in bands:
                band = self.process_band(chunk, low, high)
                compressed_bands.append(band)

            compressed_chunk = torch.sum(torch.stack(compressed_bands), dim=0)
            compressed_chunk = torch.clamp(compressed_chunk, -1, 1)

            result_waveform[:, start:end] = compressed_chunk

        logger.info(f"Final result shape before clamping: {result_waveform.shape}")
        result_waveform = torch.clamp(result_waveform, -1, 1)
        logger.info(f"Final result shape after clamping: {result_waveform.shape}")

        return result_waveform

    def analyze_frequency_content(self, waveform: torch.Tensor):
        logger.debug(f"Analyzing frequency content.")
        fft = torch.fft.rfft(waveform, dim=-1)
        freqs = torch.fft.rfftfreq(waveform.size(-1), 1 / self.sample_rate).to(self.device)  # Shape: [N]
        magnitude = torch.abs(fft)

        cumsum = torch.cumsum(magnitude, dim=-1)
        total_energy = cumsum[:, -1]

        num_bands = int(torch.clamp(total_energy.log10().int(), self.min_bands, self.max_bands).item())

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

    def process_band(self, waveform: torch.Tensor, low: float, high: float) -> torch.Tensor:
        logger.debug(f"Processing band: {low} - {high} Hz")
        filtered = torchaudio.functional.bandpass_biquad(waveform, self.sample_rate, (low + high) / 2, Q=1.0)
        filtered = torch.clamp(filtered, -1, 1)

        compressed = self.apply_compression(filtered)
        compressed = torch.clamp(compressed, -1, 1)

        return compressed

    def apply_harmonic_exciter(self, waveform: torch.Tensor) -> torch.Tensor:
        logger.debug(f"Starting harmonic exciter.")
        stft = torch.stft(waveform, n_fft=self.n_fft, hop_length=self.hop_length,
                          window=self.window, return_complex=True)
        mag_spec = torch.abs(stft)
        phase_spec = torch.angle(stft)

        harmonic_spec = torch.zeros_like(mag_spec)
        harmonic_spec[:, 1:] = mag_spec[:, :-1]

        mixed_spec = mag_spec + self.harmonic_exciter_factor * harmonic_spec

        excited_stft = mixed_spec * torch.exp(1j * phase_spec)
        excited_waveform = torch.istft(excited_stft, n_fft=self.n_fft,
                                       hop_length=self.hop_length,
                                       window=self.window, length=waveform.shape[1])
        return excited_waveform

    def save_processed_audio(self, waveform: torch.Tensor, output_path: str):
        logger.debug(f"Saving processed audio to {output_path}")
        try:
            torchaudio.save(output_path, waveform.cpu(), self.sample_rate)
        except Exception as e:
            logger.warning(f"Error saving audio: {str(e)}")
