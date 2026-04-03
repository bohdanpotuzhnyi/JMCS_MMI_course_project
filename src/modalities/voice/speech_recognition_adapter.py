"""
Microphone → speech-to-text → VoiceEvent.

This is the *I/O* part of the voice modality:
  1) capture audio from the default mic (PyAudio),
  2) send audio to a recognizer (here: Google Web Speech API via `speech_recognition`),
  3) get back a string,
  4) pass that string to intent_from_transcript and wrap the result in a VoiceEvent.

Connection to other files:
  intent_from_transcript.py  →  classifies the transcript string
  voice_event.py             →  defines the dict shape you emit

We import `speech_recognition` only inside `__init__` so that importing
`intent_from_transcript` alone does not require mic/STT dependencies (useful for tests).
"""

from __future__ import annotations

import threading
import time
from typing import Callable, Optional

from .intent_from_transcript import intent_from_transcript
from .voice_event import VoiceEvent

__all__ = ["SpeechRecognitionVoiceAdapter"]

# Callback types: fusion/core will later pass something like on_voice_event to receive events.
OnVoiceEvent = Callable[[VoiceEvent], None]
OnError = Callable[[str], None]


def _ensure_speech_recognition():
    """Load the SpeechRecognition library only when the mic adapter is actually used."""
    try:
        import speech_recognition as sr
    except ImportError as e:
        raise ImportError(
            "SpeechRecognitionVoiceAdapter needs the 'SpeechRecognition' package. "
            "Install: pip install SpeechRecognition"
        ) from e
    return sr


def _build_voice_event(transcript: str) -> VoiceEvent:
    """
    Bridge from raw STT text to the toolkit contract.

    - intent_from_transcript: did we recognize a movement keyword?
    - confidence: combines "keyword hit" vs "we heard something but no keyword"
    """
    parsed = intent_from_transcript(transcript)
    trimmed = transcript.strip()
    if parsed.confidence == 1.0:
        conf = 1.0
    elif trimmed:
        conf = 0.3
    else:
        conf = 0.0
    ev: VoiceEvent = {
        "type": "voice",
        "timestamp": time.time() * 1000.0,
        "transcript": trimmed,
        "confidence": conf,
    }
    if parsed.intent is not None:
        ev["intent"] = parsed.intent
    return ev


class SpeechRecognitionVoiceAdapter:
    """
    Two ways to use it:

    - listen_once(): block until one phrase or timeout — good for Streamlit ("click, then speak").
    - start() / stop(): background thread repeatedly calls listen_once and forwards each
      VoiceEvent to on_voice_event — closer to "always listening" demos.

    The fusion layer (not implemented here) would subscribe to these events the same way.
    """

    def __init__(
        self,
        *,
        lang: str = "en-US",
        on_voice_event: Optional[OnVoiceEvent] = None,
        on_error: Optional[OnError] = None,
    ) -> None:
        sr = _ensure_speech_recognition()
        self._sr = sr
        self._lang = lang
        self._on_voice_event = on_voice_event
        self._on_error = on_error
        self._recognizer = sr.Recognizer()
        self._microphone = sr.Microphone()
        self._running = False
        self._thread: Optional[threading.Thread] = None

    def listen_once(
        self,
        *,
        timeout: float = 5.0,
        phrase_time_limit: float = 12.0,
        adjust_ambient: bool = True,
    ) -> Optional[VoiceEvent]:
        """
        Record one utterance and return a VoiceEvent, or None if nothing heard / recognition fails.

        Steps: listen → bytes → recognize_google → text (string) → _build_voice_event.
        """
        sr = self._sr
        try:
            with self._microphone as source:
                if adjust_ambient:
                    self._recognizer.adjust_for_ambient_noise(source, duration=0.4)
                audio = self._recognizer.listen(source, timeout=timeout, phrase_time_limit=phrase_time_limit)
        except sr.WaitTimeoutError:
            return None

        try:
            text = self._recognizer.recognize_google(audio, language=self._lang)
        except sr.UnknownValueError:
            if self._on_error:
                self._on_error("could_not_understand_audio")
            return None
        except sr.RequestError as e:
            if self._on_error:
                self._on_error(f"recognition_service_error:{e}")
            return None

        return _build_voice_event(text)

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._loop, name="speech-recognition-voice", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._running = False
        if self._thread is not None:
            self._thread.join(timeout=2.0)
            self._thread = None

    def is_listening(self) -> bool:
        return self._running

    def _loop(self) -> None:
        """Background thread: repeatedly run listen_once and notify on_voice_event."""
        while self._running:
            ev = self.listen_once(timeout=1.0, phrase_time_limit=8.0, adjust_ambient=False)
            if ev is not None and self._on_voice_event:
                self._on_voice_event(ev)
