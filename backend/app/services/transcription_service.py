import asyncio
import os
from pathlib import Path
import uuid
from typing import Dict, List, Optional, Tuple, Any
import time
import tempfile

import ffmpeg
import httpx
from loguru import logger
from pydub import AudioSegment
from sqlalchemy.ext.asyncio import AsyncSession
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from app.core.config import settings
from app.core.exceptions import TranscriptionError, AudioProcessingError, ExternalServiceError
from app.crud.crud_interview import interview_crud
from app.models.models import Interview, InterviewStatus
from app.services.qdrant_service import QdrantService


class TranscriptionService:
    """Service for transcribing interview audio"""

    def __init__(self):
        self.qdrant_service = QdrantService()
        self.chunk_size = settings.AUDIO_CHUNK_SIZE
        self.chunk_duration = settings.AUDIO_CHUNK_DURATION
        # Ensure directories exist
        os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
        os.makedirs(settings.PROCESSED_DIR, exist_ok=True)
        logger.info("Transcription service initialized")

    async def process_audio(self, interview_id: str, db: AsyncSession) -> None:
        """
        Process audio for an interview

        Args:
            interview_id: ID of the interview
            db: Database session

        Raises:
            AudioProcessingError: If there's an error processing the audio
        """
        try:
            # Get interview
            interview = await interview_crud.get(db, id=interview_id)
            if not interview:
                raise AudioProcessingError(f"Interview {interview_id} not found")

            # Update status
            interview.status = InterviewStatus.PROCESSING
            await db.commit()

            # Process audio files
            if not interview.original_filenames:
                raise AudioProcessingError("No audio files found")

            original_filenames = interview.get_original_filenames()
            processed_filenames = []

            # Process each file
            for filename in original_filenames:
                # Source and destination paths
                source_path = Path(settings.UPLOAD_DIR) / filename
                processed_filename = f"processed_{uuid.uuid4()}.wav"
                dest_path = Path(settings.PROCESSED_DIR) / processed_filename

                # Process the audio file
                await self._optimize_audio(source_path, dest_path)
                processed_filenames.append(processed_filename)

            # Update interview
            interview.set_processed_filenames(processed_filenames)
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
            raise AudioProcessingError(f"Failed to process audio: {str(e)}")

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        retry=retry_if_exception_type(ffmpeg.Error)
    )
    async def _optimize_audio(self, input_path: Path, output_path: Path) -> None:
        """
        Optimize audio file for transcription

        Args:
            input_path: Path to input audio file
            output_path: Path to output audio file

        Raises:
            AudioProcessingError: If there's an error optimizing the audio
        """
        try:
            # Ensure output directory exists
            output_path.parent.mkdir(parents=True, exist_ok=True)

            # Use a temporary file first to avoid incomplete files
            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp_file:
                temp_path = temp_file.name

                # Use ffmpeg-python to process audio asynchronously
                loop = asyncio.get_event_loop()
                await loop.run_in_executor(
                    None,
                    lambda: (
                        ffmpeg
                        .input(str(input_path))
                        .filter('volume', 2.0)  # Double the volume
                        .output(
                            temp_path,
                            ar=48000,  # Set sample rate to 48kHz
                            ac=1,  # Convert to mono
                            acodec='pcm_s16le',  # 16-bit PCM
                        )
                        .overwrite_output()
                        .run(quiet=False, capture_stdout=True, capture_stderr=True)
                    )
                )

                # Move the temp file to the final destination
                os.replace(temp_path, output_path)

            logger.info(f"Audio optimized: {input_path} -> {output_path}")
        except ffmpeg.Error as e:
            error_message = f"FFmpeg error: stdout={e.stdout.decode() if e.stdout else 'None'}, stderr={e.stderr.decode() if e.stderr else 'None'}"
            logger.error(error_message)
            raise
        except Exception as e:
            error_message = f"Error optimizing audio {input_path}: {e}"
            logger.error(error_message)
            raise AudioProcessingError(error_message)

    async def transcribe_audio(self, interview_id: str, db: AsyncSession) -> None:
        """
        Transcribe audio for an interview

        Args:
            interview_id: ID of the interview
            db: Database session

        Raises:
            TranscriptionError: If there's an error transcribing the audio
        """
        try:
            # Get interview
            interview = await interview_crud.get(db, id=interview_id)
            if not interview:
                raise TranscriptionError(f"Interview {interview_id} not found")

            # Update status
            interview.status = InterviewStatus.TRANSCRIBING
            await db.commit()

            # Process audio files
            if not interview.processed_filenames:
                raise TranscriptionError("No processed audio files found")

            processed_filenames = interview.get_processed_filenames()

            # Always use whisper with alternating speakers
            logger.info("Using Whisper transcription with alternating speakers")

            # Fixed to 2 speakers
            speakers_count = 2

            # Transcribe each file
            all_segments = []
            total_duration = 0

            for filename in processed_filenames:
                file_path = Path(settings.PROCESSED_DIR) / filename

                # Check file size before processing
                file_size = file_path.stat().st_size
                if file_size > self.chunk_size:
                    logger.info(f"File too large ({file_size} bytes), splitting into chunks")
                    segments, duration = await self._process_large_file(
                        file_path, interview.language, speakers_count
                    )
                    all_segments.extend(segments)
                    total_duration += duration
                else:
                    # Process single file
                    segments, duration = await self._transcribe_chunk(
                        file_path,
                        interview.language,
                        0,
                        0,
                        speakers_count
                    )
                    all_segments.extend(segments)
                    total_duration += duration

            # Sort segments by start time
            all_segments.sort(key=lambda x: x["start_time"])

            # Generate full transcription text
            full_transcription = self._format_transcript(all_segments)

            # Update interview
            interview.set_transcript_segments(all_segments)
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
            raise TranscriptionError(f"Failed to transcribe audio: {str(e)}")

    async def _process_large_file(
            self,
            file_path: Path,
            language: Optional[str],
            speakers_count: int
    ) -> Tuple[List[Dict[str, Any]], float]:
        """
        Process a large audio file by splitting it into chunks

        Args:
            file_path: Path to the audio file
            language: Language code (optional)
            speakers_count: Number of speakers

        Returns:
            Tuple of (transcript segments, duration in seconds)

        Raises:
            TranscriptionError: If there's an error processing the large file
        """
        try:
            # Create temporary directory for chunks
            chunks_dir = Path(file_path.parent) / "chunks"
            chunks_dir.mkdir(exist_ok=True)

            try:
                # Split audio into chunks
                chunk_paths = await self._split_audio_into_chunks(file_path, chunks_dir)

                # Process each chunk
                all_segments = []
                current_time = 0

                for i, chunk_path in enumerate(chunk_paths):
                    logger.info(f"Processing chunk {i + 1}/{len(chunk_paths)}")

                    # Transcribe chunk
                    segments, chunk_duration = await self._transcribe_chunk(
                        chunk_path,
                        language,
                        current_time,
                        i,
                        speakers_count
                    )

                    all_segments.extend(segments)
                    current_time += chunk_duration

                    # Clean up chunk file
                    chunk_path.unlink(missing_ok=True)

                # Clean up chunks directory
                chunks_dir.rmdir()

                return all_segments, current_time

            except Exception as e:
                # Clean up chunks directory in case of error
                if chunks_dir.exists():
                    for chunk_file in chunks_dir.iterdir():
                        chunk_file.unlink(missing_ok=True)
                    chunks_dir.rmdir()
                raise e

        except Exception as e:
            logger.error(f"Error processing large file: {str(e)}")
            raise TranscriptionError(f"Failed to process large file: {str(e)}")

    @retry(
        stop=stop_after_attempt(settings.OPENAI_MAX_RETRIES),
        wait=wait_exponential(multiplier=settings.OPENAI_RETRY_DELAY, min=1, max=60),
        retry=retry_if_exception_type((httpx.HTTPError, httpx.TimeoutException))
    )
    async def _transcribe_chunk(
            self,
            file_path: Path,
            language: Optional[str],
            start_time: float,
            chunk_index: int,
            speakers_count: int
    ) -> Tuple[List[Dict], float]:
        """
        Transcribe a single chunk of audio

        Args:
            file_path: Path to audio file
            language: Language code (optional)
            start_time: Start time of this chunk in the original audio
            chunk_index: Index of this chunk (for speaker alternation)
            speakers_count: Number of speakers

        Returns:
            Tuple of (transcript segments, duration in seconds)

        Raises:
            TranscriptionError: If there's an error transcribing the chunk
        """
        try:
            # Get audio duration
            audio = AudioSegment.from_file(str(file_path))
            duration = len(audio) / 1000  # Convert to seconds

            # Transcribe with Whisper
            whisper_result = await self._transcribe_with_whisper(file_path, language)
            whisper_text = whisper_result.get("text", "")

            if not whisper_text:
                raise TranscriptionError("Whisper returned empty transcript")

            # Split into sentences
            import re
            sentences = re.split(r'(?<=[.!?])\s+', whisper_text)

            # Create segments
            segments = []
            segment_duration = duration / len(sentences) if sentences else duration

            for i, sentence in enumerate(sentences):
                if not sentence.strip():
                    continue

                # Alternate speakers
                speaker_num = ((chunk_index * len(sentences) + i) % speakers_count) + 1

                # Create segment with adjusted timing
                segments.append({
                    "text": sentence.strip(),
                    "start_time": start_time + (i * segment_duration),
                    "end_time": start_time + ((i + 1) * segment_duration),
                    "speaker": f"Speaker {speaker_num}",
                    "words": []
                })

            if not segments:  # Fallback if no sentences were created
                segments = [{
                    "text": whisper_text,
                    "start_time": start_time,
                    "end_time": start_time + duration,
                    "speaker": "Speaker 1",
                    "words": []
                }]

            return segments, duration

        except Exception as e:
            logger.error(f"Error transcribing chunk: {str(e)}")
            raise TranscriptionError(f"Failed to transcribe chunk: {str(e)}")

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

    async def _split_audio_into_chunks(self, input_path: Path, output_dir: Path) -> List[Path]:
        """
        Split audio file into chunks of specified duration

        Args:
            input_path: Path to input audio file
            output_dir: Directory to store chunks

        Returns:
            List of chunk file paths

        Raises:
            AudioProcessingError: If there's an error splitting the audio
        """
        try:
            # Ensure output directory exists
            output_dir.mkdir(parents=True, exist_ok=True)

            # Load audio file
            audio = AudioSegment.from_file(str(input_path))
            duration = len(audio) / 1000  # Convert to seconds

            # Calculate number of chunks needed
            num_chunks = int(duration / self.chunk_duration) + 1
            chunk_paths = []

            logger.info(f"Splitting audio into {num_chunks} chunks")

            # Split audio into chunks with overlap
            for i in range(num_chunks):
                # Add 1 second overlap at the start and end of each chunk
                # This helps prevent cutting words at chunk boundaries
                start_time = max(0, i * self.chunk_duration * 1000 - 1000)  # Convert to milliseconds
                end_time = min(len(audio), (i + 1) * self.chunk_duration * 1000 + 1000)

                # Extract chunk
                chunk = audio[start_time:end_time]

                # Generate chunk filename
                chunk_filename = f"chunk_{uuid.uuid4()}.wav"
                chunk_path = output_dir / chunk_filename

                # Export chunk with high quality settings
                chunk.export(
                    str(chunk_path),
                    format="wav",
                    parameters=[
                        "-ar", "48000",  # Sample rate
                        "-ac", "1",  # Mono
                        "-acodec", "pcm_s16le"  # 16-bit PCM
                    ]
                )

                # Log chunk size
                chunk_size = chunk_path.stat().st_size
                logger.info(
                    f"Created chunk {i + 1}/{num_chunks}: {chunk_path} (size: {chunk_size / 1024 / 1024:.2f}MB)")

                chunk_paths.append(chunk_path)

            return chunk_paths

        except Exception as e:
            logger.error(f"Error splitting audio into chunks: {e}")
            raise AudioProcessingError(f"Failed to split audio into chunks: {str(e)}")

    @retry(
        stop=stop_after_attempt(settings.OPENAI_MAX_RETRIES),
        wait=wait_exponential(multiplier=settings.OPENAI_RETRY_DELAY, min=1, max=60),
        retry=retry_if_exception_type((httpx.HTTPError, httpx.TimeoutException))
    )
    async def _transcribe_with_whisper(self, file_path: Path, language: Optional[str] = None) -> Dict:
        """
        Transcribe audio using OpenAI's Whisper API

        Args:
            file_path: Path to audio file
            language: Language code (optional)

        Returns:
            Transcription result

        Raises:
            TranscriptionError: If there's an error with the Whisper service
            ExternalServiceError: If there's an error with the OpenAI API
        """
        logger.info(f"Transcribing with Whisper: {file_path}")

        if not settings.OPENAI_API_KEY:
            raise TranscriptionError("OpenAI API key is not configured")

        # Read the file as binary
        with open(file_path, "rb") as audio_file:
            data = audio_file.read()

        headers = {
            "Authorization": f"Bearer {settings.OPENAI_API_KEY}"
        }

        try:
            # Create a form with the audio data
            files = {
                "file": (file_path.name, data),
                "model": (None, "whisper-1"),
                "response_format": (None, "verbose_json"),
            }

            if language:
                files["language"] = (None, language)

            logger.info("Sending request to OpenAI Whisper API")

            async with httpx.AsyncClient(timeout=120.0) as client:
                response = await client.post(
                    "https://api.openai.com/v1/audio/transcriptions",
                    headers=headers,
                    files=files
                )

                if response.status_code != 200:
                    error_detail = response.text
                    # Avoid exposing potentially sensitive error details in prod
                    if settings.ENVIRONMENT == "production":
                        error_detail = f"Error code: {response.status_code}"

                    raise ExternalServiceError(
                        "OpenAI Whisper",
                        f"Transcription failed with status {response.status_code}"
                    )

                result = response.json()
                logger.info(f"Whisper transcription completed successfully, length: {len(result.get('text', ''))}")
                return result

        except httpx.HTTPError as e:
            error_message = f"HTTP error with Whisper API: {str(e)}"
            logger.error(error_message)
            raise ExternalServiceError("OpenAI Whisper", "Connection error")
        except Exception as e:
            error_message = f"Error transcribing with Whisper: {str(e)}"
            logger.error(error_message)
            raise TranscriptionError(error_message)


# Create singleton instance
transcription_service = TranscriptionService()