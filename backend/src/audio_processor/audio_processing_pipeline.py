# src/audio_processor/audio_processing_pipeline.py
import os

import torch
import torchaudio

from .audio_processor import AudioProcessor
from .config import settings
from .exceptions import AudioLoadError


class AudioProcessingPipeline:
    def __init__(self):
        self.audio_processor = AudioProcessor()

    def process(self, file_path: str):
        try:
            waveform, sample_rate = torchaudio.load(file_path)
            original_duration = waveform.shape[1] / sample_rate

            processed_waveform = self.audio_processor.process(waveform, sample_rate)
            processed_duration = processed_waveform.shape[1] / settings.SAMPLE_RATE

            file_info = {
                "original_filename": os.path.basename(file_path),
                "original_duration": original_duration,
                "processed_duration": processed_duration,
                "sample_rate": settings.SAMPLE_RATE
            }

            return processed_waveform, file_info
        except Exception as e:
            error_message = f"Error processing audio: {str(e)}"
            raise AudioLoadError(error_message)

    def save_processed_audio(self, waveform: torch.Tensor, output_path: str):
        output_path = os.path.splitext(output_path)[0] + '.wav'
        self.audio_processor.save_processed_audio(waveform, output_path)
