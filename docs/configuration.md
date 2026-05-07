# Fusion Config Guide

The fusion config describes how the shared fusion core converts voice and
gesture events into canonical actions. It does not configure an app UI, canvas,
colors, scoring, or rendering.

Use an INI-style file:

```ini
[section-name]
KEY = value
```

Recommended location for the default config:

```text
config/fusion.conf
```

Apps may keep sample configs next to their code, but those files should still
configure only the fusion core.

## Basic Shape

A fusion config usually has five parts:

1. core mode
2. timing and confidence
3. pointer behavior
4. voice phrase-to-intent mapping
5. intent/gesture-to-action mapping

Minimal example:

```ini
[fusion-core]
ENABLED = YES
ENGINE = 2d
STRATEGY = rule-based

[fusion-timing]
TEMPORAL_WINDOW = 1.5s

[fusion-confidence]
VOICE_MIN_CONFIDENCE = 0.60
GESTURE_MIN_CONFIDENCE = 0.60

[fusion-voice.intent.left]
PHRASES = move left, go left, left

[fusion-action.voice.left]
ACTION = move_object
DX = -0.10
DY = 0.00
```

## Core Mode

```ini
[fusion-core]
ENABLED = YES
ENGINE = 2d
STRATEGY = rule-based
```

`ENGINE` controls the kind of fusion metadata the core emits:

- `2d`: basic pointer positions and 2D actions.
- `3d`: pointer updates plus palm and pinch metadata for drag, rotate, resize.

This does not configure rendering. A 3D app still owns its own rendering and
scoring logic.

## Timing And Confidence

```ini
[fusion-timing]
TEMPORAL_WINDOW = 1.5s

[fusion-confidence]
VOICE_MIN_CONFIDENCE = 0.60
GESTURE_MIN_CONFIDENCE = 0.60
```

`TEMPORAL_WINDOW` controls how close voice and gesture events must be to count as
one multimodal command.

## Pointer Behavior

```ini
[fusion-pointer]
SOURCE = index-finger
EMIT_UPDATE_POINTER = YES
EMIT_POINTER_DELTA = YES
EMIT_PALM_DELTA = YES
EMIT_PINCH_DELTA = YES
```

Use this section when an app needs continuous movement information.

For a simple 2D app:

```ini
EMIT_UPDATE_POINTER = NO
EMIT_PALM_DELTA = NO
EMIT_PINCH_DELTA = NO
```

For a 3D manipulation app:

```ini
EMIT_UPDATE_POINTER = YES
EMIT_POINTER_DELTA = YES
EMIT_PALM_DELTA = YES
EMIT_PINCH_DELTA = YES
```

## Voice Intents

Voice intent sections map recognized words or phrases to normalized intents.

```ini
[fusion-voice.intent.create-cube]
PHRASES = create cube, make cube, add cube

[fusion-voice.intent.move-here]
PHRASES = move here, move there, place here, put here

[fusion-voice.intent.delete]
PHRASES = delete, delete this, remove this
REQUIRES_CONFIRMATION = YES
```

The section name after `fusion-voice.intent.` is the intent name. The `PHRASES`
list defines what the user can say to trigger it.

## Include Or Exclude Inputs

Use include/exclude sections to enable or disable groups of inputs without
removing their definitions.

```ini
[fusion-voice-include]
INTENTS = create-cube, select, drag, rotate, resize, done

[fusion-voice-exclude]
INTENTS = delete

[fusion-gesture-include]
GESTURES = point, grab, release

[fusion-gesture-exclude]
GESTURES = open_palm, fist
```

Exclude wins over include. This is useful for disabling destructive commands
during demos.

## Map Voice Intents To Actions

After an intent is recognized, map it to a canonical action.

```ini
[fusion-action.voice.create-cube]
ACTION = create_object
OBJECT_TYPE = cube
USE_POSITION = YES

[fusion-action.voice.drag]
ACTION = set_interaction_mode
MODE = dragging

[fusion-action.voice.insert]
ACTION = insert_object

[fusion-action.voice.delete]
ACTION = delete_object
REQUIRES_CONFIRMATION = YES
```

Common action fields:

- `ACTION`: canonical action type.
- `DX`, `DY`, `DZ`: movement delta.
- `ROTATION`: rotation amount.
- `OBJECT_TYPE`: object type for `create_object`.
- `MODE`: mode for `set_interaction_mode`.
- `USE_POSITION`: include current pointer position.
- `REQUIRES_CONFIRMATION`: require confirmation before emitting action.

## Map Gestures To Actions

```ini
[fusion-action.gesture.point]
ACTION = select_object
USE_POSITION = YES

[fusion-action.gesture.swipe_left]
ACTION = move_object
DX = -0.10
DY = 0.00

[fusion-action.gesture.release]
ACTION = deselect_object
```

Gesture section names should match normalized gesture names, such as `point`,
`grab`, `release`, `swipe_left`, `open_palm`, or `fist`.

## 2D Example

```ini
[fusion-core]
ENABLED = YES
ENGINE = 2d
STRATEGY = rule-based

[fusion-voice.intent.left]
PHRASES = move left, go left, left

[fusion-action.voice.left]
ACTION = move_object
DX = -0.10
DY = 0.00

[fusion-action.gesture.point]
ACTION = select_object
USE_POSITION = YES
```

See also:

```text
src/apps/fusion-2d.conf
```

## 3D Example

```ini
[fusion-core]
ENABLED = YES
ENGINE = 3d
STRATEGY = rule-based

[fusion-pointer]
SOURCE = index-finger
EMIT_UPDATE_POINTER = YES
EMIT_POINTER_DELTA = YES
EMIT_PALM_DELTA = YES
EMIT_PINCH_DELTA = YES

[fusion-voice.intent.create-cube]
PHRASES = create cube, make cube, add cube

[fusion-action.voice.create-cube]
ACTION = create_object
OBJECT_TYPE = cube
USE_POSITION = YES

[fusion-action.voice.rotate]
ACTION = set_interaction_mode
MODE = rotating
```

See also:

```text
src/apps/shape-puzzle/fusion-3d.conf
```

## Rule Of Thumb

Put something in the fusion config if it changes how input becomes an action.

Do not put something in the fusion config if it changes how an app looks,
renders, scores, or stores its own domain state.
