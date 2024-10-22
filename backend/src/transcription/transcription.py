# src/transcription/transcription.py
import logging
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
    def __init__(self, asr_model: str = "openai/whisper-large-v3-turbo",
                 device: str = "cuda" if torch.cuda.is_available() else "cpu"):
        self.device = device
        self.asr_model_name = asr_model
        self.asr_pipeline = None
        self.diarization_pipeline = None

    def load_models(self):
        logger.info("Loading ASR and diarization models")

        # Load ASR model (Whisper) with return_timestamps=True
        self.asr_pipeline = pipeline(
            "automatic-speech-recognition",
            model=self.asr_model_name,
            device=self.device,
            generate_kwargs={"return_timestamps": True}
        )

        # Load diarization pipeline
        self.diarization_pipeline = DiarizationPipeline.from_pretrained(
            "pyannote/speaker-diarization-3.1"
        )

        logger.info("Models loaded successfully")


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
            # Load audio
            audio = self.load_audio(audio_path)
            logger.info(f"Audio loaded: shape={audio['array'].shape}, dtype={audio['array'].dtype}")

            # Load the ASR and diarization models
            self.load_models()

            # Run the ASR pipeline with return_timestamps=True
            logger.info("Running ASR pipeline with return_timestamps=True")
            asr_result = self.asr_pipeline(audio["array"], return_timestamps=True)
            logger.info(f"ASR result: {asr_result}")

            # Check for chunks
            if 'chunks' not in asr_result or not asr_result['chunks']:
                logger.error("ASR pipeline returned empty chunks.")
                raise ValueError("ASR pipeline failed to transcribe audio with timestamps.")

            # Run the diarization pipeline
            logger.info("Running diarization pipeline")
            diarization_result = self.diarization_pipeline(audio_path, min_speakers=min_speakers, max_speakers=max_speakers)
            logger.info(f"Diarization result: {diarization_result}")

            # Assign speakers to ASR chunks
            logger.info("Assigning speakers to ASR chunks")
            assigned_segments = self.assign_speakers(asr_result, diarization_result)

            # Merge segments if necessary
            merged_segments = self.merge_segments(assigned_segments)

            return merged_segments
        except Exception as e:
            logger.error(f"Error in transcribe_and_diarize: {str(e)}")
            logger.error(traceback.format_exc())
            raise
        finally:
            # Unload the models and clean up memory
            self.unload_model()

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
