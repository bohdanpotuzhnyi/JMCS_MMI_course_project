

from __future__ import annotations
import threading
import time
from typing import Callable, Optional

import cv2
import numpy as np

from contracts.events import GestureEvent, GestureType
from .camera import CameraCapture, CameraOptions
from .landmark_detector import LandmarkDetector
from .classifier import SwipeDetector, classify_gesture, get_palm_center


GestureEventHandler = Callable[[GestureEvent], None]
GestureErrorHandler = Callable[[str], None]
GesturePreviewHandler = Callable[[np.ndarray], None]


class GestureDetectorOptions:
    def __init__(
        self,
        camera: Optional[CameraOptions] = None,
        min_confidence: float = 0.60,
        suppress_unknown: bool = True,
        debounce_frames: int = 6,
        max_hands: int = 2,
        show_preview: bool = False,
        preview_window_name: str = "Gesture Preview",
        on_error: GestureErrorHandler | None = None,
        on_preview: GesturePreviewHandler | None = None,
    ):
        self.camera          = camera or CameraOptions()
        self.min_confidence  = min_confidence
        self.suppress_unknown = suppress_unknown
        self.debounce_frames = debounce_frames
        self.max_hands       = max_hands
        self.show_preview    = show_preview
        self.preview_window_name = preview_window_name
        self.on_error = on_error
        self.on_preview = on_preview


class GestureDetector:
    """
    Main entry point for the gesture modality.

    Usage:
        detector = GestureDetector()
        unsub = detector.on(lambda event: print(event.gesture))
        detector.start()          # blocks if blocking=True (default)
        ...
        detector.stop()
        unsub()
    """

    def __init__(self, opts: Optional[GestureDetectorOptions] = None):
        self._opts     = opts or GestureDetectorOptions()
        self._camera   = CameraCapture(self._opts.camera)
        self._detector = LandmarkDetector(max_hands=self._opts.max_hands)

        self._handlers: list[GestureEventHandler] = []
        self._swipe_detectors: dict[int, SwipeDetector] = {}
        self._last_gesture: dict[int, dict] = {} 

        self._running  = False
        self._thread: Optional[threading.Thread] = None

   

    def on(self, handler: GestureEventHandler) -> Callable[[], None]:
        """Register a callback. Returns an unsubscribe function."""
        self._handlers.append(handler)
        def unsubscribe():
            self._handlers = [h for h in self._handlers if h is not handler]
        return unsubscribe



    def start(self, blocking: bool = False) -> None:
        """
        Start the detection loop.
        blocking=True: runs on the calling thread (good for scripts).
        blocking=False: runs on a background thread (good for apps).
        """
        self._camera.start()
        self._running = True

        if blocking:
            self._loop()
        else:
            self._thread = threading.Thread(target=self._loop, daemon=True)
            self._thread.start()

    def stop(self) -> None:
        self._running = False
        if self._thread:
            self._thread.join(timeout=2.0)
            self._thread = None
        self._camera.stop()
        self._detector.close()
        self._swipe_detectors.clear()
        self._last_gesture.clear()
        if self._opts.show_preview:
            cv2.destroyWindow(self._opts.preview_window_name)

    # ── Detection loop ────────────────────────────────────────────────────────

    def _loop(self) -> None:
        while self._running:
            try:
                frame = self._camera.read()
                if frame is None:
                    continue

                now   = time.monotonic()
                timestamp_ms = int(time.monotonic() * 1000)
                hands = self._detector.detect(frame, timestamp_ms)
                preview_rows: list[tuple[GestureType, float, tuple[int, int], str]] = []

                for hand_idx, hand in enumerate(hands):
                    if hand_idx not in self._swipe_detectors:
                        self._swipe_detectors[hand_idx] = SwipeDetector()

                    palm    = get_palm_center(hand.landmarks)
                    swiper  = self._swipe_detectors[hand_idx]

                    swipe_result  = swiper.update(palm, now)
                    static_result = classify_gesture(hand)

                    # Swipe wins when it fires — it's more deliberate than a held gesture.
                    result = (
                        swipe_result
                        if swipe_result and swipe_result.confidence >= self._opts.min_confidence
                        else static_result
                    )
                    preview_rows.append(
                        (
                            result.gesture,
                            result.confidence,
                            (
                                int(palm.x * frame.shape[1]),
                                int(palm.y * frame.shape[0]),
                            ),
                            hand.handedness,
                        )
                    )

                    if self._opts.suppress_unknown and result.gesture == GestureType.UNKNOWN:
                        continue
                    if result.confidence < self._opts.min_confidence:
                        continue

                    # same gesture held across frames.
                    last = self._last_gesture.get(hand_idx)
                    if last and last["type"] == result.gesture:
                        last["frame_count"] += 1
                        if last["frame_count"] < self._opts.debounce_frames:
                            continue
                        last["frame_count"] = 0
                    else:
                        self._last_gesture[hand_idx] = {
                            "type": result.gesture,
                            "frame_count": 0,
                        }

                    event = GestureEvent(
                        confidence=result.confidence,
                        gesture=result.gesture,
                        position=palm,
                        landmarks=hand.landmarks,
                        hand=hand.handedness,
                    )
                    self._emit(event)

                # Clean up detectors for hands that left the frame.
                active_indices = set(range(len(hands)))
                for idx in list(self._swipe_detectors):
                    if idx not in active_indices:
                        self._swipe_detectors[idx].reset()
                        del self._swipe_detectors[idx]
                        self._last_gesture.pop(idx, None)

                preview_frame = self._build_preview(frame, hands, preview_rows)
                if self._opts.on_preview is not None:
                    self._opts.on_preview(preview_frame)
                if self._opts.show_preview:
                    self._show_preview(preview_frame)
            except Exception as exc:
                self._running = False
                if self._opts.on_error is not None:
                    self._opts.on_error(str(exc))
                else:
                    print(f"[GestureDetector] detection loop failed: {exc}")
                break

    def _emit(self, event: GestureEvent) -> None:
        for handler in self._handlers:
            try:
                handler(event)
            except Exception as exc:
                print(f"[GestureDetector] handler raised: {exc}")

    def _build_preview(
        self,
        frame,
        hands,
        preview_rows: list[tuple[GestureType, float, tuple[int, int], str]],
    ) -> np.ndarray:
        preview = frame.copy()
        for hand in hands:
            for landmark in hand.landmarks:
                x = int(landmark.x * preview.shape[1])
                y = int(landmark.y * preview.shape[0])
                cv2.circle(preview, (x, y), 3, (0, 255, 180), -1)

        for idx, (gesture, confidence, center, handedness) in enumerate(preview_rows):
            cv2.circle(preview, center, 8, (0, 165, 255), 2)
            label = f"{handedness}: {gesture.value} ({confidence:.2f})"
            text_y = 30 + idx * 28
            cv2.putText(
                preview,
                label,
                (12, text_y),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.7,
                (40, 40, 255),
                2,
                cv2.LINE_AA,
            )

        if not preview_rows:
            cv2.putText(
                preview,
                "No confident gesture detected",
                (12, 30),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.7,
                (180, 180, 180),
                2,
                cv2.LINE_AA,
            )

        return preview

    def _show_preview(self, preview: np.ndarray) -> None:
        cv2.imshow(self._opts.preview_window_name, preview)
        cv2.waitKey(1)

   

    def __enter__(self) -> "GestureDetector":
        self.start(blocking=False)
        return self

    def __exit__(self, *_) -> None:
        self.stop()
