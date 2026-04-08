# Python Collaboration Core

Importable runtime modules live directly in `src/core/*.py`.

Current responsibilities:

- `event_bus.py`: internal publish/subscribe for modality events and actions
- `context_store.py`: short-lived multimodal interaction state
- `fusion_engine.py`: rule-based mapping from gesture/voice events to app-facing actions
- `application_router.py`: routes fused actions to the active app
- `runtime.py`: wires modalities, fusion, and apps together
