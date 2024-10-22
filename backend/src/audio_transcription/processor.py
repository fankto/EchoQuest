# src/audio_transcription/processor.py
import logging
import os
import uuid

from fastapi import UploadFile

from .models import AudioTranscriptionResult
from ..audio_processor.audio_processing_pipeline import AudioProcessingPipeline
from ..audio_processor.config import settings
from ..transcription.transcription import TranscriptionModule

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class AudioProcessingError(Exception):
    pass


class TranscriptionError(Exception):
    pass


class AudioTranscriptionProcessor:
    def __init__(self):
        self.audio_pipeline = AudioProcessingPipeline()
        self.transcription_module = TranscriptionModule()

    async def process_and_transcribe(self, file: UploadFile) -> AudioTranscriptionResult:
        temp_file_path = None
        processed_file_path = None
        try:
            # Generate a unique filename
            unique_filename = f"{uuid.uuid4()}_{file.filename}"
            temp_file_path = os.path.join(settings.TEMP_DIR, unique_filename)

            logger.info(f"Saving uploaded file: {unique_filename}")
            with open(temp_file_path, "wb") as buffer:
                content = await file.read()
                buffer.write(content)

            # Process audio
            logger.info(f"Processing audio: {unique_filename}")
            processed_waveform, file_info = self.audio_pipeline.process(temp_file_path)

            if processed_waveform is None:
                raise AudioProcessingError("Failed to process audio")

            # Generate a unique ID for this processed audio
            process_id = str(uuid.uuid4())

            # Save the processed audio
            processed_file_path = os.path.join(settings.TEMP_DIR, f"processed_{process_id}.wav")
            self.audio_pipeline.save_processed_audio(processed_waveform, processed_file_path)

            # Transcribe the processed audio
            logger.info(f"Transcribing processed audio: processed_{process_id}.wav")
            transcription_result = self.transcription_module.transcribe(processed_file_path)

            if not transcription_result:
                raise TranscriptionError("Failed to transcribe audio")

            return AudioTranscriptionResult(
                process_id=process_id,
                file_info=file_info,
                transcription=transcription_result
            )

        except Exception as e:
            logger.error(f"Error in process_and_transcribe: {str(e)}")
            raise

        finally:
            logger.info(f"Cleaning up temporary files")
            if temp_file_path and os.path.exists(temp_file_path):
                os.remove(temp_file_path)
            if processed_file_path and os.path.exists(processed_file_path):
                os.remove(processed_file_path)
