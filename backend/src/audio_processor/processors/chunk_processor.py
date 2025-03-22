# src/audio_processor/processors/chunk_processor.py
import gc
import logging
import multiprocessing as mp
import os
from concurrent.futures import ProcessPoolExecutor, as_completed

import numpy as np
import torch
import torch.backends.mkldnn
import torchaudio
from numba import jit

logger = logging.getLogger(__name__)


@jit(nopython=True)
def normalize_audio(audio: np.ndarray, target_peak: float = 0.99) -> np.ndarray:
    """Optimized audio normalization with consistent float32 dtype."""
    # Ensure input is float32
    audio = audio.astype(np.float32)
    max_val = np.max(np.abs(audio))
    if max_val > 0:
        return ((audio / max_val) * target_peak).astype(np.float32)
    return audio


@jit(nopython=True, parallel=True)
def apply_crossfade(chunk: np.ndarray, fade_in: np.ndarray = None, fade_out: np.ndarray = None) -> np.ndarray:
    """Apply crossfade to chunk using manual indexing for Numba compatibility."""
    # Create output array as float32
    output = np.zeros_like(chunk, dtype=np.float32)
    output[:] = chunk

    # Apply fade in if provided
    if fade_in is not None and len(fade_in) > 0:
        fade_length = len(fade_in)
        for i in range(fade_length):
            output[:, i] *= float(fade_in[i])  # Convert to float explicitly

    # Apply fade out if provided
    if fade_out is not None and len(fade_out) > 0:
        fade_length = len(fade_out)
        for i in range(fade_length):
            output[:, -(fade_length - i)] *= float(fade_out[i])  # Convert to float explicitly

    return output


