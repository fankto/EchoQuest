# src/audio_processor/exceptions.py
class AudioProcessorError(Exception):
    """Base exception for audio processor errors"""


class AudioLoadError(AudioProcessorError):
    """Raised when there's an error loading an audio file"""


class AudioFormatError(AudioProcessorError):
    """Raised when there's an unsupported audio format"""
