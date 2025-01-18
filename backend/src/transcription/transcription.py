# src/transcription/transcription.py
import gc
import logging
import os
from typing import Dict, Any, List, Optional

import librosa
import numpy as np
import torch
from pyannote.core import Segment, Annotation
import torchaudio

from ..model_manager.manager import model_manager

logger = logging.getLogger(__name__)


class TranscriptionModule:
    LANGUAGE_MODELS = {
        'gsw': 'nizarmichaud/whisper-large-v3-turbo-swissgerman',
        'default': 'openai/whisper-large-v3'
    }

    def __init__(self):
        logger.info("Initializing TranscriptionModule")
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        logger.info(f"Using device: {self.device}")
        self._setup_cuda_optimizations()

    def _setup_cuda_optimizations(self):
        if torch.cuda.is_available():
            logger.info("Setting up CUDA optimizations")
            try:
                torch.cuda.amp.autocast(enabled=True, dtype=torch.float16)
                logger.info("CUDA optimizations setup successfully")
            except Exception as e:
                logger.error(f"Error setting up CUDA optimizations: {str(e)}")
                raise

    def load_audio(self, audio_path: str) -> Dict[str, Any]:
        """Load audio without resampling"""
        try:
            waveform, sample_rate = torchaudio.load(audio_path)

            # Convert to mono if stereo
            if waveform.shape[0] > 1:
                waveform = torch.mean(waveform, dim=0, keepdim=True)

            return {
                "array": waveform.numpy().squeeze(),
                "sampling_rate": sample_rate
            }
        except Exception as e:
            logger.error(f"Error loading audio: {str(e)}", exc_info=True)
            raise

    def transcribe_and_diarize(
            self,
            audio_path: str,
            min_speakers: Optional[int] = None,
            max_speakers: Optional[int] = None,
            language: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        try:
            logger.info(f"Starting transcription and diarization for: {audio_path}")
            logger.info(f"Language setting: {language}")

            # Load audio
            audio = self.load_audio(audio_path)

            try:
                # Run diarization first
                logger.info("Starting diarization")
                diarization_pipeline = model_manager.get_pipeline('diarization')
                with torch.amp.autocast('cuda'):
                    diarization_result = diarization_pipeline(
                        audio_path,
                        min_speakers=min_speakers,
                        max_speakers=max_speakers,
                        num_speakers=None
                    )

                logger.info("Diarization completed successfully")

                # Unload diarization model immediately after use
                model_manager.unload_model('diarization')

                # Get ASR pipeline
                logger.info("Starting ASR processing")
                asr_pipeline = model_manager.get_pipeline('asr', language=language)

                # Configure generation parameters for full-file processing
                generate_kwargs = {
                    "max_new_tokens": 224,
                    "num_beams": 2,
                    "temperature": 0.0,
                    "no_speech_threshold": 0.6,
                    "logprob_threshold": -1.0,
                    "condition_on_prev_tokens": True,
                    "return_timestamps": True
                }

                # Add language parameter if not Swiss German
                if language and language != 'gsw':
                    generate_kwargs["language"] = language
                    generate_kwargs["task"] = "transcribe"

                # Process full file
                with torch.amp.autocast('cuda'):
                    asr_result = asr_pipeline(
                        audio["array"],
                        batch_size=1,  # Process as single batch
                        return_timestamps=True,
                        generate_kwargs=generate_kwargs
                    )

                logger.info("ASR completed successfully")

                # Process results
                processed_segments = self._process_results(asr_result, diarization_result)
                return processed_segments

            finally:
                # Ensure cleanup happens in the correct order
                self._cleanup()

        except Exception as e:
            logger.error(f"Error in transcribe_and_diarize: {str(e)}", exc_info=True)
            raise

    def _cleanup(self):
        """Cleanup resources after transcription"""
        try:
            # Unload models in specific order
            model_manager.unload_model('asr')
            model_manager.unload_model('diarization')

            # Force garbage collection
            gc.collect()

            if torch.cuda.is_available():
                # Synchronize CUDA
                torch.cuda.synchronize()

                # Clear CUDA cache
                with torch.cuda.device('cuda'):
                    torch.cuda.empty_cache()
                    torch.cuda.ipc_collect()

                # Reset stats
                torch.cuda.reset_peak_memory_stats()

                # Log memory state
                memory_allocated = torch.cuda.memory_allocated() / 1024**2
                memory_reserved = torch.cuda.memory_reserved() / 1024**2
                logger.info(f"Cleanup completed. Current CUDA memory allocated: {memory_allocated:.2f} MB")
                logger.info(f"Current CUDA memory reserved: {memory_reserved:.2f} MB")
        except Exception as e:
            logger.error(f"Error during cleanup: {str(e)}")
            raise

    def _process_results(self, asr_result: Dict, diarization_result: Annotation) -> List[Dict[str, Any]]:
        """Process and merge ASR and diarization results"""
        try:
            processed_segments = []

            for chunk in asr_result['chunks']:
                if not isinstance(chunk.get('timestamp'), (list, tuple)):
                    continue

                start, end = chunk['timestamp']
                if not (isinstance(start, (int, float)) and isinstance(end, (int, float)) and end > 0 and start < end):
                    continue

                # Create segment for current chunk
                current_segment = Segment(start, end)

                # Find overlapping speaker segments using Segment intersection
                overlapping_segments = []
                for segment, _, speaker_label in diarization_result.itertracks(yield_label=True):
                    # Use Segment's built-in intersection method
                    intersection = current_segment & segment
                    if intersection:  # If there's an overlap
                        overlapping_segments.append({
                            'speaker': speaker_label,
                            'duration': intersection.duration,
                            'segment': intersection
                        })

                # Determine dominant speaker based on overlap
                if not overlapping_segments:
                    speaker = "UNKNOWN"
                else:
                    # Sort by duration of overlap
                    overlapping_segments.sort(key=lambda x: x['duration'], reverse=True)
                    speaker = overlapping_segments[0]['speaker']

                # Add processed segment
                text = chunk['text'].strip()
                if text:  # Only add segments that have text
                    processed_segments.append({
                        "text": text,
                        "start": float(start),
                        "end": float(end),
                        "speaker": speaker
                    })

            # Sort segments by start time
            processed_segments.sort(key=lambda x: x['start'])

            # Merge adjacent segments from same speaker
            merged_segments = self._merge_segments(processed_segments)

            return merged_segments

        except Exception as e:
            logger.error(f"Error in _process_results: {str(e)}", exc_info=True)
            raise

    def _merge_segments(self, segments: List[Dict[str, Any]], max_gap: float = 1.0) -> List[Dict[str, Any]]:
        if not segments:
            return []

        merged = []
        current = segments[0].copy()
        min_segment_duration = 0.5  # Minimum segment duration

        for next_segment in segments[1:]:
            gap = next_segment["start"] - current["end"]
            segment_duration = current["end"] - current["start"]

            # Check if current segment is long enough
            if segment_duration < min_segment_duration:
                # For very short segments, try to merge with next regardless of speaker
                if gap <= max_gap:
                    current["text"] += " " + next_segment["text"]
                    current["end"] = next_segment["end"]
                    current["speaker"] = next_segment["speaker"]  # Take speaker from longer segment
                    continue

            # Normal merging logic
            if (current["speaker"] == next_segment["speaker"] and gap <= max_gap):
                # Merge segments
                current["text"] += " " + next_segment["text"]
                current["end"] = next_segment["end"]
            else:
                # Before adding, check if segment is significant
                if segment_duration >= min_segment_duration:
                    merged.append(current)
                current = next_segment.copy()

        # Don't forget the last segment
        if (current["end"] - current["start"]) >= min_segment_duration:
            merged.append(current)

        return merged

    def format_as_transcription(self, segments: List[Dict[str, Any]]) -> str:
        """Format segments into a readable transcription with timestamps"""
        if not segments:
            return ""

        formatted_text = []
        current_speaker = None

        for segment in segments:
            timestamp = f"[{segment['start']:.1f}s - {segment['end']:.1f}s]"
            if segment["speaker"] != current_speaker:
                formatted_text.append(f"\n[{segment['speaker']}] {timestamp}")
                current_speaker = segment["speaker"]
            else:
                formatted_text.append(timestamp)
            formatted_text.append(segment["text"])

        return " ".join(formatted_text).strip()
