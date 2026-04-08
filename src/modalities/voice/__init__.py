"""
Public entry points for the voice modality.

Suggested reading order for a beginner:
  1. voice_event.py          — what data leaves this module
  2. intent_from_transcript.py — pure text → intent (no mic)
  3. speech_recognition_adapter.py — mic + local Vosk STT → VoiceEvent (uses #2)

Import from elsewhere (e.g. fusion core or a Streamlit app):
    from modalities.voice import VoskVoiceAdapter, intent_from_transcript
"""

from .intent_from_transcript import IntentFromTranscriptResult, intent_from_transcript
from .speech_recognition_adapter import (
    SpeechRecognitionVoiceAdapter,
    VoskVoiceAdapter,
    recognize_vosk,
)
from .voice_event import VoiceEvent, VoiceIntent

__all__ = [
    "IntentFromTranscriptResult",
    "SpeechRecognitionVoiceAdapter",
    "VoskVoiceAdapter",
    "VoiceEvent",
    "VoiceIntent",
    "intent_from_transcript",
    "recognize_vosk",
]
