"""
Microphone → local speech-to-text → VoiceEvent.

One-file mental model:
1) SpeechRecognition records audio from the microphone
2) Vosk turns audio bytes into text
3) intent_from_transcript turns text into an intent label
4) we emit a contracts.events.VoiceEvent into the runtime
"""

from __future__ import annotations

import json
import os
import threading
import time
from pathlib import Path
from typing import Callable

from contracts.events import VoiceEvent

from .intent_from_transcript import COMMAND_GRAMMAR, intent_from_transcript

__all__ = ["VoskVoiceAdapter", "SpeechRecognitionVoiceAdapter", "recognize_vosk"]

# Keep imports simple: this module is only used when the voice modality is enabled.
try:
    import speech_recognition as sr
except ImportError as e:  # pragma: no cover
    raise ImportError(
        "Voice module requires the 'SpeechRecognition' package. Install with: pip install SpeechRecognition"
    ) from e

try:
    import vosk
except ImportError as e:  # pragma: no cover
    raise ImportError(
        "Voice module requires the 'vosk' package. Install with: pip install vosk"
    ) from e

# Callback types: fusion/core will later pass something like on_voice_event to receive events.
OnVoiceEvent = Callable[[VoiceEvent], None]
OnError = Callable[[str], None]


def _default_model_path() -> str:
    """
    Return the default Vosk model folder.

    The setup scripts place the model at `src/modalities/voice/models/vosk-model` and also
    export `VOSK_MODEL_PATH`. We support the env var override, otherwise we use the known
    local path directly (no searching).
    """
    env_path = os.environ.get("VOSK_MODEL_PATH")
    if env_path:
        return env_path
    module_dir = Path(__file__).resolve().parent
    return str(module_dir / "models" / "vosk-model")


def _to_voice_event(transcript: str) -> VoiceEvent:
    # Turn plain text into our toolkit event object.
    parsed = intent_from_transcript(transcript)
    trimmed = transcript.strip()
    # Confidence rule:
    # - 1.0 if it's a clean command match
    # - 0.3 if we heard something but it wasn't a command
    # - 0.0 if empty
    conf = 1.0 if parsed.confidence == 1.0 else (0.3 if trimmed else 0.0)
    return VoiceEvent(
        timestamp=time.monotonic(),
        confidence=conf,
        transcript=trimmed,
        is_final=True,
        intent=parsed.intent,
    )


def _pick_best_text(vosk_final_result: dict) -> str:
    """Prefer the candidate that matches an intent best (more stable for commands)."""
    # Vosk can return multiple alternatives; we pick the one that looks most like a known command.
    candidates: list[str] = []
    for alt in (vosk_final_result.get("alternatives") or []):
        text = (alt.get("text") or "").strip()
        if text:
            candidates.append(text)
    top = (vosk_final_result.get("text") or "").strip()
    if top:
        candidates.append(top)

    best_text = ""
    best_score = -1.0
    for text in candidates:
        score = intent_from_transcript(text).confidence
        if score > best_score:
            best_score = score
            best_text = text
    return best_text


def recognize_vosk(
    audio: sr.AudioData,
    sample_rate: int,
    model: vosk.Model,
    grammar: tuple[str, ...] | None = None,
) -> str:
    """
    Run local speech recognition with Vosk and return the best transcript string.

    The `audio` object is a SpeechRecognition AudioData instance. We only rely on
    its `get_raw_data` method to keep the adapter boundary simple.
    """
    # Passing a grammar to Vosk makes it listen mainly for our command phrases.
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

    # Convert the audio into 16kHz, 16-bit PCM bytes (what Vosk expects).
    pcm_bytes = audio.get_raw_data(
        convert_rate=sample_rate,
        convert_width=2,
    )
    recognizer.AcceptWaveform(pcm_bytes)

    final_result = json.loads(recognizer.FinalResult())
    return _pick_best_text(final_result)


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
        model_path: str | None = None,
        sample_rate: int = 16000,
        on_voice_event: OnVoiceEvent | None = None,
        on_error: OnError | None = None,
    ) -> None:
        # Find the Vosk model folder.
        resolved_model_path = model_path or _default_model_path()
        if not Path(resolved_model_path).exists():
            raise FileNotFoundError(
                f"Vosk model path does not exist: {resolved_model_path}"
            )

        # Store config + callbacks.
        self._lang = lang
        self._on_voice_event = on_voice_event
        self._on_error = on_error
        self._sample_rate = sample_rate
        self._grammar = COMMAND_GRAMMAR

        # SpeechRecognition "front end" (microphone + phrase detection).
        self._recognizer = sr.Recognizer()
        self._recognizer.dynamic_energy_threshold = True
        self._recognizer.pause_threshold = 0.5
        self._recognizer.non_speaking_duration = 0.25
        self._recognizer.phrase_threshold = 0.2

        self._microphone = sr.Microphone(sample_rate=sample_rate)
        # Vosk "back end" (audio bytes -> text).
        self._model = vosk.Model(resolved_model_path)
        self._running = False
        self._thread: threading.Thread | None = None

    def listen_once(
        self,
        *,
        timeout: float = 5.0,
        phrase_time_limit: float = 4.0,
        adjust_ambient: bool = True,
    ) -> VoiceEvent | None:
        """
        Record one utterance and return a VoiceEvent, or None if nothing heard / recognition fails.

        Steps: listen → bytes → recognize_vosk → text (string) → _build_voice_event.
        """
        try:
            with self._microphone as source:
                # Quick calibration to current background noise level.
                if adjust_ambient:
                    self._recognizer.adjust_for_ambient_noise(source, duration=0.4)
                # This blocks until it detects a phrase (or hits timeout).
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
            # Any Vosk/decoding error ends this attempt.
            if self._on_error:
                self._on_error(f"recognition_service_error:{e}")
            return None

        if not text:
            # We got audio but no clear text.
            if self._on_error:
                self._on_error("could_not_understand_audio")
            return None

        return _to_voice_event(text)

    def start(self) -> None:
        # Start a background thread that continuously listens.
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._loop, name="vosk-voice", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        # Stop listening and wait briefly for the thread to exit.
        self._running = False
        if self._thread is not None:
            self._thread.join(timeout=2.0)
            self._thread = None

    def is_listening(self) -> bool:
        return self._running

    def _loop(self) -> None:
        """Background thread: repeatedly run listen_once and notify on_voice_event."""
        # Keep looping until stop() flips _running to False.
        while self._running:
            ev = self.listen_once(timeout=1.0, phrase_time_limit=4.0, adjust_ambient=False)
            if ev is not None and self._on_voice_event:
                self._on_voice_event(ev)


# Backward-compatible alias for older imports.
SpeechRecognitionVoiceAdapter = VoskVoiceAdapter
