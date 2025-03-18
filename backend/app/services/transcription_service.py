import asyncio
import json
import os
import uuid
from typing import Dict, List, Optional, Tuple

import assemblyai as aai  # Add AssemblyAI SDK import
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
        # Configure AssemblyAI SDK
        aai.settings.api_key = self.assembly_api_key
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
            
            # Get speaker count from metadata if available
            speakers_count = None
            transcription_method = "whisper"  # Default to whisper approach - changed from hybrid to more reliable
            
            if interview.metadata and isinstance(interview.metadata, dict):
                # Check if a specific transcription method is requested
                requested_method = interview.metadata.get("transcription_method")
                if requested_method in ["assemblyai", "whisper", "hybrid"]:
                    transcription_method = requested_method
                    logger.info(f"Using requested transcription method: {transcription_method}")
                
                # Get speakers count if available
                speakers_count = interview.metadata.get("speakers_count")
                if speakers_count:
                    try:
                        speakers_count = int(speakers_count)
                        logger.info(f"Using speaker count from metadata: {speakers_count}")
                    except (ValueError, TypeError):
                        logger.warning(f"Invalid speakers_count in metadata: {speakers_count}, ignoring")
                        speakers_count = None
            
            # Transcribe each file
            all_segments = []
            total_duration = 0
            
            for filename in processed_filenames:
                file_path = os.path.join(settings.PROCESSED_DIR, filename)
                
                # Choose the transcription method based on settings
                if transcription_method == "assemblyai":
                    logger.info(f"Using AssemblyAI-only transcription for {file_path}")
                    segments, duration = await self._transcribe_file(
                        file_path, 
                        interview.language,
                        speakers_count=speakers_count
                    )
                else:
                    # Default to Whisper (more reliable) with simulated speakers
                    try:
                        logger.info(f"Using Whisper transcription with simulated speakers for {file_path}")
                        segments, duration = await self._transcribe_file_with_simulated_speakers(
                            file_path, 
                            interview.language,
                            speakers_count=speakers_count
                        )
                    except Exception as e:
                        logger.error(f"Whisper transcription failed: {str(e)}")
                        # Fall back to AssemblyAI as a last resort
                        logger.info(f"Falling back to AssemblyAI for {file_path}")
                        segments, duration = await self._transcribe_file(
                            file_path, 
                            interview.language,
                            speakers_count=speakers_count
                        )
                
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
        # Read the file as binary
        with open(file_path, "rb") as audio_file:
            data = audio_file.read()
        
        # Set up the proper headers for uploading binary data
        # NOTE: For binary uploads, we don't set content-type: application/json
        headers = {
            "authorization": self.assembly_api_key
        }
        
        try:
            # Create a client with increased timeout for large uploads
            async with httpx.AsyncClient(timeout=60.0) as client:
                logger.info(f"Starting upload of file {file_path} to AssemblyAI (size: {len(data)} bytes)")
                
                # Make the upload request with the audio file as binary data
                response = await client.post(
                    f"{self.assembly_base_url}/upload",
                    headers=headers,
                    content=data  # For binary data upload
                )
                
                if response.status_code != 200:
                    error_message = f"Error uploading file to AssemblyAI: Status code {response.status_code}, Response: {response.text}"
                    logger.error(error_message)
                    raise Exception(error_message)
                
                # Get the upload URL from the response
                response_json = response.json()
                upload_url = response_json.get("upload_url")
                
                if not upload_url:
                    error_message = f"No upload_url in AssemblyAI response: {response.text}"
                    logger.error(error_message)
                    raise Exception(error_message)
                
                logger.info(f"Successfully uploaded audio to AssemblyAI, got upload URL: {upload_url}")
                return upload_url
                
        except httpx.TimeoutException as e:
            error_message = f"Timeout when uploading to AssemblyAI: {str(e)}"
            logger.error(error_message)
            raise Exception(error_message) from e
        except httpx.RequestError as e:
            error_message = f"HTTP Request error when uploading to AssemblyAI: {str(e)}"
            logger.error(error_message)
            raise Exception(error_message) from e
    
    async def _create_transcription_job(self, upload_url: str, language: Optional[str] = None, speakers_expected: Optional[int] = None) -> str:
        """
        Create a transcription job in AssemblyAI
        
        Args:
            upload_url: The URL of the uploaded file
            language: The language code (optional)
            speakers_expected: Number of expected speakers (optional)
            
        Returns:
            The ID of the transcription job
        """
        # Set headers for the JSON request
        headers = {
            "authorization": self.assembly_api_key,
            "content-type": "application/json"
        }
        
        # Prepare transcription request according to AssemblyAI V2 API docs
        data = {
            "audio_url": upload_url,
            "speaker_labels": True,        # Enable speaker diarization
            "punctuate": True,             # Add punctuation
            "format_text": True,           # Clean up text (e.g., capitalization)
            "word_boost": ["interview", "question", "answer"],  # Boost relevant words
        }
        
        # Add speakers_expected if provided
        if speakers_expected and speakers_expected > 0:
            data["speakers_expected"] = speakers_expected
            
        # Add language if provided
        if language:
            data["language_code"] = language
            
        logger.info(f"Creating transcription job with config: {json.dumps(data)}")
            
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                logger.info(f"Creating transcription job for audio at {upload_url}")
                
                # Submit the transcription request
                response = await client.post(
                    f"{self.assembly_base_url}/transcript",
                    json=data,
                    headers=headers
                )
                
                if response.status_code != 200:
                    error_message = f"Error creating transcription job: Status code {response.status_code}, Response: {response.text}"
                    logger.error(error_message)
                    raise Exception(error_message)
                    
                # Extract the transcript ID
                response_json = response.json()
                transcript_id = response_json.get("id")
                
                if not transcript_id:
                    error_message = f"No transcript ID in AssemblyAI response: {response.text}"
                    logger.error(error_message)
                    raise Exception(error_message)
                
                logger.info(f"Successfully created transcription job with ID: {transcript_id}")
                return transcript_id
                
        except httpx.TimeoutException as e:
            error_message = f"Timeout when creating transcription job: {str(e)}"
            logger.error(error_message)
            raise Exception(error_message) from e
        except httpx.RequestError as e:
            error_message = f"HTTP Request error when creating transcription job: {str(e)}"
            logger.error(error_message)
            raise Exception(error_message) from e
    
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
        # Starting with shorter intervals and increasing over time
        max_retries = 30  # About 10 minutes total
        retry_count = 0
        wait_time = 10  # Start with 10 seconds
        
        while retry_count < max_retries:
            try:
                async with httpx.AsyncClient(timeout=15.0) as client:
                    # Get the current status of the transcription
                    response = await client.get(
                        f"{self.assembly_base_url}/transcript/{transcript_id}",
                        headers=headers
                    )
                    
                    if response.status_code != 200:
                        error_message = f"Error getting transcription result: Status code {response.status_code}, Response: {response.text}"
                        logger.error(error_message)
                        raise Exception(error_message)
                    
                    # Parse the response    
                    result = response.json()
                    status = result.get("status")
                    
                    # Handle different statuses
                    if status == "completed":
                        logger.info(f"Transcription job {transcript_id} completed successfully")
                        # Log the complete result to see what we're getting from AssemblyAI
                        logger.info(f"Raw AssemblyAI response: {json.dumps(result)}")
                        return result
                    elif status == "error":
                        error_message = f"Transcription failed with status 'error': {result.get('error')}"
                        logger.error(error_message)
                        raise Exception(error_message)
                    elif status == "processing":
                        logger.info(f"Transcription job {transcript_id} still processing (attempt {retry_count+1}/{max_retries})")
                    elif status == "queued":
                        logger.info(f"Transcription job {transcript_id} is queued (attempt {retry_count+1}/{max_retries})")
                    else:
                        logger.warning(f"Unexpected status '{status}' for transcription job {transcript_id}")
                
                # Wait before retrying - increase wait time slightly for progressive backoff
                await asyncio.sleep(wait_time)
                if retry_count < 5:
                    wait_time = min(wait_time + 5, 30)  # Increase up to 30 seconds max
                
                retry_count += 1
                
            except httpx.TimeoutException as e:
                error_message = f"Timeout when checking transcription status: {str(e)}"
                logger.warning(error_message)
                # Continue polling despite timeout errors
                await asyncio.sleep(wait_time)
                retry_count += 1
            except httpx.RequestError as e:
                error_message = f"HTTP Request error when checking transcription status: {str(e)}"
                logger.error(error_message)
                # Continue polling despite network errors
                await asyncio.sleep(wait_time)
                retry_count += 1
        
        error_message = f"Transcription timed out after {max_retries} attempts"
        logger.error(error_message)
        raise Exception(error_message)
    
    async def _transcribe_file(
        self, file_path: str, language: Optional[str] = None, speakers_count: Optional[int] = None
    ) -> Tuple[List[Dict], float]:
        """
        Transcribe a single audio file using AssemblyAI
        
        Args:
            file_path: Path to audio file
            language: Language code (optional)
            speakers_count: Number of speakers in the audio (optional)
            
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
            
            logger.info(f"Starting transcription process for file: {file_path}")
            
            # Setup transcription config
            config = aai.TranscriptionConfig(
                speaker_labels=True,
                punctuate=True,
                format_text=True,
                language_code=language if language else None,
            )
            
            # Set speakers_expected if provided
            if speakers_count and speakers_count > 0:
                # Use the SDK's speakers_expected parameter
                config.speakers_expected = speakers_count
                logger.info(f"Using speakers_expected={speakers_count} for better diarization")
                
            # Create transcriber
            transcriber = aai.Transcriber()
            
            # Run transcription (this is a blocking call, so we'll run it in an executor)
            logger.info(f"Submitting transcription job with SDK for file: {file_path}")
            
            # Run in executor to avoid blocking the event loop
            loop = asyncio.get_event_loop()
            transcript = await loop.run_in_executor(
                None, 
                lambda: transcriber.transcribe(file_path, config=config)
            )
            
            logger.info(f"Transcription completed successfully, got {len(transcript.utterances) if transcript.utterances else 0} utterances")
            
            # Convert to our segment format
            segments = []
            
            if transcript.utterances:
                for utterance in transcript.utterances:
                    # Convert times to seconds (SDK returns times in milliseconds)
                    start_time = utterance.start / 1000
                    end_time = utterance.end / 1000
                    text = utterance.text
                    speaker = f"Speaker {utterance.speaker}"
                    
                    # Extract word-level data if available
                    words = []
                    if transcript.words:
                        # Filter words that belong to this utterance
                        utterance_words = [
                            word for word in transcript.words
                            if word.start >= utterance.start and word.end <= utterance.end
                        ]
                        
                        for word in utterance_words:
                            words.append({
                                "word": word.text,
                                "start": word.start / 1000,
                                "end": word.end / 1000,
                                "confidence": word.confidence
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
                logger.warning("No utterances found in transcription, using fallback")
                segments.append({
                    "text": transcript.text if hasattr(transcript, "text") and transcript.text else "No transcription available",
                    "start_time": 0,
                    "end_time": duration,
                    "speaker": "Speaker 1",
                    "words": []
                })
            
            return segments, duration
            
        except Exception as e:
            import traceback
            error_traceback = traceback.format_exc()
            logger.error(f"Error transcribing file {file_path}:\n{str(e)}\n{error_traceback}")
            # Create error segments with more informative error message
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
        Use Whisper for transcription and simulate speaker changes
        
        Args:
            file_path: Path to audio file
            language: Language code (optional)
            speakers_count: Number of speakers in the audio (optional)
            
        Returns:
            Tuple of (transcript segments, duration in seconds)
        """
        try:
            # Get audio duration
            audio = AudioSegment.from_file(file_path)
            duration = len(audio) / 1000  # Convert to seconds
            
            logger.info(f"Starting Whisper transcription with simulated speakers for file: {file_path}")
            
            # Step 1: Get full transcript from Whisper
            whisper_result = await self._transcribe_with_whisper(file_path, language)
            whisper_text = whisper_result.get("text", "")
            
            if not whisper_text:
                raise ValueError("Whisper returned empty transcript")
                
            logger.info(f"Got Whisper transcript of length {len(whisper_text)}")
            
            # Step 2: Segment the transcript based on punctuation
            segments = []
            
            # Set a default number of speakers if not provided
            if not speakers_count or speakers_count < 2:
                speakers_count = 2  # Default to 2 speakers
                
            # Basic sentence splitting
            import re
            sentences = re.split(r'(?<=[.!?])\s+', whisper_text)
            
            # Combine short sentences
            min_sentence_length = 50  # characters
            combined_sentences = []
            current_sentence = ""
            
            for sentence in sentences:
                if len(current_sentence) + len(sentence) < min_sentence_length:
                    current_sentence += " " + sentence if current_sentence else sentence
                else:
                    if current_sentence:
                        combined_sentences.append(current_sentence)
                    current_sentence = sentence
                    
            if current_sentence:  # Add the last one
                combined_sentences.append(current_sentence)
                
            if not combined_sentences:  # Fallback if no sentences
                combined_sentences = [whisper_text]
                
            # Create segments with alternating speakers
            segment_duration = duration / len(combined_sentences)
            current_time = 0
            
            for i, sentence in enumerate(combined_sentences):
                # Alternate between speakers
                speaker_num = (i % speakers_count) + 1
                
                # Create segment
                segments.append({
                    "text": sentence.strip(),
                    "start_time": current_time,
                    "end_time": current_time + segment_duration,
                    "speaker": f"Speaker {speaker_num}",
                    "words": []  # No word-level data available
                })
                
                current_time += segment_duration
                
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
                "end_time": 10,
                "speaker": "System",
            }]
            return segments, 10


# Create singleton instance
transcription_service = TranscriptionService()