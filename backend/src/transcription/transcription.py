# src/transcription/transcription.py
import gc
import logging
import os
import threading
import traceback
from typing import Dict, Any, List

import librosa
import torch
from pyannote.audio import Pipeline as DiarizationPipeline
from pyannote.core import Segment
from transformers import pipeline

logger = logging.getLogger(__name__)


class TranscriptionModule:
    def __init__(self):
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.asr_pipeline = None
        self.diarization_pipeline = None
        self._model_lock = threading.Lock()
        # Enable cuDNN autotuner
        if torch.cuda.is_available():
            torch.backends.cudnn.benchmark = True

    def _load_asr_model(self):
        """Load ASR model with optimized settings"""
        if self.asr_pipeline is None:
            torch.cuda.empty_cache()
            self.asr_pipeline = pipeline(
                "automatic-speech-recognition",
                model="openai/whisper-large-v3-turbo",
                device=self.device,
                torch_dtype=torch.float16,  # Use fp16 for better performance
                batch_size=4,  # Add reasonable batch size
                generate_kwargs={
                    "return_timestamps": True,
                    "task": "transcribe"  # Explicitly set task
                }
            )

    def _load_diarization_model(self):
        """Load diarization model with optimized settings"""
        if self.diarization_pipeline is None:
            torch.cuda.empty_cache()
            self.diarization_pipeline = DiarizationPipeline.from_pretrained(
                "pyannote/speaker-diarization-3.1",
                use_auth_token=os.getenv("HF_TOKEN")
            ).to(self.device)

    def transcribe_and_diarize(self, audio_path: str, min_speakers: int = None, max_speakers: int = None) -> List[
        Dict[str, Any]]:
        try:
            with self._model_lock:
                # Load models if not already loaded
                if self.asr_pipeline is None:
                    self._load_asr_model()
                if self.diarization_pipeline is None:
                    self._load_diarization_model()

                # Load audio
                audio = self.load_audio(audio_path)

                # Step 1: Run ASR
                logger.info("Starting ASR processing")
                asr_result = self.asr_pipeline(
                    audio["array"],
                    batch_size=4,  # Process in batches
                    return_timestamps=True
                )
                logger.info("ASR processing completed")

                # Step 2: Run diarization
                logger.info("Starting diarization")
                diarization_result = self.diarization_pipeline(
                    audio_path,
                    min_speakers=min_speakers,
                    max_speakers=max_speakers
                )
                logger.info("Diarization completed")

                # Process results
                assigned_segments = self.assign_speakers(asr_result, diarization_result)
                merged_segments = self.merge_segments(assigned_segments)

                return merged_segments

        except Exception as e:
            logger.error(f"Error in transcribe_and_diarize: {str(e)}")
            logger.error(traceback.format_exc())
            raise

        finally:
            # Always unload models after processing
            logger.info("Unloading models after transcription")
            self.unload_models()

    def unload_models(self):
        """Unload all models and clear memory"""
        logger.info(f"VRAM usage before unloading: {torch.cuda.memory_allocated() / 1024 ** 2:.2f} MB")

        if self.asr_pipeline:
            del self.asr_pipeline
            self.asr_pipeline = None

        if self.diarization_pipeline:
            del self.diarization_pipeline
            self.diarization_pipeline = None

        # Clear CUDA cache
        gc.collect()
        torch.cuda.empty_cache()
        if torch.cuda.is_available():
            torch.cuda.ipc_collect()

        logger.info(f"VRAM usage after unloading: {torch.cuda.memory_allocated() / 1024 ** 2:.2f} MB")

    def load_audio(self, audio_path: str) -> Dict[str, Any]:
        logger.info(f"Loading audio from: {audio_path}")
        try:
            audio, sr = librosa.load(audio_path, sr=16000)
            logger.info(f"Audio loaded with sampling rate: {sr}")
            return {"array": audio, "sampling_rate": sr}
        except Exception as e:
            logger.error(f"Error loading audio: {str(e)}")
            raise

    def assign_speakers(self, asr_result, diarization_result):
        assigned_segments = []

        # Process chunks from ASR result
        for chunk in asr_result['chunks']:
            chunk_start, chunk_end = chunk['timestamp']
            chunk_segment = Segment(chunk_start, chunk_end)

            # Find overlapping diarization segments
            overlapping_segments = diarization_result.crop(chunk_segment, mode='intersection')

            # Find the dominant speaker for this chunk
            if overlapping_segments:
                speaker_durations = {}
                for segment, _, speaker in overlapping_segments.itertracks(yield_label=True):
                    overlap = segment & chunk_segment
                    if overlap:
                        overlap_duration = overlap.duration
                        speaker_durations[speaker] = speaker_durations.get(speaker, 0) + overlap_duration

                # Assign the speaker with the longest overlap
                speaker = max(speaker_durations.items(), key=lambda x: x[1])[0]
            else:
                speaker = 'UNKNOWN'

            assigned_segments.append({
                "text": chunk['text'],
                "start": chunk_start,
                "end": chunk_end,
                "speaker": speaker
            })

        return assigned_segments

    def merge_segments(self, segments: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        if not segments:
            return []

        merged = []
        current = segments[0]

        for segment in segments[1:]:
            # Merge if same speaker and close in time (less than 1 second gap)
            if (current["speaker"] == segment["speaker"] and
                    segment["start"] - current["end"] < 1.0):
                current["text"] += " " + segment["text"]
                current["end"] = segment["end"]
            else:
                merged.append(current)
                current = segment

        merged.append(current)
        return merged

    def format_as_transcription(self, segments: List[Dict[str, Any]]) -> str:
        def format_timestamp(start: float, end: float) -> str:
            return f"({start:.1f}, {end:.1f})"

        return "\n\n".join([
            f"{segment['speaker']} {format_timestamp(segment['start'], segment['end'])} {segment['text']}"
            for segment in segments
        ])
