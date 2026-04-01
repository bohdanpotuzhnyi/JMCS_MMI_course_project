from __future__ import annotations
import math
import time
from collections import deque
from dataclasses import dataclass
from typing import Callable, Optional

from contracts.events import GestureType, NormalizedPosition
from .landmark_detector import RawHandResult


# Landmark index map 

WRIST       = 0
THUMB_CMC, THUMB_MCP, THUMB_IP, THUMB_TIP         = 1, 2, 3, 4
INDEX_MCP,  INDEX_PIP,  INDEX_DIP,  INDEX_TIP      = 5, 6, 7, 8
MIDDLE_MCP, MIDDLE_PIP, MIDDLE_DIP, MIDDLE_TIP     = 9, 10, 11, 12
RING_MCP,   RING_PIP,   RING_DIP,   RING_TIP       = 13, 14, 15, 16
PINKY_MCP,  PINKY_PIP,  PINKY_DIP,  PINKY_TIP      = 17, 18, 19, 20


@dataclass
class ClassificationResult:
    gesture: GestureType
    confidence: float

GestureClassifier = Callable[
    [list[NormalizedPosition]], Optional[ClassificationResult]
]


def _dist(a: NormalizedPosition, b: NormalizedPosition) -> float:
    return math.sqrt((a.x - b.x) ** 2 + (a.y - b.y) ** 2)


def _is_extended(tip: NormalizedPosition, pip: NormalizedPosition) -> bool:
    return tip.y < pip.y - 0.02


#  Static gesture classifiers 

def _classify_open_palm(lm: list[NormalizedPosition]) -> Optional[ClassificationResult]:
    fingers_up = (
        _is_extended(lm[INDEX_TIP],  lm[INDEX_PIP])  and
        _is_extended(lm[MIDDLE_TIP], lm[MIDDLE_PIP]) and
        _is_extended(lm[RING_TIP],   lm[RING_PIP])   and
        _is_extended(lm[PINKY_TIP],  lm[PINKY_PIP])
    )
    if not fingers_up:
        return None
    return ClassificationResult(GestureType.OPEN_PALM, 0.85)


def _classify_fist(lm: list[NormalizedPosition]) -> Optional[ClassificationResult]:
    fingers_closed = (
        not _is_extended(lm[INDEX_TIP],  lm[INDEX_PIP])  and
        not _is_extended(lm[MIDDLE_TIP], lm[MIDDLE_PIP]) and
        not _is_extended(lm[RING_TIP],   lm[RING_PIP])   and
        not _is_extended(lm[PINKY_TIP],  lm[PINKY_PIP])
    )
    if not fingers_closed:
        return None
    return ClassificationResult(GestureType.FIST, 0.85)


def _classify_grab(lm: list[NormalizedPosition]) -> Optional[ClassificationResult]:

    fist = _classify_fist(lm)
    if not fist:
        return None
    if lm[MIDDLE_MCP].y > 0.7:
        return None
    return ClassificationResult(GestureType.GRAB, 0.80)


def _classify_pinch(lm: list[NormalizedPosition]) -> Optional[ClassificationResult]:
    tip_dist  = _dist(lm[THUMB_TIP], lm[INDEX_TIP])
    hand_size = _dist(lm[WRIST], lm[MIDDLE_MCP])

    if hand_size < 1e-6:
        return None

    ratio = tip_dist / hand_size
    if ratio > 0.25:
        return None

    confidence = min(1.0, 1 - ratio / 0.25) * 0.9
    return ClassificationResult(GestureType.PINCH, confidence)


def _classify_point(lm: list[NormalizedPosition]) -> Optional[ClassificationResult]:
    index_up   = _is_extended(lm[INDEX_TIP],  lm[INDEX_PIP])
    others_down = (
        not _is_extended(lm[MIDDLE_TIP], lm[MIDDLE_PIP]) and
        not _is_extended(lm[RING_TIP],   lm[RING_PIP])   and
        not _is_extended(lm[PINKY_TIP],  lm[PINKY_PIP])
    )
    if not (index_up and others_down):
        return None
    return ClassificationResult(GestureType.POINT, 0.88)



_STATIC_CLASSIFIERS: list[GestureClassifier] = [
    _classify_pinch,
    _classify_point,
    _classify_grab,
    _classify_fist,
    _classify_open_palm,
]



_HISTORY_SIZE    = 12    
_SWIPE_THRESHOLD = 0.15  
_SWIPE_MAX_MS    = 600   


@dataclass
class _PositionSample:
    position: NormalizedPosition
    timestamp: float 


class SwipeDetector:
    """Keeps a rolling frame history and detects directional palm movement."""

    def __init__(self):
        self._history: deque[_PositionSample] = deque(maxlen=_HISTORY_SIZE)

    def update(
        self, palm: NormalizedPosition, timestamp: float
    ) -> Optional[ClassificationResult]:
        self._history.append(_PositionSample(palm, timestamp))

        if len(self._history) < _HISTORY_SIZE // 2:
            return None

        first = self._history[0]
        last  = self._history[-1]
        dx = last.position.x - first.position.x
        dy = last.position.y - first.position.y
        elapsed_ms = (last.timestamp - first.timestamp) * 1000

        if elapsed_ms > _SWIPE_MAX_MS:
            return None

        if abs(dx) > abs(dy) and abs(dx) > _SWIPE_THRESHOLD:
            gesture = GestureType.SWIPE_RIGHT if dx > 0 else GestureType.SWIPE_LEFT
            return ClassificationResult(gesture, 0.82)

        if abs(dy) > abs(dx) and abs(dy) > _SWIPE_THRESHOLD:
            gesture = GestureType.SWIPE_DOWN if dy > 0 else GestureType.SWIPE_UP
            return ClassificationResult(gesture, 0.82)

        return None

    def reset(self) -> None:
        self._history.clear()


#  Public helper

def classify_gesture(hand: RawHandResult) -> ClassificationResult:
    for classifier in _STATIC_CLASSIFIERS:
        result = classifier(hand.landmarks)
        if result:
            return result
    return ClassificationResult(GestureType.UNKNOWN, 0.0)


def get_palm_center(landmarks: list[NormalizedPosition]) -> NormalizedPosition:
    """Average of the four MCP knuckles — stable anchor point for position tracking."""
    points = [
        landmarks[INDEX_MCP],
        landmarks[MIDDLE_MCP],
        landmarks[RING_MCP],
        landmarks[PINKY_MCP],
    ]
    return NormalizedPosition(
        x=sum(p.x for p in points) / 4,
        y=sum(p.y for p in points) / 4,
        z=sum((p.z or 0) for p in points) / 4,
    )