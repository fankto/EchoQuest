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

            # Run diarization
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

            # Get ASR pipeline
            logger.info("Starting ASR processing")
            asr_pipeline = model_manager.get_pipeline('asr', language=language)

            # Configure generation parameters based on language
            generate_kwargs = {
                "max_new_tokens": 445,  # Reduced to account for special tokens
                "num_beams": 1,
                "condition_on_prev_tokens": False,
                "compression_ratio_threshold": 1.35,
                "temperature": (0.0, 0.2, 0.4, 0.6, 0.8, 1.0),
                "logprob_threshold": -1.0,
                "no_speech_threshold": 0.6,
                "return_timestamps": True,
            }

            # Only add language parameter if not Swiss German
            if language and language != 'gsw':
                generate_kwargs["language"] = language
                generate_kwargs["task"] = "transcribe"

            with torch.amp.autocast('cuda'):
                asr_result = asr_pipeline(
                    audio["array"],
                    return_timestamps=True,
                    chunk_length_s=30,
                    stride_length_s=1,
                    batch_size=8,
                    generate_kwargs=generate_kwargs
                )

            logger.info("ASR completed successfully")

            processed_segments = self._process_results(asr_result, diarization_result)
            return processed_segments

        except Exception as e:
            logger.error(f"Error in transcribe_and_diarize: {str(e)}", exc_info=True)
            raise
        finally:
            self._cleanup()

    def _cleanup(self):
        """Cleanup resources after transcription"""
        if torch.cuda.is_available():
            model_manager.unload_model('asr')
            model_manager.unload_model('diarization')
            torch.cuda.empty_cache()
            gc.collect()

    def _process_results(self, asr_result: Dict, diarization_result: Annotation) -> List[Dict[str, Any]]:
        """Process and merge ASR and diarization results"""
        try:
            processed_segments = []

            # Process each ASR chunk
            for chunk in asr_result['chunks']:
                if not isinstance(chunk.get('timestamp'), (list, tuple)):
                    continue

                start, end = chunk['timestamp']
                if not (isinstance(start, (int, float)) and isinstance(end, (int, float)) and end > 0 and start < end):
                    continue

                # Create segment for current chunk
                current_segment = Segment(start, end)

                # Find overlapping speaker segments using overlap()
                overlapping_segments = []
                for segment, _, speaker_label in diarization_result.itertracks(yield_label=True):
                    if segment.start <= end and segment.end >= start:
                        overlap_start = max(segment.start, start)
                        overlap_end = min(segment.end, end)
                        if overlap_end > overlap_start:
                            overlapping_segments.append({
                                'speaker': speaker_label,
                                'duration': overlap_end - overlap_start
                            })

                # Determine dominant speaker
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

    def _merge_segments(self, segments: List[Dict[str, Any]], max_gap: float = 0.5) -> List[Dict[str, Any]]:
        """Merge consecutive segments from the same speaker with small gaps"""
        if not segments:
            return []

        merged = []
        current = segments[0].copy()

        for next_segment in segments[1:]:
            gap = next_segment["start"] - current["end"]

            # Check if segments should be merged
            if (current["speaker"] == next_segment["speaker"] and gap <= max_gap):
                # Merge segments while preserving timing
                current["text"] += " " + next_segment["text"]
                current["end"] = next_segment["end"]
                current["duration"] = current["end"] - current["start"]
            else:
                # Start new segment
                merged.append(current)
                current = next_segment.copy()

        merged.append(current)

        # Final sort by start time to ensure order
        merged.sort(key=lambda x: x['start'])
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
