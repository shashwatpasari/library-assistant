"""
Voice API routes for speech-to-text transcription.
"""

from fastapi import APIRouter, UploadFile, File, HTTPException
from app.services.whisper import transcribe_audio

router = APIRouter(prefix="/voice", tags=["voice"])


@router.post("/transcribe")
async def transcribe_voice(audio: UploadFile = File(...)):
    """
    Transcribe audio file to text using Whisper.
    
    Accepts audio files (webm, wav, mp3, etc.)
    Returns the transcribed text.
    """
    try:
        audio_bytes = await audio.read()
        
        if len(audio_bytes) == 0:
            raise HTTPException(status_code=400, detail="Empty audio file")
        
        text = transcribe_audio(audio_bytes, audio.filename or "audio.webm")
        
        return {"text": text}
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Transcription failed: {str(e)}")

