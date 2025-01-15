# src/audio_processor/processors/chunk_processor.py
import logging
from typing import List, Tuple

import torch
import torchaudio

logger = logging.getLogger(__name__)


class ChunkProcessor:
    def __init__(self, processor):
        """
        Initialize the chunk processor with the main audio processor.

        Args:
            processor: The main AudioProcessor instance
        """
        self.processor = processor
        self.chunk_duration = 900  # in seconds
        self.overlap_duration = 1  # overlap to avoid artifacts, in seconds

        # Configure CUDA memory management
        if torch.cuda.is_available():
            # Set strict memory limits
            torch.cuda.set_per_process_memory_fraction(0.75)  # Use only % of available VRAM
            torch.cuda.empty_cache()

            # Enable memory defragmentation
            import os
            os.environ['PYTORCH_CUDA_ALLOC_CONF'] = 'max_split_size_mb:512,expandable_segments:True'

        # Set CUDA memory configuration
        if torch.cuda.is_available():
            torch.cuda.set_per_process_memory_fraction(0.80)  # Use only % of available VRAM
            torch.cuda.empty_cache()  # Clear cache before starting

    def split_audio(self, waveform: torch.Tensor, sample_rate: int) -> List[Tuple[torch.Tensor, int, int]]:
        """
        Split audio into overlapping chunks.

        Returns:
            List of tuples containing (chunk, start_idx, end_idx)
        """
        chunk_samples = int(self.chunk_duration * sample_rate)
        overlap_samples = int(self.overlap_duration * sample_rate)
        total_samples = waveform.shape[-1]

        chunks = []
        start_idx = 0

        while start_idx < total_samples:
            end_idx = min(start_idx + chunk_samples, total_samples)
            chunk = waveform[:, start_idx:end_idx]
            chunks.append((chunk, start_idx, end_idx))
            start_idx += chunk_samples - overlap_samples

        return chunks

    def merge_chunks(self, chunks: List[Tuple[torch.Tensor, int, int]], total_length: int) -> torch.Tensor:
        """
        Merge processed chunks back together with crossfading in overlap regions.
        """
        result = torch.zeros((1, total_length), device=chunks[0][0].device)
        overlap_samples = int(self.overlap_duration * self.processor.sample_rate)

        for i, (chunk, start_idx, end_idx) in enumerate(chunks):
            # Create linear crossfade weights for overlapping regions
            if i > 0:  # Apply fade-in
                fade_in = torch.linspace(0, 1, overlap_samples, device=chunk.device)
                chunk[:, :overlap_samples] *= fade_in

            if i < len(chunks) - 1:  # Apply fade-out
                fade_out = torch.linspace(1, 0, overlap_samples, device=chunk.device)
                chunk[:, -overlap_samples:] *= fade_out

            result[:, start_idx:end_idx] += chunk

        return result

    def process_chunked(self, waveform: torch.Tensor, original_sample_rate: int) -> torch.Tensor:
        """
        Process audio in chunks to avoid memory issues.
        """
        try:
            logger.info("Starting chunked processing")

            # Pre-process on CPU
            waveform = waveform.cpu()
            if original_sample_rate != self.processor.sample_rate:
                waveform = torchaudio.functional.resample(
                    waveform, original_sample_rate, self.processor.sample_rate)
            if waveform.shape[0] > 1:
                waveform = torch.mean(waveform, dim=0, keepdim=True)

            # Initialize result tensor on CPU
            result = torch.zeros_like(waveform)

            # Calculate chunks
            chunk_samples = int(self.chunk_duration * self.processor.sample_rate)
            overlap_samples = int(self.overlap_duration * self.processor.sample_rate)
            total_samples = waveform.shape[-1]

            # Process chunks sequentially with explicit memory management
            start_idx = 0
            chunk_count = 0

            # Process chunks one by one
            while start_idx < total_samples:
                chunk_count += 1

                # Clear CUDA cache at the start of each iteration
                if torch.cuda.is_available():
                    torch.cuda.empty_cache()

                # Calculate chunk indices
                end_idx = min(start_idx + chunk_samples, total_samples)
                current_chunk = waveform[:, start_idx:end_idx]

                try:
                    # Process chunk with memory safeguards
                    logger.info(f"Processing chunk {chunk_count} ({start_idx / total_samples * 100:.1f}%)")

                    # Clear CUDA cache before processing each chunk
                    if torch.cuda.is_available():
                        torch.cuda.empty_cache()

                    processed_chunk = self.processor.process_chunk(current_chunk)

                    # Move processed chunk to CPU immediately
                    processed_chunk = processed_chunk.cpu()

                    # Apply crossfade
                    if start_idx > 0:  # Apply fade-in
                        fade_in = torch.linspace(0, 1, overlap_samples, device=processed_chunk.device)
                        processed_chunk[:, :overlap_samples] *= fade_in

                    if end_idx < total_samples:  # Apply fade-out
                        fade_out = torch.linspace(1, 0, overlap_samples, device=processed_chunk.device)
                        processed_chunk[:, -overlap_samples:] *= fade_out

                    # Add to result
                    result[:, start_idx:end_idx] += processed_chunk.cpu()

                except Exception as e:
                    logger.error(f"Error processing chunk {chunk_count}: {str(e)}")
                    result[:, start_idx:end_idx] += current_chunk  # Use original chunk on error

                # Update start_idx with overlap
                start_idx += chunk_samples - overlap_samples

                # Force garbage collection
                del current_chunk
                if 'processed_chunk' in locals():
                    del processed_chunk

            # Final normalization
            max_val = torch.max(torch.abs(result))
            if max_val > 0:
                result = result / max_val * 0.99

            return result

        except Exception as e:
            logger.error(f"Error in chunked processing: {str(e)}")
            return waveform.cpu()
