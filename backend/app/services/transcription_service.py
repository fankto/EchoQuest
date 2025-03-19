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
        self.chunk_size = 20 * 1024 * 1024  # 20MB in bytes (reduced from 25MB to stay under Whisper's limit)
        self.chunk_duration = 180  # 3 minutes in seconds (reduced from 5 minutes to create smaller chunks)
        logger.info("Transcription service initialized")
    
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
                    .filter('volume', 2.0)  # Double the volume
                    .output(
                        output_path,
                        ar=48000,  # Set sample rate to 48kHz
                        ac=1,  # Convert to mono
                        acodec='pcm_s16le',  # 16-bit PCM
                    )
                    .overwrite_output()
                    .run(quiet=False, capture_stdout=True, capture_stderr=True)
                )
            )
            
            logger.info(f"Audio optimized: {input_path} -> {output_path}")
        except ffmpeg.Error as e:
            logger.error(f"FFmpeg error: stdout={e.stdout.decode() if e.stdout else 'None'}, stderr={e.stderr.decode() if e.stderr else 'None'}")
            raise
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
            
            # Always use whisper with alternating speakers
            logger.info("Using Whisper transcription with alternating speakers")
            
            # Fixed to 2 speakers
            speakers_count = 2
            
            # Transcribe each file
            all_segments = []
            total_duration = 0
            
            for filename in processed_filenames:
                file_path = os.path.join(settings.PROCESSED_DIR, filename)
                
                # Check file size before processing
                file_size = os.path.getsize(file_path)
                if file_size > self.chunk_size:
                    logger.info(f"File too large ({file_size} bytes), splitting into chunks")
                    
                    # Create temporary directory for chunks
                    chunks_dir = os.path.join(os.path.dirname(file_path), "chunks")
                    os.makedirs(chunks_dir, exist_ok=True)
                    
                    try:
                        # Split audio into chunks
                        chunk_paths = await self._split_audio_into_chunks(file_path, chunks_dir)
                        
                        # Process each chunk
                        current_time = 0
                        
                        for i, chunk_path in enumerate(chunk_paths):
                            logger.info(f"Processing chunk {i+1}/{len(chunk_paths)}")
                            
                            # Transcribe chunk
                            segments, chunk_duration = await self._transcribe_chunk(
                                chunk_path,
                                interview.language,
                                current_time,
                                i,
                                speakers_count
                            )
                            
                            all_segments.extend(segments)
                            current_time += chunk_duration
                            
                            # Clean up chunk file
                            os.remove(chunk_path)
                        
                        # Clean up chunks directory
                        os.rmdir(chunks_dir)
                        
                    except Exception as e:
                        # Clean up chunks directory in case of error
                        if os.path.exists(chunks_dir):
                            for chunk_file in os.listdir(chunks_dir):
                                os.remove(os.path.join(chunks_dir, chunk_file))
                            os.rmdir(chunks_dir)
                        raise e
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

    async def _transcribe_chunk(
        self,
        file_path: str,
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
        """
        try:
            # Get audio duration
            audio = AudioSegment.from_file(file_path)
            duration = len(audio) / 1000  # Convert to seconds
            
            # Transcribe with Whisper
            whisper_result = await self._transcribe_with_whisper(file_path, language)
            whisper_text = whisper_result.get("text", "")
            
            if not whisper_text:
                raise ValueError("Whisper returned empty transcript")
            
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
            raise
    
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

    async def _split_audio_into_chunks(self, input_path: str, output_dir: str) -> List[str]:
        """
        Split audio file into chunks of specified duration
        
        Args:
            input_path: Path to input audio file
            output_dir: Directory to store chunks
            
        Returns:
            List of chunk file paths
        """
        try:
            # Ensure output directory exists
            os.makedirs(output_dir, exist_ok=True)
            
            # Load audio file
            audio = AudioSegment.from_file(input_path)
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
                chunk_path = os.path.join(output_dir, chunk_filename)
                
                # Export chunk with high quality settings
                chunk.export(
                    chunk_path,
                    format="wav",
                    parameters=[
                        "-ar", "48000",  # Sample rate
                        "-ac", "1",      # Mono
                        "-acodec", "pcm_s16le"  # 16-bit PCM
                    ]
                )
                
                # Log chunk size
                chunk_size = os.path.getsize(chunk_path)
                logger.info(f"Created chunk {i+1}/{num_chunks}: {chunk_path} (size: {chunk_size/1024/1024:.2f}MB)")
                
                chunk_paths.append(chunk_path)
            
            return chunk_paths
            
        except Exception as e:
            logger.error(f"Error splitting audio into chunks: {e}")
            raise

    async def _transcribe_with_whisper(self, file_path: str, language: Optional[str] = None) -> Dict:
        """
        Transcribe audio using OpenAI's Whisper API
        
        Args:
            file_path: Path to audio file
            language: Language code (optional)
            
        Returns:
            Transcription result
        """
        logger.info(f"Transcribing with Whisper: {file_path}")
        
        if not settings.OPENAI_API_KEY:
            raise ValueError("OpenAI API key is not configured")
            
        # Read the file as binary
        with open(file_path, "rb") as audio_file:
            data = audio_file.read()
            
        headers = {
            "Authorization": f"Bearer {settings.OPENAI_API_KEY}"
        }
        
        try:
            # Create a form with the audio data
            files = {
                "file": (os.path.basename(file_path), data),
                "model": (None, "whisper-1"),
                "response_format": (None, "verbose_json"),
            }
            
            if language:
                files["language"] = (None, language)
                
            logger.info("Sending request to OpenAI Whisper API")
            
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    "https://api.openai.com/v1/audio/transcriptions",
                    headers=headers,
                    files=files
                )
                
                if response.status_code != 200:
                    error_message = f"Error transcribing with Whisper: Status code {response.status_code}, Response: {response.text}"
                    logger.error(error_message)
                    raise Exception(error_message)
                    
                result = response.json()
                logger.info(f"Whisper transcription completed successfully, length: {len(result.get('text', ''))}")
                return result
                
        except Exception as e:
            error_message = f"Error transcribing with Whisper: {str(e)}"
            logger.error(error_message)
            raise Exception(error_message)

    async def _transcribe_file_with_simulated_speakers(
        self, file_path: str, language: Optional[str] = None, speakers_count: Optional[int] = None
    ) -> Tuple[List[Dict], float]:
        """
        Use Whisper for transcription and alternate speakers for each sentence
        
        Args:
            file_path: Path to audio file
            language: Language code (optional)
            speakers_count: Number of speakers in the audio (optional, defaults to 2)
            
        Returns:
            Tuple of (transcript segments, duration in seconds)
        """
        try:
            # Get audio duration
            audio = AudioSegment.from_file(file_path)
            duration = len(audio) / 1000  # Convert to seconds
            
            # If file is too large, split into chunks
            if os.path.getsize(file_path) > self.chunk_size:
                logger.info(f"File too large ({os.path.getsize(file_path)} bytes), splitting into chunks")
                
                # Create temporary directory for chunks
                chunks_dir = os.path.join(os.path.dirname(file_path), "chunks")
                os.makedirs(chunks_dir, exist_ok=True)
                
                # Split audio into chunks
                chunk_paths = await self._split_audio_into_chunks(file_path, chunks_dir)
                
                # Process each chunk
                all_segments = []
                current_time = 0
                
                for i, chunk_path in enumerate(chunk_paths):
                    logger.info(f"Processing chunk {i+1}/{len(chunk_paths)}")
                    
                    # Transcribe chunk
                    whisper_result = await self._transcribe_with_whisper(chunk_path, language)
                    whisper_text = whisper_result.get("text", "")
                    
                    if not whisper_text:
                        raise ValueError(f"Whisper returned empty transcript for chunk {i+1}")
                    
                    # Split into sentences
                    import re
                    sentences = re.split(r'(?<=[.!?])\s+', whisper_text)
                    
                    # Calculate chunk duration
                    chunk_audio = AudioSegment.from_file(chunk_path)
                    chunk_duration = len(chunk_audio) / 1000
                    
                    # Create segments for this chunk
                    segment_duration = chunk_duration / len(sentences) if sentences else chunk_duration
                    
                    for j, sentence in enumerate(sentences):
                        if not sentence.strip():
                            continue
                        
                        # Alternate speakers
                        speaker_num = ((i * len(sentences) + j) % 2) + 1
                        
                        # Create segment with adjusted timing
                        segments.append({
                            "text": sentence.strip(),
                            "start_time": current_time + (j * segment_duration),
                            "end_time": current_time + ((j + 1) * segment_duration),
                            "speaker": f"Speaker {speaker_num}",
                            "words": []
                        })
                    
                    # Clean up chunk file
                    os.remove(chunk_path)
                    
                    # Update current time for next chunk
                    current_time += chunk_duration
                
                # Clean up chunks directory
                os.rmdir(chunks_dir)
                
                return segments, current_time
                
            else:
                # Process single file as before
                logger.info(f"Starting Whisper transcription with alternating speakers for file: {file_path}")
                
                # Step 1: Get full transcript from Whisper
                whisper_result = await self._transcribe_with_whisper(file_path, language)
                whisper_text = whisper_result.get("text", "")
                
                if not whisper_text:
                    raise ValueError("Whisper returned empty transcript")
                    
                logger.info(f"Got Whisper transcript of length {len(whisper_text)}")
                
                # Always use exactly 2 speakers as requested
                speakers_count = 2
                
                # Basic sentence splitting
                import re
                sentences = re.split(r'(?<=[.!?])\s+', whisper_text)
                
                # Create segments with alternating speakers (1 and 2)
                segments = []
                segment_duration = duration / len(sentences) if sentences else duration
                current_time = 0
                
                for i, sentence in enumerate(sentences):
                    if not sentence.strip():
                        continue
                    
                    # Simply alternate between speaker 1 and 2 for each sentence
                    speaker_num = (i % 2) + 1
                    
                    # Create segment
                    segments.append({
                        "text": sentence.strip(),
                        "start_time": current_time,
                        "end_time": current_time + segment_duration,
                        "speaker": f"Speaker {speaker_num}",
                        "words": []  # No word-level data available
                    })
                    
                    current_time += segment_duration
                    
                if not segments:  # Fallback if no sentences were created
                    segments = [{
                        "text": whisper_text,
                        "start_time": 0,
                        "end_time": duration,
                        "speaker": "Speaker 1",
                        "words": []
                    }]
                    
                return segments, duration
                
        except Exception as e:
            logger.error(f"Error in simulated speaker transcription: {str(e)}")
            # Create a single segment with the full text if possible
            try:
                whisper_result = await self._transcribe_with_whisper(file_path, language)
                whisper_text = whisper_result.get("text", "")
                
                if whisper_text:
                    segments = [{
                        "text": whisper_text,
                        "start_time": 0,
                        "end_time": duration,
                        "speaker": "Speaker 1",
                        "words": []
                    }]
                    return segments, duration
            except:
                pass
                
            # Create error segments as a last resort
            segments = [{
                "text": f"Error transcribing audio: {str(e)}",
                "start_time": 0,
                "end_time": duration,
                "speaker": "Speaker 1",
                "words": []
            }]
            return segments, duration


# Create singleton instance
transcription_service = TranscriptionService()