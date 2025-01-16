# src/transcription/transcription.py
import gc
import logging
from typing import Dict, Any, List
import librosa
import torch
from pyannote.core import Segment
from ..model_manager.manager import model_manager

logger = logging.getLogger(__name__)

class TranscriptionModule:
    def __init__(self):
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    def transcribe_and_diarize(
            self,
            audio_path: str,
            min_speakers: int = None,
            max_speakers: int = None
    ) -> List[Dict[str, Any]]:
        try:
            # Load audio
            audio = self.load_audio(audio_path)

            # Step 1: Run ASR using centralized pipeline
            logger.info("Starting ASR processing")
            asr_pipeline = model_manager.get_pipeline('asr')
            asr_result = asr_pipeline(
                audio["array"],
                return_timestamps=True
            )
            logger.info("ASR processing completed")

            # Step 2: Run diarization using centralized pipeline
            logger.info("Starting diarization")
            diarization_pipeline = model_manager.get_pipeline('diarization')
            diarization_result = diarization_pipeline(
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
            raise

    def load_audio(self, audio_path: str) -> Dict[str, Any]:
        """Load audio file"""
        logger.info(f"Loading audio from: {audio_path}")
        try:
            audio, sr = librosa.load(audio_path, sr=16000)
            logger.info(f"Audio loaded with sampling rate: {sr}")
            return {"array": audio, "sampling_rate": sr}
        except Exception as e:
            logger.error(f"Error loading audio: {str(e)}")
            raise

    def assign_speakers(self, asr_result, diarization_result):
        """Assign speakers to transcribed segments"""
        assigned_segments = []

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
        """Merge consecutive segments from the same speaker"""
        if not segments:
            return []

        merged = []
        current = segments[0].copy()  # Make a copy to avoid modifying the original

        for segment in segments[1:]:
            # Merge if same speaker and close in time (less than 1 second gap)
            if (current["speaker"] == segment["speaker"] and
                    segment["start"] - current["end"] < 1.0):
                current["text"] += " " + segment["text"]
                current["end"] = segment["end"]
            else:
                merged.append(current)
                current = segment.copy()  # Make a copy of the new segment

        merged.append(current)
        return merged

    def format_as_transcription(self, segments: List[Dict[str, Any]]) -> str:
        """Format segments as a readable transcription"""
        def format_timestamp(start: float, end: float) -> str:
            return f"({start:.1f}, {end:.1f})"

        return "\n\n".join([
            f"{segment['speaker']} {format_timestamp(segment['start'], segment['end'])} {segment['text']}"
            for segment in segments
        ])