class ChunkProcessor:
    def __init__(self, processor):
        self.processor = processor
        self.chunk_duration = 900  # seconds
        self.overlap_duration = 5  # seconds

        # STFT parameters
        self.n_fft = 2048
        self.hop_length = 512

        # Calculate chunk sizes in samples
        self.samples_per_chunk = int(self.chunk_duration * processor.sample_rate)
        self.samples_per_chunk = self.samples_per_chunk - (self.samples_per_chunk % self.hop_length)
        self.overlap_samples = int(self.overlap_duration * processor.sample_rate)
        self.overlap_samples = self.overlap_samples - (self.overlap_samples % self.hop_length)

        # Process management
        self.num_cpus = mp.cpu_count()
        self.num_processes = max(1, self.num_cpus - 1)
        self.num_threads = max(1, self.num_cpus // self.num_processes)

        self._setup_processing_env()

    def _setup_processing_env(self):
        """Configure processing environment."""
        if torch.backends.mkldnn.is_available():
            torch.backends.mkldnn.enabled = True
            logger.info("MKL-DNN optimization enabled")

        if torch.cuda.is_available():
            torch.cuda.empty_cache()
            torch.cuda.set_per_process_memory_fraction(0.75)
            torch.backends.cuda.matmul.allow_tf32 = True
            torch.backends.cudnn.allow_tf32 = True
            logger.info(f"CUDA enabled, device: {torch.cuda.get_device_name()}")

        os.environ['OMP_NUM_THREADS'] = str(self.num_threads)
        os.environ['MKL_NUM_THREADS'] = str(self.num_threads)

    def process_chunked(self, waveform: torch.Tensor, original_sample_rate: int) -> torch.Tensor:
        """Process audio in chunks using multiple CPU cores."""
        try:
            logger.info("Starting optimized multi-CPU processing")
            waveform = self._preprocess_waveform(waveform, original_sample_rate)
            chunks_data = self._prepare_chunks(waveform)
            result = self._process_chunks_parallel(chunks_data, waveform.shape[-1])
            return torch.from_numpy(result).to(torch.float32)
        except Exception as e:
            logger.error(f"Error in parallel processing: {str(e)}", exc_info=True)
            return waveform.cpu()

    def _preprocess_waveform(self, waveform: torch.Tensor, original_sample_rate: int) -> torch.Tensor:
        """Preprocess the input waveform."""
        waveform = waveform.cpu().to(torch.float32)
        if original_sample_rate != self.processor.sample_rate:
            waveform = torchaudio.functional.resample(
                waveform, original_sample_rate, self.processor.sample_rate)
        if waveform.shape[0] > 1:
            waveform = torch.mean(waveform, dim=0, keepdim=True)
        return waveform

    def _prepare_chunks(self, waveform: torch.Tensor) -> list:
        """Prepare chunks for parallel processing."""
        total_samples = waveform.shape[-1]
        total_samples = total_samples - (total_samples % self.hop_length)
        chunks_data = []
        start_idx = 0

        while start_idx < total_samples:
            end_idx = min(start_idx + self.samples_per_chunk, total_samples)
            end_idx = end_idx - ((end_idx - start_idx) % self.hop_length)
            chunk = waveform[:, start_idx:end_idx].numpy().astype(np.float32)  # Ensure float32

            chunks_data.append({
                'chunk': chunk,
                'start_idx': start_idx,
                'end_idx': end_idx,
                'device': self.processor.device,
                'sample_rate': self.processor.sample_rate,
                'n_fft': self.n_fft,
                'hop_length': self.hop_length
            })

            start_idx += self.samples_per_chunk - self.overlap_samples

        return chunks_data

    def _process_chunks_parallel(self, chunks_data: list, total_samples: int) -> np.ndarray:
        """Process chunks in parallel."""
        result = np.zeros((1, total_samples), dtype=np.float32)  # Ensure float32

        with ProcessPoolExecutor(max_workers=self.num_processes) as executor:
            future_to_chunk = {
                executor.submit(self._process_single_chunk, chunk_data): i
                for i, chunk_data in enumerate(chunks_data)
            }

            for future in as_completed(future_to_chunk):
                try:
                    processed_chunk, start_idx, end_idx = future.result()

                    # Prepare crossfade arrays
                    fade_in = np.linspace(0, 1, self.overlap_samples, dtype=np.float32) if start_idx > 0 else np.array(
                        [], dtype=np.float32)
                    fade_out = np.linspace(1, 0, self.overlap_samples,
                                           dtype=np.float32) if end_idx < total_samples else np.array([],
                                                                                                      dtype=np.float32)

                    processed_chunk = apply_crossfade(processed_chunk, fade_in, fade_out)
                    result[:, start_idx:end_idx] += processed_chunk

                    logger.info(f"Processed chunk {future_to_chunk[future] + 1}/{len(chunks_data)}")

                except Exception as e:
                    chunk_idx = future_to_chunk[future]
                    logger.error(f"Error processing chunk {chunk_idx}: {str(e)}", exc_info=True)
                    chunk_data = chunks_data[chunk_idx]
                    result[:, chunk_data['start_idx']:chunk_data['end_idx']] = chunk_data['chunk']

        return result

    @staticmethod
    def _process_single_chunk(chunk_data: dict) -> tuple:
        """Process a single chunk of audio."""
        try:
            torch.set_num_threads(1)  # Ensure single thread per process

            chunk_tensor = torch.from_numpy(chunk_data['chunk']).to(chunk_data['device'])

            # Spectral processing
            window = torch.hann_window(chunk_data['n_fft']).to(chunk_data['device'])
            spec = torch.stft(
                chunk_tensor,
                n_fft=chunk_data['n_fft'],
                hop_length=chunk_data['hop_length'],
                window=window,
                center=True,
                normalized=False,
                return_complex=True
            )

            spec = torch.view_as_real(spec)
            chunk_tensor = torch.istft(
                torch.view_as_complex(spec),
                n_fft=chunk_data['n_fft'],
                hop_length=chunk_data['hop_length'],
                window=window,
                center=True,
                normalized=False,
                length=chunk_tensor.shape[-1]
            )

            processed_chunk = chunk_tensor.cpu().numpy().astype(np.float32)  # Ensure float32
            processed_chunk = normalize_audio(processed_chunk)

            return processed_chunk, chunk_data['start_idx'], chunk_data['end_idx']

        except Exception as e:
            logger.error(f"Error in chunk processing: {str(e)}", exc_info=True)
            return chunk_data['chunk'], chunk_data['start_idx'], chunk_data['end_idx']

    def cleanup(self):
        """Clean up resources."""
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
        gc.collect()
