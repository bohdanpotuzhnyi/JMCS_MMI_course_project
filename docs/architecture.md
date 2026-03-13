# Architecture

## Overview

This project is structured as a reusable multimodal interaction toolkit with two demonstration applications built on top of a shared core.

The architecture is local-first:

- speech recognition runs through a voice adapter
- hand tracking and gesture recognition run through a gesture adapter
- a collaboration core fuses both modalities into canonical actions
- demo applications consume those actions through a stable application API

This separation keeps modality logic, fusion logic, and app-specific logic independent.

## Goals

- support object manipulation through voice and gesture
- reuse the same multimodal core across multiple apps
- keep the fusion engine understandable and easy to evaluate
- prefer open-source and locally runnable components where possible
- remain extensible for future modalities or additional demo apps

## High-Level Modules

### 1. Gesture Adapter

Responsibilities:

- camera input capture
- hand landmark tracking
- gesture recognition
- 2D/3D pointer or hand pose estimation
- normalized gesture event emission

Input:

- webcam frames

Output:

- `GestureEvent`

### 2. Voice Adapter

Responsibilities:

- microphone input capture
- speech-to-text
- intent extraction
- slot extraction for phrases such as "move this here" or "rotate left"
- normalized voice event emission

Input:

- microphone audio

Output:

- `VoiceEvent`

### 3. Collaboration Core

Responsibilities:

- receive modality events from adapters
- synchronize events in time
- resolve cross-modal references such as "this" and "there"
- track interaction context
- map multimodal evidence to canonical actions
- handle ambiguity and confirmation flow

Submodules:

- `event-bus`
- `context-store`
- `fusion-engine`
- `intent-resolver`
- `ambiguity-handler`

### 4. Application Layer

Responsibilities:

- define domain objects and scene state
- accept canonical actions from the core
- update the app state
- render the scene and feedback

Apps:

- `shape-puzzle`
- `virtual-workspace`

## Data Flow

1. The gesture adapter emits gesture events.
2. The voice adapter emits voice events.
3. The event bus timestamps and forwards all events.
4. The fusion engine evaluates events in a temporal window.
5. The intent resolver converts fused evidence into canonical actions.
6. The active application consumes those actions and updates its state.
7. The UI renders scene changes and system feedback.

## Canonical Contracts

### Gesture Event

```ts
export type GestureEvent = {
  type: "gesture";
  timestamp: number;
  hand: "left" | "right";
  gesture: "point" | "grab" | "release" | "rotate" | "pinch";
  position2d?: { x: number; y: number };
  position3d?: { x: number; y: number; z: number };
  targetObjectId?: string;
  confidence: number;
};
```

### Voice Event

```ts
export type VoiceEvent = {
  type: "voice";
  timestamp: number;
  transcript: string;
  intent?: "select" | "move" | "rotate" | "delete" | "confirm" | "cancel";
  slots?: Record<string, string | number>;
  confidence: number;
};
```

### Canonical Action

```ts
export type CanonicalAction =
  | { type: "select"; objectId: string }
  | { type: "move"; objectId: string; target: { x: number; y: number; z: number } }
  | { type: "rotate"; objectId: string; delta: number }
  | { type: "delete"; objectId: string }
  | { type: "confirm" }
  | { type: "cancel" };
```

## Fusion Strategy

The first implementation should use a rule-based fusion engine.

Why:

- easier to explain in the report
- easier to debug during live demos
- easier to evaluate systematically
- a better fit for the project scope than an LLM-dependent pipeline

Suggested rule set:

- maintain a short temporal fusion window for recent speech and gesture events
- allow deictic language such as "this", "that", and "there"
- prefer current pointing targets when speech references an object implicitly
- require confirmation when multiple objects match with similar confidence
- preserve the most recent selected object as part of context

## Context Model

The context store should track:

- selected object
- pointed object
- recent target position
- last confirmed action
- pending ambiguity or clarification state
- modality confidence values

This allows multi-turn interactions such as:

- point at object + say "select this"
- grab object + say "move here"
- say "rotate left" after selection

## Error Handling

The system should degrade safely when inputs are uncertain.

Examples:

- no object under pointer: ask the user to point again
- low speech confidence: repeat or request confirmation
- conflicting gesture and speech targets: prefer clarification over silent execution
- missing destination for "move this there": wait for or request a placement gesture

## License and Deployment Implications

The repository license is AGPL-3.0.

Implications for architecture:

- prefer a local-first deployment for the main demo
- keep network services optional and replaceable
- if the system is exposed as a network service, corresponding source obligations apply to the deployed modified version

For the course project, a local desktop setup is the simplest and clearest option.

## Suggested Milestones

1. Define interaction scenarios and supported commands.
2. Implement normalized event contracts.
3. Build gesture adapter with a basic hand-tracking pipeline.
4. Build voice adapter with speech-to-text and simple intent extraction.
5. Implement rule-based fusion and context tracking.
6. Integrate the shape puzzle app.
7. Integrate the virtual workspace app.
8. Add evaluation instrumentation and user testing tasks.
