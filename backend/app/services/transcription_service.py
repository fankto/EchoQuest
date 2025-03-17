import asyncio
import json
import os
import uuid
from typing import Dict, List, Optional, Tuple

import ffmpeg
import openai
from loguru import logger
from pydub import AudioSegment
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.crud.crud_interview import interview_crud
from app.models.models import Interview, InterviewStatus
from app.services.qdrant_service import QdrantService


class TranscriptionService:
    """Service for transcribing interview audio"""
    
    def __init__(self):
        self.qdrant_service = QdrantService()
        # Ensure API key is set from settings
        openai.api_key = settings.OPENAI_API_KEY
        logger.info(f"OpenAI API key configured: {'Valid key' if not settings.OPENAI_API_KEY.startswith('your-') else 'Invalid key'}")
    
    async def process_audio(self, interview_id: str, db: AsyncSession) -> None:
        """
        Process audio for an interview
        
        Args:
            interview_id: ID of the interview
            db: Database session
        """
        try:
            # Get interview
            interview = await interview_crud.get(db, id=interview_id)
            if not interview:
                raise ValueError(f"Interview {interview_id} not found")
            
            # Update status
            interview.status = InterviewStatus.PROCESSING
            await db.commit()
            
            # Process audio files
            if not interview.original_filenames:
                raise ValueError("No audio files found")
            
            original_filenames = json.loads(interview.original_filenames)
            processed_filenames = []
            
            # Process each file
            for filename in original_filenames:
                # Source and destination paths
                source_path = os.path.join(settings.UPLOAD_DIR, filename)
                processed_filename = f"processed_{uuid.uuid4()}.wav"
                dest_path = os.path.join(settings.PROCESSED_DIR, processed_filename)
                
                # Process the audio file
                await self._optimize_audio(source_path, dest_path)
                processed_filenames.append(processed_filename)
            
            # Update interview
            interview.processed_filenames = json.dumps(processed_filenames)
            interview.status = InterviewStatus.PROCESSED
            await db.commit()
            
            logger.info(f"Audio processing completed for interview {interview_id}")
        except Exception as e:
            logger.error(f"Error processing audio for interview {interview_id}: {e}")
            # Update interview status
            interview = await interview_crud.get(db, id=interview_id)
            if interview:
                interview.status = InterviewStatus.ERROR
                interview.error_message = str(e)
                await db.commit()
            raise
    
    async def _optimize_audio(self, input_path: str, output_path: str) -> None:
        """
        Optimize audio file for transcription
        
        Args:
            input_path: Path to input audio file
            output_path: Path to output audio file
        """
        try:
            # Ensure output directory exists
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            
            # Use ffmpeg-python to process audio asynchronously
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None,
                lambda: (
                    ffmpeg
                    .input(input_path)
                    .filter('loudnorm')  # Normalize audio loudness
                    .filter('highpass', f='200')  # High-pass filter to reduce noise
                    .filter('acompressor')  # Apply compression
                    .output(
                        output_path,
                        ar=48000,  # Set sample rate to 48kHz
                        ac=1,  # Convert to mono
                        acodec='pcm_s16le',  # 16-bit PCM
                    )
                    .overwrite_output()
                    .run(quiet=True, capture_stdout=True, capture_stderr=True)
                )
            )
            
            logger.info(f"Audio optimized: {input_path} -> {output_path}")
        except Exception as e:
            logger.error(f"Error optimizing audio {input_path}: {e}")
            raise
    
    async def transcribe_audio(self, interview_id: str, db: AsyncSession) -> None:
        """
        Transcribe audio for an interview
        
        Args:
            interview_id: ID of the interview
            db: Database session
        """
        try:
            # Get interview
            interview = await interview_crud.get(db, id=interview_id)
            if not interview:
                raise ValueError(f"Interview {interview_id} not found")
            
            # Update status
            interview.status = InterviewStatus.TRANSCRIBING
            await db.commit()
            
            # Process audio files
            if not interview.processed_filenames:
                raise ValueError("No processed audio files found")
            
            processed_filenames = json.loads(interview.processed_filenames)
            
            # Transcribe each file
            all_segments = []
            total_duration = 0
            
            for filename in processed_filenames:
                file_path = os.path.join(settings.PROCESSED_DIR, filename)
                segments, duration = await self._transcribe_file(file_path, interview.language)
                
                # Adjust timestamps for segments
                for segment in segments:
                    segment["start_time"] += total_duration
                    segment["end_time"] += total_duration
                
                all_segments.extend(segments)
                total_duration += duration
            
            # Sort segments by start time
            all_segments.sort(key=lambda x: x["start_time"])
            
            # Generate full transcription text
            full_transcription = self._format_transcript(all_segments)
            
            # Update interview
            interview.transcript_segments = all_segments
            interview.transcription = full_transcription
            interview.duration = total_duration
            interview.status = InterviewStatus.TRANSCRIBED
            
            # Initialize chat tokens
            interview.remaining_chat_tokens = settings.DEFAULT_CHAT_TOKENS_PER_INTERVIEW
            
            await db.commit()
            
            # Index transcript in Qdrant for RAG
            await self.qdrant_service.index_transcript_chunks(str(interview.id), all_segments)
            
            logger.info(f"Transcription completed for interview {interview_id}")
        except Exception as e:
            logger.error(f"Error transcribing audio for interview {interview_id}: {e}")
            # Update interview status
            interview = await interview_crud.get(db, id=interview_id)
            if interview:
                interview.status = InterviewStatus.ERROR
                interview.error_message = str(e)
                await db.commit()
            raise
    
    async def _transcribe_file(
        self, file_path: str, language: Optional[str] = None
    ) -> Tuple[List[Dict], float]:
        """
        Transcribe a single audio file
        
        Args:
            file_path: Path to audio file
            language: Language code (optional)
            
        Returns:
            Tuple of (transcript segments, duration in seconds)
        """
        try:
            # Get audio duration
            audio = AudioSegment.from_file(file_path)
            duration = len(audio) / 1000  # Convert to seconds
            
            # For demo purposes, if the API key is not valid, create a mock transcript
            if not settings.OPENAI_API_KEY or settings.OPENAI_API_KEY.startswith("your-") or "your-openai-api-key" in settings.OPENAI_API_KEY:
                logger.warning("Using mock transcription as OpenAI API key is not configured properly")
                segments = [{
                    "text": "This is a mock transcript. To get real transcriptions, please set a valid OpenAI API key in your .env file.",
                    "start_time": 0,
                    "end_time": duration,
                    "speaker": "Speaker",
                }]
                return segments, duration
            
            # Open file
            with open(file_path, "rb") as audio_file:
                # Prepare options for OpenAI API
                options = {
                    "response_format": "verbose_json",
                }
                
                if language:
                    options["language"] = language
                
                # Transcribe with OpenAI - v0.28.1 doesn't have native async support
                loop = asyncio.get_event_loop()
                response = await loop.run_in_executor(
                    None, 
                    lambda: openai.Audio.transcribe("whisper-1", audio_file, **options)
                )
            
            # Extract segments
            segments = []
            if "segments" in response:
                for segment in response["segments"]:
                    segments.append({
                        "text": segment["text"],
                        "start_time": segment["start"],
                        "end_time": segment["end"],
                        "speaker": "Speaker",  # Default speaker label
                    })
            else:
                # Fallback if no segments are available
                segments.append({
                    "text": response["text"],
                    "start_time": 0,
                    "end_time": duration,
                    "speaker": "Speaker",  # Default speaker label
                })
            
            return segments, duration
        except Exception as e:
            logger.error(f"Error transcribing file {file_path}: {e}")
            # Create a mock transcript with the error message for debugging
            segments = [{
                "text": f"Error during transcription: {str(e)}. Please check backend logs and ensure OpenAI API key is configured correctly.",
                "start_time": 0,
                "end_time": 10,
                "speaker": "System",
            }]
            return segments, 10
    
    def _format_transcript(self, segments: List[Dict]) -> str:
        """
        Format transcript segments into readable text
        
        Args:
            segments: List of transcript segments
            
        Returns:
            Formatted transcript text
        """
        formatted_text = []
        current_speaker = None
        
        for segment in segments:
            speaker = segment.get("speaker", "Speaker")
            text = segment.get("text", "").strip()
            start_time = segment.get("start_time", 0)
            end_time = segment.get("end_time", 0)
            
            # Format timestamp
            timestamp = f"[{self._format_time(start_time)} - {self._format_time(end_time)}]"
            
            # Add speaker if changed
            if speaker != current_speaker:
                formatted_text.append(f"\n{speaker}: {timestamp} {text}")
                current_speaker = speaker
            else:
                formatted_text.append(f"{timestamp} {text}")
        
        return " ".join(formatted_text).strip()
    
    def _format_time(self, seconds: float) -> str:
        """Format seconds as MM:SS"""
        minutes = int(seconds // 60)
        seconds = int(seconds % 60)
        return f"{minutes:02d}:{seconds:02d}"


# Create singleton instance
transcription_service = TranscriptionService()