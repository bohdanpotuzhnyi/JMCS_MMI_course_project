# JMCS_MMI Course Project

## Project Goal

This project aims to build a small interaction toolkit that lets users manipulate digital objects through voice commands and hand gestures instead of a mouse or keyboard.

The toolkit should combine:

- voice input for commands such as selecting, creating, deleting, or confirming actions
- hand gesture input for spatial interaction such as moving, rotating, placing, or resizing objects

The main idea is to fuse speech and gesture into a shared interaction system that can be reused across multiple applications.

## Planned Demonstration Apps

To demonstrate the toolkit, we plan to build two simple applications on top of the same interaction core:

1. **Shape Puzzle / Matching App**
   Users can pick, move, rotate, and match shapes using gestures and spoken commands.
2. **Virtual Workspace**
   A small free-form object manipulation board where users can arrange and transform digital objects in space.

These apps should help validate whether the toolkit is reusable across both task-oriented and open-ended interaction scenarios.

## Preliminary System Modules

The current project structure is based on four main components:

### 1. Gesture Module

This module detects and interprets hand gestures using a camera and computer vision.

Possible responsibilities:

- hand tracking
- gesture recognition
- spatial position estimation
- motion interpretation for actions like move, rotate, grab, or release

### 2. Voice Module

This module is responsible for speech recognition and command parsing.

Possible responsibilities:

- microphone input capture
- speech-to-text
- intent detection
- command extraction such as "move this here", "rotate left", or "delete object"

### 3. Collaboration Core

This is the central integration layer of the toolkit. It combines gesture input with spoken commands and decides what the system should do.

Possible responsibilities:

- synchronizing gesture and speech events
- resolving references between modalities
- mapping user intent to system actions
- handling ambiguity, timing, and context

Example:
If a user points to an object while saying "move this there", the collaboration core should combine the pointing gesture with the spoken command and execute the intended action.

### 4. Demo Applications

On top of the toolkit, we will implement:

- a shape matching application
- a free object manipulation board / virtual workspace

These applications should share the same underlying multimodal toolkit rather than implementing separate input logic.

## Open-Source Direction

The project should prefer open-source models and libraries for:

- speech recognition
- hand and gesture detection
- other perception or interaction-related components

This keeps the system transparent, modifiable, and easier to reproduce for academic work.

## Initial Task List

The following tasks are a good starting point and can be adjusted as the project evolves:

1. Define the interaction scenarios for both demo apps.
2. Select open-source tools or models for gesture detection and speech recognition.
3. Implement a first version of the gesture module.
4. Implement a first version of the voice module.
5. Design the collaboration core that fuses speech and gesture input.
6. Build the Shape Puzzle / Matching App on top of the toolkit.
7. Build the Virtual Workspace on top of the same toolkit.
8. Evaluate whether the shared toolkit supports both applications effectively.

## Evaluation Criteria

According to the mini-project evaluation criteria for JMCS, the project should address the following points:

1. **Idea / Design**
   The architecture should be well-thought-out and clearly justified.
2. **Quality and Amount of Work**
   The code should be modular and the repository structure should be clear.
3. **Usability and Extensibility of the Toolkit**
   The result should feel like a reusable toolkit rather than a single demo.
   It should be possible for others to reuse it, configure it, and extend it with new modalities.
   This may include a simple API, configuration files, and clear module boundaries.
4. **Fusion Engine Originality and Simplicity**
   The fusion engine describes how the system combines multiple modalities.
   The design should be understandable, original where possible, and not unnecessarily complex.
   Possible approaches could include rule-based fusion, meaning frames, or LLM-supported interpretation.
5. **Example Application Quality**
   The toolkit must be demonstrated with a real use case using at least two modalities.
   Important aspects include interaction quality, dialogue flow, and error handling.
6. **Evaluation**
   The project should include a meaningful evaluation of the system and its behavior.
7. **Report**
   The final report should clearly explain the system, implementation decisions, and results.
8. **Presentation**
   The project should be presented clearly through an oral presentation, live demo, and/or video.
9. **User Evaluation**
   The project should include user-centered evaluation to assess usability and interaction quality.

## Core Idea

The value of this project is not only in building two small apps, but in creating a reusable multimodal interaction toolkit that supports natural object manipulation through speech and gesture.

## Quick Start

The repository includes setup scripts that create the virtual environment, install Python dependencies, download the local speech and gesture models, and export the required paths.

### macOS

From the project root:

```bash
chmod +x scripts/setup_macos.sh scripts/activate_macos.sh
./scripts/setup_macos.sh
source scripts/activate_macos.sh
python -m apps.demo_app
```

### Windows PowerShell

From the project root:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/setup_windows.ps1
. .\scripts\activate_windows.ps1
python -m apps.demo_app
```

### Windows cmd.exe

From the project root:

```bat
powershell -ExecutionPolicy Bypass -File scripts\setup_windows.ps1
scripts\activate_windows.bat
python -m apps.demo_app
```

## Current Demo Controls

The current demo app opens a canvas where squares are rendered on top of the live camera view.

- `Start Camera`: starts the gesture detector and embeds the annotated camera feed into the square field
- `Start Voice`: starts the local Vosk-based speech recognizer
- `Add Square`: creates a square object
- mouse click on a square: selects it
- arrow keys or spoken commands like `move left`, `move right`, `move up`, `move down`: move the selected square
- `Q` / `E` or spoken commands like `rotate left`, `rotate right`: rotate the selected square
- `Delete` / `Backspace`: remove the selected square
