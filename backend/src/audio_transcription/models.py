# src/audio_transcription/models.py
from typing import Dict, Any, List

from pydantic import BaseModel


class AudioTranscriptionResult(BaseModel):
    process_id: str
    file_info: Dict[str, Any]
    transcription: List[str]

class TranscriptionUpdate(BaseModel):
    transcription: str