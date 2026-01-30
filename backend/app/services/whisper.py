"""
Whisper speech-to-text service using faster-whisper.
"""

from faster_whisper import WhisperModel
import tempfile
import os

# Load model globally (downloaded on first use)
_model = None

def get_model() -> WhisperModel:
    """Get or initialize the Whisper model."""
    global _model
    if _model is None:
        # Using base model for good balance of speed and accuracy
        # compute_type="int8" for faster inference on CPU
        _model = WhisperModel("base", device="cpu", compute_type="int8")
    return _model


def preload_model():
    """Preload the model on startup."""
    get_model()


def transcribe_audio(audio_bytes: bytes, filename: str = "audio.webm") -> str:
    """
    Transcribe audio bytes to text.
    
    Args:
        audio_bytes: Raw audio file bytes
        filename: Original filename (used to determine format)
    
    Returns:
        Transcribed text
    """
    model = get_model()
    
    # Write to temp file (faster-whisper needs a file path)
    suffix = os.path.splitext(filename)[1] or ".webm"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as f:
        f.write(audio_bytes)
        temp_path = f.name
    
    try:
        segments, info = model.transcribe(temp_path, beam_size=5)
        text = " ".join([segment.text for segment in segments])
        return text.strip()
    finally:
        os.unlink(temp_path)

