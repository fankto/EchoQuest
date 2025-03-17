import asyncio
import json
import os
import uuid
from typing import Dict, List, Optional, Tuple

import ffmpeg
import httpx
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
        # Configure AssemblyAI with API key
        self.assembly_api_key = settings.ASSEMBLY_API_KEY
        self.assembly_base_url = "https://api.assemblyai.com/v2"
        logger.info(f"AssemblyAI API key configured: {'Valid key' if not self.assembly_api_key.startswith('your-') else 'Invalid key'}")
    
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
    
    async def _upload_file_to_assembly(self, file_path: str) -> str:
        """
        Upload a file to AssemblyAI for transcription
        
        Args:
            file_path: Path to the audio file
            
        Returns:
            The upload URL
        """
        # Read the file
        with open(file_path, "rb") as audio_file:
            data = audio_file.read()
        
        # Upload to AssemblyAI
        headers = {
            "authorization": self.assembly_api_key,
            "content-type": "application/json"
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.assembly_base_url}/upload",
                headers=headers,
                data=data
            )
            
            if response.status_code != 200:
                raise Exception(f"Error uploading file to AssemblyAI: {response.text}")
                
            upload_url = response.json()["upload_url"]
            return upload_url
    
    async def _create_transcription_job(self, upload_url: str, language: Optional[str] = None) -> str:
        """
        Create a transcription job in AssemblyAI
        
        Args:
            upload_url: The URL of the uploaded file
            language: The language code (optional)
            
        Returns:
            The ID of the transcription job
        """
        headers = {
            "authorization": self.assembly_api_key,
            "content-type": "application/json"
        }
        
        # Prepare transcription request
        data = {
            "audio_url": upload_url,
            "speaker_labels": True,  # Enable speaker diarization
            "word_boost": ["interview", "question", "answer"],  # Boost relevant words
            "punctuate": True,
            "format_text": True,
            "dual_channel": False,  # Set to True for two-channel audio
        }
        
        if language:
            data["language_code"] = language
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.assembly_base_url}/transcript",
                json=data,
                headers=headers
            )
            
            if response.status_code != 200:
                raise Exception(f"Error creating transcription job: {response.text}")
                
            return response.json()["id"]
    
    async def _get_transcription_result(self, transcript_id: str) -> Dict:
        """
        Get the result of a transcription job
        
        Args:
            transcript_id: The ID of the transcription job
            
        Returns:
            The transcription result
        """
        headers = {
            "authorization": self.assembly_api_key
        }
        
        # Poll until the transcription is complete
        max_retries = 60  # 10 minute timeout (60 * 10 seconds)
        retry_count = 0
        
        while retry_count < max_retries:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.assembly_base_url}/transcript/{transcript_id}",
                    headers=headers
                )
                
                if response.status_code != 200:
                    raise Exception(f"Error getting transcription result: {response.text}")
                    
                result = response.json()
                status = result.get("status")
                
                if status == "completed":
                    return result
                elif status == "error":
                    raise Exception(f"Transcription failed: {result.get('error')}")
                
                # Wait before retrying
                await asyncio.sleep(10)
                retry_count += 1
        
        raise Exception("Transcription timed out")
    
    async def _transcribe_file(
        self, file_path: str, language: Optional[str] = None
    ) -> Tuple[List[Dict], float]:
        """
        Transcribe a single audio file using AssemblyAI
        
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
            if not self.assembly_api_key or self.assembly_api_key.startswith("your-"):
                logger.warning("Using mock transcription as AssemblyAI API key is not configured properly")
                segments = [{
                    "text": "This is a mock transcript. To get real transcriptions, please set a valid AssemblyAI API key in your .env file.",
                    "start_time": 0,
                    "end_time": duration,
                    "speaker": "Speaker",
                }]
                return segments, duration
            
            # Upload file to AssemblyAI
            upload_url = await self._upload_file_to_assembly(file_path)
            
            # Create transcription job
            transcript_id = await self._create_transcription_job(upload_url, language)
            
            # Get transcription result
            transcription = await self._get_transcription_result(transcript_id)
            
            # Convert AssemblyAI format to our segment format
            segments = []
            
            if "utterances" in transcription:
                for utterance in transcription["utterances"]:
                    # AssemblyAI provides start and end times in milliseconds, we convert to seconds
                    start_time = utterance["start"] / 1000
                    end_time = utterance["end"] / 1000
                    text = utterance["text"]
                    speaker = f"Speaker {utterance['speaker']}"
                    
                    # Extract word-level data if available
                    words = []
                    if "words" in transcription:
                        # Filter words that belong to this utterance
                        utterance_words = [
                            word for word in transcription["words"]
                            if word["start"] >= utterance["start"] and word["end"] <= utterance["end"]
                        ]
                        
                        for word in utterance_words:
                            words.append({
                                "word": word["text"],
                                "start": word["start"] / 1000,
                                "end": word["end"] / 1000,
                                "confidence": word.get("confidence", 1.0)
                            })
                    
                    segments.append({
                        "text": text,
                        "start_time": start_time,
                        "end_time": end_time,
                        "speaker": speaker,
                        "words": words
                    })
            else:
                # Fallback if no utterances are available
                segments.append({
                    "text": transcription.get("text", "No transcription available"),
                    "start_time": 0,
                    "end_time": duration,
                    "speaker": "Speaker 1",
                    "words": []
                })
            
            return segments, duration
        except Exception as e:
            logger.error(f"Error transcribing file {file_path}: {e}")
            # Create error segments
            segments = [{
                "text": f"Error transcribing audio: {str(e)}",
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