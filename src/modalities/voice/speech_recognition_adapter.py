"""
Microphone → local speech-to-text → VoiceEvent.

This keeps the existing microphone capture flow based on `speech_recognition`,
but replaces the remote Google recognizer with a local Vosk recognizer.

Connection to other files:
  intent_from_transcript.py  →  classifies the transcript string
  voice_event.py             →  defines the dict shape you emit
"""

from __future__ import annotations

import json
import os
import threading
import time
from pathlib import Path
from typing import Callable, Optional

from contracts.events import VoiceEvent

from .intent_from_transcript import COMMAND_GRAMMAR, intent_from_transcript

__all__ = ["VoskVoiceAdapter", "SpeechRecognitionVoiceAdapter", "recognize_vosk"]

# Callback types: fusion/core will later pass something like on_voice_event to receive events.
OnVoiceEvent = Callable[[VoiceEvent], None]
OnError = Callable[[str], None]


def _ensure_speech_recognition():
    """Load the microphone helper library only when the adapter is actually used."""
    try:
        import speech_recognition as sr
    except ImportError as e:
        raise ImportError(
            "VoskVoiceAdapter needs the 'SpeechRecognition' package for microphone capture. "
            "Install: pip install SpeechRecognition"
        ) from e
    return sr


def _ensure_vosk():
    """Load the local speech recognizer only when it is actually used."""
    try:
        import vosk
    except ImportError as e:
        raise ImportError(
            "VoskVoiceAdapter needs the 'vosk' package for local speech recognition. "
            "Install: pip install vosk"
        ) from e
    return vosk


def _default_model_path() -> Optional[str]:
    """
    Resolve the Vosk model path.

    Order:
    1. VOSK_MODEL_PATH environment variable
    2. common local folder names under the voice module
    """
    env_path = os.environ.get("VOSK_MODEL_PATH")
    if env_path:
        return env_path

    module_dir = Path(__file__).resolve().parent
    candidates = (
        module_dir / "models" / "vosk-model",
        module_dir / "models" / "vosk",
        module_dir / "model",
    )
    for candidate in candidates:
        if candidate.exists():
            return str(candidate)
    return None


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
    return VoiceEvent(
        timestamp=time.monotonic(),
        confidence=conf,
        transcript=trimmed,
        is_final=True,
        intent=parsed.intent,
    )


def _best_transcript_from_result(result: dict) -> str:
    alternatives = result.get("alternatives") or []
    candidates: list[str] = []
    if alternatives:
        candidates.extend(
            candidate.get("text", "").strip()
            for candidate in alternatives
        )
    if result.get("text"):
        candidates.append(result.get("text", "").strip())

    best_text = ""
    best_confidence = -1.0
    for candidate in candidates:
        parsed = intent_from_transcript(candidate)
        if parsed.confidence > best_confidence:
            best_confidence = parsed.confidence
            best_text = candidate
    return best_text.strip()


def recognize_vosk(
    audio: object,
    sample_rate: int,
    model: object,
    grammar: tuple[str, ...] | None = None,
) -> str:
    """
    Run local speech recognition with Vosk and return the best transcript string.

    The `audio` object is a SpeechRecognition AudioData instance. We only rely on
    its `get_raw_data` method to keep the adapter boundary simple.
    """
    vosk = _ensure_vosk()
    grammar_payload = None
    if grammar:
        grammar_payload = json.dumps(list(grammar) + ["[unk]"])
    recognizer = (
        vosk.KaldiRecognizer(model, sample_rate, grammar_payload)
        if grammar_payload is not None
        else vosk.KaldiRecognizer(model, sample_rate)
    )
    recognizer.SetWords(True)
    recognizer.SetMaxAlternatives(5)

    pcm_bytes = audio.get_raw_data(
        convert_rate=sample_rate,
        convert_width=2,
    )
    recognizer.AcceptWaveform(pcm_bytes)

    final_result = json.loads(recognizer.FinalResult())
    return _best_transcript_from_result(final_result)


class VoskVoiceAdapter:
    """
    Two ways to use it:

    - listen_once(): block until one phrase or timeout — good for UI-triggered capture
    - start() / stop(): background thread repeatedly calls listen_once and forwards each
      VoiceEvent to on_voice_event — closer to "always listening" demos
    """

    def __init__(
        self,
        *,
        lang: str = "en-US",
        model_path: Optional[str] = None,
        sample_rate: int = 16000,
        on_voice_event: Optional[OnVoiceEvent] = None,
        on_error: Optional[OnError] = None,
    ) -> None:
        sr = _ensure_speech_recognition()
        vosk = _ensure_vosk()

        resolved_model_path = model_path or _default_model_path()
        if not resolved_model_path:
            raise ValueError(
                "No Vosk model path configured. Set VOSK_MODEL_PATH or place a model under "
                "src/modalities/voice/models/vosk-model."
            )
        if not Path(resolved_model_path).exists():
            raise FileNotFoundError(
                f"Vosk model path does not exist: {resolved_model_path}"
            )

        self._sr = sr
        self._lang = lang
        self._sample_rate = sample_rate
        self._on_voice_event = on_voice_event
        self._on_error = on_error
        self._recognizer = sr.Recognizer()
        self._recognizer.dynamic_energy_threshold = True
        self._recognizer.pause_threshold = 0.5
        self._recognizer.non_speaking_duration = 0.25
        self._recognizer.phrase_threshold = 0.2
        self._microphone = sr.Microphone(sample_rate=sample_rate)
        self._model = vosk.Model(resolved_model_path)
        self._grammar = COMMAND_GRAMMAR
        self._running = False
        self._thread: Optional[threading.Thread] = None

    def listen_once(
        self,
        *,
        timeout: float = 5.0,
        phrase_time_limit: float = 4.0,
        adjust_ambient: bool = True,
    ) -> Optional[VoiceEvent]:
        """
        Record one utterance and return a VoiceEvent, or None if nothing heard / recognition fails.

        Steps: listen → bytes → recognize_vosk → text (string) → _build_voice_event.
        """
        sr = self._sr
        try:
            with self._microphone as source:
                if adjust_ambient:
                    self._recognizer.adjust_for_ambient_noise(source, duration=0.4)
                audio = self._recognizer.listen(
                    source,
                    timeout=timeout,
                    phrase_time_limit=phrase_time_limit,
                )
        except sr.WaitTimeoutError:
            return None

        try:
            text = recognize_vosk(audio, self._sample_rate, self._model, self._grammar)
        except Exception as e:
            if self._on_error:
                self._on_error(f"recognition_service_error:{e}")
            return None

        if not text:
            if self._on_error:
                self._on_error("could_not_understand_audio")
            return None

        return _build_voice_event(text)

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._loop, name="vosk-voice", daemon=True)
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
            ev = self.listen_once(timeout=1.0, phrase_time_limit=4.0, adjust_ambient=False)
            if ev is not None and self._on_voice_event:
                self._on_voice_event(ev)


# Backward-compatible alias for older imports.
SpeechRecognitionVoiceAdapter = VoskVoiceAdapter
