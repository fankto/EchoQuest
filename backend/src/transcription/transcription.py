# src/transcription/transcription.py
import logging
import os
import threading
import traceback
import librosa
import torch
import gc
from typing import Dict, Any, List
from transformers import pipeline
from pyannote.audio import Pipeline as DiarizationPipeline
from pyannote.core import Segment

logger = logging.getLogger(__name__)

class TranscriptionModule:
    def __init__(self):
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.asr_pipeline = None
        self.diarization_pipeline = None
        self._model_lock = threading.Lock()

    def _load_asr_model(self):
        """Load ASR model with memory optimization"""
        if self.asr_pipeline is None:
            torch.cuda.empty_cache()
            self.asr_pipeline = pipeline(
                "automatic-speech-recognition",
                model="openai/whisper-large-v3-turbo",
                device=self.device,
                torch_dtype=torch.float16,  # Use fp16 to reduce memory
                generate_kwargs={"return_timestamps": True}
            )

    def _load_diarization_model(self):
        """Load diarization model with memory optimization"""
        if self.diarization_pipeline is None:
            torch.cuda.empty_cache()
            self.diarization_pipeline = DiarizationPipeline.from_pretrained(
                "pyannote/speaker-diarization-3.1",
                use_auth_token=os.getenv("HF_TOKEN")
            )


    def unload_model(self):
        logger.info(f"VRAM usage before unloading: {torch.cuda.memory_allocated() / 1024 ** 2:.2f} MB")

        # Delete the ASR and diarization models
        if self.asr_pipeline:
            del self.asr_pipeline
        self.asr_pipeline = None

        if self.diarization_pipeline:
            del self.diarization_pipeline
        self.diarization_pipeline = None

        # Trigger garbage collection
        gc.collect()

        # Clear CUDA cache if available
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
            torch.cuda.ipc_collect()

        logger.info(f"VRAM usage after unloading: {torch.cuda.memory_allocated() / 1024 ** 2:.2f} MB")

    def transcribe_and_diarize(self, audio_path: str, min_speakers: int = None, max_speakers: int = None) -> List[Dict[str, Any]]:
        try:
            with self._model_lock:
                # Load audio
                audio = self.load_audio(audio_path)

                # Step 1: Run ASR
                self._load_asr_model()
                asr_result = self.asr_pipeline(audio["array"], return_timestamps=True)

                # Unload ASR model before diarization
                self.unload_asr_model()
                torch.cuda.empty_cache()

                # Step 2: Run diarization
                self._load_diarization_model()
                diarization_result = self.diarization_pipeline(
                    audio_path,
                    min_speakers=min_speakers,
                    max_speakers=max_speakers
                )

                # Process results
                assigned_segments = self.assign_speakers(asr_result, diarization_result)
                merged_segments = self.merge_segments(assigned_segments)

                # Unload models
                self.unload_models()

                return merged_segments

        except Exception as e:
            logger.error(f"Error in transcribe_and_diarize: {str(e)}")
            logger.error(traceback.format_exc())
            self.unload_models()  # Ensure models are unloaded even on error
            raise

    def unload_asr_model(self):
        """Unload ASR model and clear memory"""
        if self.asr_pipeline:
            del self.asr_pipeline
            self.asr_pipeline = None
        torch.cuda.empty_cache()

    def unload_diarization_model(self):
        """Unload diarization model and clear memory"""
        if self.diarization_pipeline:
            del self.diarization_pipeline
            self.diarization_pipeline = None
        torch.cuda.empty_cache()

    def unload_models(self):
        """Unload all models and clear memory"""
        self.unload_asr_model()
        self.unload_diarization_model()
        gc.collect()
        torch.cuda.empty_cache()

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

        # For each ASR chunk, find the speaker with the maximum overlap
        for chunk in asr_result['chunks']:
            chunk_start, chunk_end = chunk['timestamp']
            chunk_segment = Segment(chunk_start, chunk_end)

            # Find overlapping diarization segments
            overlapping_segments = diarization_result.crop(chunk_segment, mode='intersection')

            if overlapping_segments:
                # Calculate overlap durations for each speaker
                speaker_durations = {}
                for segment, _, speaker in overlapping_segments.itertracks(yield_label=True):
                    overlap = segment & chunk_segment
                    if overlap:
                        overlap_duration = overlap.duration
                        if speaker in speaker_durations:
                            speaker_durations[speaker] += overlap_duration
                        else:
                            speaker_durations[speaker] = overlap_duration

                # Assign the speaker with the longest total overlap
                speaker = max(speaker_durations, key=speaker_durations.get)
            else:
                speaker = 'Unknown'

            assigned_segments.append({
                "text": chunk['text'],
                "start": chunk_start,
                "end": chunk_end,
                "speaker": speaker
            })
        return assigned_segments

    def merge_segments(self, segments: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        merged = []
        current = None
        for segment in segments:
            if current is None:
                current = segment
            elif current["speaker"] == segment["speaker"] and segment["start"] - current["end"] < 1.0:
                current["text"] += " " + segment["text"]
                current["end"] = segment["end"]
            else:
                merged.append(current)
                current = segment
        if current:
            merged.append(current)
        return merged

    def format_as_transcription(self, segments: List[Dict[str, Any]]) -> str:
        def tuple_to_string(start_end_tuple, ndigits=1):
            return str((round(start_end_tuple[0], ndigits), round(start_end_tuple[1], ndigits)))

        return "\n\n".join([
            f"{segment['speaker']} {tuple_to_string((segment['start'], segment['end']))} {segment['text']}"
            for segment in segments
        ])
