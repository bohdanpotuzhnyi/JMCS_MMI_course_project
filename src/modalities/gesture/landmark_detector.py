# modalities/gesture/landmark_detector.py
from __future__ import annotations
import numpy as np
from dataclasses import dataclass

import mediapipe as mp
from mediapipe.tasks import python
from mediapipe.tasks.python import vision
from mediapipe.tasks.python.vision import HandLandmarkerOptions, HandLandmarker

from contracts.events import NormalizedPosition


@dataclass
class RawHandResult:
    landmarks: list[NormalizedPosition]
    world_landmarks: list[NormalizedPosition]
    handedness: str
    score: float


class LandmarkDetector:
    def __init__(
        self,
        max_hands: int = 2,
        detection_confidence: float = 0.5,
        tracking_confidence: float = 0.5,
    ):
        self._max_hands = max_hands
        self._detection_confidence = detection_confidence
        self._tracking_confidence = tracking_confidence
        self._landmarker = None

    def _init_landmarker(self):
        import urllib.request, os, tempfile

        model_url = (
            "https://storage.googleapis.com/mediapipe-models/"
            "hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task"
        )
        model_path = os.path.join(tempfile.gettempdir(), "hand_landmarker.task")

        if not os.path.exists(model_path):
            print("Downloading MediaPipe hand model (~25MB)...")
            urllib.request.urlretrieve(model_url, model_path)
            print("Done.")

        options = HandLandmarkerOptions(
            base_options=python.BaseOptions(model_asset_path=model_path),
            running_mode=vision.RunningMode.VIDEO,
            num_hands=self._max_hands,
            min_hand_detection_confidence=self._detection_confidence,
            min_tracking_confidence=self._tracking_confidence,
        )
        self._landmarker = HandLandmarker.create_from_options(options)

    def detect(self, bgr_frame: np.ndarray, timestamp_ms: int) -> list[RawHandResult]:
        if self._landmarker is None:
            self._init_landmarker()

        rgb = bgr_frame[:, :, ::-1]
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
        result = self._landmarker.detect_for_video(mp_image, timestamp_ms)

        if not result.hand_landmarks:
            return []

        output = []
        for i, hand_lm in enumerate(result.hand_landmarks):
            handedness_info = result.handedness[i][0] if result.handedness else None
            landmarks = [NormalizedPosition(x=lm.x, y=lm.y, z=lm.z) for lm in hand_lm]
            world_landmarks = []
            if result.hand_world_landmarks:
                world_landmarks = [
                    NormalizedPosition(x=lm.x, y=lm.y, z=lm.z)
                    for lm in result.hand_world_landmarks[i]
                ]
            output.append(RawHandResult(
                landmarks=landmarks,
                world_landmarks=world_landmarks,
                handedness=handedness_info.category_name.lower() if handedness_info else "unknown",
                score=handedness_info.score if handedness_info else 0.0,
            ))

        return output

    def close(self) -> None:
        if self._landmarker:
            self._landmarker.close()
            self._landmarker = None

    def __enter__(self) -> "LandmarkDetector":
        return self

    def __exit__(self, *_) -> None:
        self.close()