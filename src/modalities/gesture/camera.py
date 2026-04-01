# modalities/gesture/camera.py
from __future__ import annotations
import cv2
import numpy as np
from dataclasses import dataclass


@dataclass
class CameraOptions:
    device_index: int = 0
    width: int = 640
    height: int = 480
    fps: int = 30


class CameraCapture:
    def __init__(self, opts: CameraOptions | None = None):
        self._opts = opts or CameraOptions()
        self._cap: cv2.VideoCapture | None = None

    def start(self) -> None:
        cap = cv2.VideoCapture(self._opts.device_index)
        cap.set(cv2.CAP_PROP_FRAME_WIDTH,  self._opts.width)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self._opts.height)
        cap.set(cv2.CAP_PROP_FPS,          self._opts.fps)

        if not cap.isOpened():
            raise RuntimeError(
                f"CameraCapture: could not open device {self._opts.device_index}"
            )
        self._cap = cap

    def read(self) -> np.ndarray | None:
        if self._cap is None:
            raise RuntimeError("CameraCapture: call start() first")
        ok, frame = self._cap.read()
        return frame if ok else None

    def stop(self) -> None:
        if self._cap:
            self._cap.release()
            self._cap = None

    @property
    def is_running(self) -> bool:
        return self._cap is not None and self._cap.isOpened()

    def __enter__(self) -> "CameraCapture":
        self.start()
        return self

    def __exit__(self, *_) -> None:
        self.stop()