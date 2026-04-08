# Voice Adapter

This module should encapsulate all voice-specific perception code.

Expected responsibilities:

- microphone capture
- local speech-to-text
- intent extraction
- slot extraction (reserved for future use)
- emission of normalized `VoiceEvent` objects

Current implementation notes:

- audio capture uses `SpeechRecognition` + `PyAudio`
- transcription uses a local `Vosk` model
- recognition is constrained to a small command grammar to improve command-and-control accuracy
- transcript matching includes normalization and fuzzy recovery for common STT mistakes
- set `VOSK_MODEL_PATH` to the unpacked model directory, or place a model under `src/modalities/voice/models/vosk-model`
