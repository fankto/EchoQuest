# src/transcription/transcription.py
import gc
import logging
import os
from typing import Dict, Any, List, Optional
import librosa
import numpy as np
import torch
from pyannote.core import Segment, Timeline, Annotation
from ..model_manager.manager import model_manager, settings

logger = logging.getLogger(__name__)

class TranscriptionModule:
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
        """Load audio with optimal settings"""
        logger.info(f"Loading audio from: {audio_path}")
        try:
            if not os.path.exists(audio_path):
                raise FileNotFoundError(f"Audio file not found: {audio_path}")

            file_size = os.path.getsize(audio_path) / (1024 * 1024)
            logger.info(f"Audio file size: {file_size:.2f} MB")

            audio, sr = librosa.load(
                audio_path,
                sr=16000,
                mono=True,
                dtype=np.float32
            )

            logger.info(f"Audio loaded successfully - Duration: {len(audio)/sr:.2f}s, Sample rate: {sr}Hz")

            if np.max(np.abs(audio)) < 0.001:
                logger.warning("Audio file may be silent or very quiet")

            return {"array": audio, "sampling_rate": sr}
        except Exception as e:
            logger.error(f"Error loading audio: {str(e)}", exc_info=True)
            raise

    def transcribe_and_diarize(
            self,
            audio_path: str,
            min_speakers: Optional[int] = None,
            max_speakers: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """Process full audio file with transcription and diarization"""
        try:
            logger.info(f"Starting transcription and diarization for: {audio_path}")

            # Load audio
            audio = self.load_audio(audio_path)

            # Get ASR pipeline
            logger.info("Initializing ASR pipeline")
            asr_pipeline = model_manager.get_pipeline('asr')
            if not asr_pipeline:
                raise RuntimeError("Failed to initialize ASR pipeline")

            # Run ASR on full file
            logger.info("Starting ASR processing")
            with torch.cuda.amp.autocast():
                asr_result = asr_pipeline(
                    audio["array"],
                    batch_size=settings.ASR_BATCH_SIZE,
                    return_timestamps=True
                )

            if not asr_result or 'chunks' not in asr_result:
                raise ValueError("ASR failed to produce valid results")

            logger.info(f"ASR completed successfully")

            # Get diarization pipeline
            logger.info("Initializing diarization pipeline")
            diarization_pipeline = model_manager.get_pipeline('diarization')
            if not diarization_pipeline:
                raise RuntimeError("Failed to initialize diarization pipeline")

            # Run diarization on full file
            logger.info("Starting diarization")
            with torch.cuda.amp.autocast():
                diarization_result = diarization_pipeline(
                    audio_path,
                    min_speakers=min_speakers,
                    max_speakers=max_speakers
                )

            if not isinstance(diarization_result, Annotation):
                raise ValueError("Diarization failed to produce valid results")

            logger.info("Diarization completed successfully")

            # Process and merge results
            logger.info("Processing and merging results")
            processed_segments = self._process_results(asr_result, diarization_result)

            return processed_segments

        except Exception as e:
            logger.error(f"Error in transcribe_and_diarize: {str(e)}", exc_info=True)
            raise
        finally:
            if torch.cuda.is_available():
                model_manager.unload_model('asr')
                model_manager.unload_model('diarization')
                torch.cuda.empty_cache()
                gc.collect()

    def _process_results(self, asr_result: Dict, diarization_result: Annotation) -> List[Dict[str, Any]]:
        """Process and merge ASR and diarization results"""
        try:
            processed_segments = []

            # Create timeline from diarization result
            diarization_timeline = Timeline([
                segment for segment, _, _ in diarization_result.itertracks(yield_label=True)
            ])

            # Process each ASR chunk
            for chunk in asr_result['chunks']:
                # Validate timestamp
                if not isinstance(chunk.get('timestamp'), (list, tuple)):
                    logger.warning(f"Invalid timestamp format in chunk: {chunk}")
                    continue

                start, end = chunk['timestamp']

                # Skip invalid timestamps
                if start is None or end is None or end <= 0 or start >= end:
                    logger.warning(f"Invalid timestamp values: start={start}, end={end}")
                    continue

                try:
                    # Create segment for current chunk
                    current_segment = Segment(start, end)

                    # Find overlapping speaker segments
                    overlapping = diarization_result.crop(current_segment)

                    # Determine dominant speaker
                    if not overlapping:
                        speaker = "UNKNOWN"
                    else:
                        speaker_durations = {}
                        for segment, track, speaker_label in overlapping.itertracks(yield_label=True):
                            duration = segment.duration
                            if duration > 0:  # Only count positive durations
                                speaker_durations[speaker_label] = speaker_durations.get(speaker_label, 0) + duration

                        if speaker_durations:
                            speaker = max(speaker_durations.items(), key=lambda x: x[1])[0]
                        else:
                            speaker = "UNKNOWN"

                    # Add processed segment
                    text = chunk['text'].strip()
                    if text:  # Only add segments that have text
                        processed_segments.append({
                            "text": text,
                            "start": float(start),
                            "end": float(end),
                            "speaker": speaker
                        })

                except Exception as segment_error:
                    logger.warning(f"Error processing segment: {str(segment_error)}")
                    continue

            # Sort segments by start time
            processed_segments.sort(key=lambda x: x['start'])

            # Merge adjacent segments from same speaker
            merged_segments = self._merge_segments(processed_segments)

            return merged_segments

        except Exception as e:
            logger.error(f"Error in _process_results: {str(e)}", exc_info=True)
            raise

    def _merge_segments(self, segments: List[Dict[str, Any]], max_gap: float = 1.0) -> List[Dict[str, Any]]:
        """Merge consecutive segments from the same speaker with small gaps"""
        if not segments:
            return []

        merged = []
        current = segments[0].copy()

        for next_segment in segments[1:]:
            # Check if segments should be merged
            if (current["speaker"] == next_segment["speaker"] and
                    next_segment["start"] - current["end"] <= max_gap):
                # Merge segments
                current["text"] += " " + next_segment["text"]
                current["end"] = next_segment["end"]
            else:
                # Start new segment
                merged.append(current)
                current = next_segment.copy()

        merged.append(current)
        return merged

    def format_as_transcription(self, segments: List[Dict[str, Any]]) -> str:
        """Format segments into a readable transcription"""
        if not segments:
            return ""

        formatted_text = []
        current_speaker = None

        for segment in segments:
            if segment["speaker"] != current_speaker:
                formatted_text.append(f"\n[{segment['speaker']}]")
                current_speaker = segment["speaker"]
            formatted_text.append(segment["text"])

        return " ".join(formatted_text).strip()