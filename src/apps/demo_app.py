from __future__ import annotations

import random
import tkinter as tk
from tkinter import scrolledtext
from dataclasses import dataclass

import cv2
from PIL import Image, ImageTk

from contracts.actions import ActionPayload, ActionType
from contracts.events import BaseEvent, GestureEvent, GestureType, NormalizedPosition, VoiceEvent
from core import CollaborationRuntime
from modalities.gesture import GestureDetector, GestureDetectorOptions
from modalities.voice import VoskVoiceAdapter


CANVAS_WIDTH = 800
CANVAS_HEIGHT = 500
DEFAULT_SQUARE_SIZE = 90


@dataclass
class SquareState:
    object_id: str
    rect_id: int
    label_id: int
    angle: float = 0.0


class DemoCanvasApp:
    """Small canvas-based demo app for exercising the fusion/runtime path."""

    app_id = "demo"

    def __init__(self, runtime: CollaborationRuntime) -> None:
        self.runtime = runtime
        self.root = tk.Tk()
        self.root.title("Multimodal Demo")

        self._menu_open = False
        self._counter = 0
        self._selected_object_id: str | None = None
        self._squares: dict[str, SquareState] = {}
        self._gesture_detector: GestureDetector | None = None
        self._voice_adapter: VoskVoiceAdapter | None = None
        self._preview_image: ImageTk.PhotoImage | None = None
        self._camera_background_id: int | None = None

        self._build_ui()
        self._bind_shortcuts()
        self.runtime.register_app(self)
        self.runtime.bus.subscribe_events(self._on_runtime_event)
        self.runtime.bus.subscribe_actions(self._on_runtime_action)
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    def _build_ui(self) -> None:
        outer = tk.Frame(self.root, padx=12, pady=12)
        outer.pack(fill=tk.BOTH, expand=True)

        controls = tk.Frame(outer)
        controls.pack(fill=tk.X, pady=(0, 10))

        tk.Button(controls, text="Add Square", command=self.add_square).pack(side=tk.LEFT)
        tk.Button(controls, text="Delete Selected", command=self._delete_selected_locally).pack(
            side=tk.LEFT,
            padx=(8, 0),
        )
        tk.Button(controls, text="Start Camera", command=self.start_gesture_input).pack(
            side=tk.LEFT,
            padx=(8, 0),
        )
        tk.Button(controls, text="Start Voice", command=self.start_voice_input).pack(
            side=tk.LEFT,
            padx=(8, 0),
        )
        tk.Button(controls, text="Stop Inputs", command=self.stop_inputs).pack(
            side=tk.LEFT,
            padx=(8, 0),
        )

        self.status_var = tk.StringVar(
            value=(
                "Click canvas to point/select. Arrow keys move. Q/E rotate. "
                "N adds a square. Start Camera/Voice for live input."
            )
        )
        tk.Label(controls, textvariable=self.status_var, anchor="w").pack(
            side=tk.LEFT,
            padx=(12, 0),
            fill=tk.X,
            expand=True,
        )

        self.canvas = tk.Canvas(
            outer,
            width=CANVAS_WIDTH,
            height=CANVAS_HEIGHT,
            bg="#f4f1ea",
            highlightthickness=0,
        )
        self.canvas.pack(fill=tk.BOTH, expand=True)

        self.menu_label = tk.Label(
            outer,
            text="Menu closed",
            anchor="w",
            fg="#666666",
        )
        self.menu_label.pack(fill=tk.X, pady=(8, 0))

        self.event_var = tk.StringVar(value="Last modality event: none")
        tk.Label(outer, textvariable=self.event_var, anchor="w", fg="#555555").pack(fill=tk.X)

        self.log_widget = scrolledtext.ScrolledText(
            outer,
            height=10,
            wrap=tk.WORD,
            state=tk.DISABLED,
            font=("Menlo", 11),
        )
        self.log_widget.pack(fill=tk.BOTH, expand=False, pady=(8, 0))

    def _bind_shortcuts(self) -> None:
        self.root.bind("<Button-1>", self._on_canvas_click)
        self.root.bind("<n>", lambda _event: self.add_square())
        self.root.bind("<Delete>", lambda _event: self._emit_delete_action())
        self.root.bind("<BackSpace>", lambda _event: self._emit_delete_action())
        self.root.bind("<Left>", lambda _event: self._emit_voice_intent("left", "move left"))
        self.root.bind("<Right>", lambda _event: self._emit_voice_intent("right", "move right"))
        self.root.bind("<Up>", lambda _event: self._emit_voice_intent("up", "move up"))
        self.root.bind("<Down>", lambda _event: self._emit_voice_intent("down", "move down"))
        self.root.bind("<q>", lambda _event: self._emit_voice_intent("rotate-left", "rotate left"))
        self.root.bind("<e>", lambda _event: self._emit_voice_intent("rotate-right", "rotate right"))
        self.root.bind("<m>", lambda _event: self._emit_menu_toggle())

    def run(self) -> None:
        if not self._squares:
            self.add_square()
            self.add_square()
        self.root.mainloop()

    def add_square(self) -> None:
        self._counter += 1
        object_id = f"square-{self._counter}"
        size = DEFAULT_SQUARE_SIZE
        x = random.randint(80, CANVAS_WIDTH - size - 80)
        y = random.randint(80, CANVAS_HEIGHT - size - 80)
        fill = random.choice(["#d95f5f", "#5f8dd9", "#5fbf7a", "#d9a85f"])

        rect_id = self.canvas.create_rectangle(
            x,
            y,
            x + size,
            y + size,
            fill=fill,
            outline="#333333",
            width=2,
        )
        label_id = self.canvas.create_text(
            x + size / 2,
            y + size / 2,
            text=f"{object_id}\n0°",
            fill="white",
            font=("Helvetica", 12, "bold"),
            justify="center",
        )

        self._squares[object_id] = SquareState(
            object_id=object_id,
            rect_id=rect_id,
            label_id=label_id,
        )
        self._select_square(object_id)
        self.status_var.set(f"Added {object_id}.")

    def handle_action(self, action: ActionPayload) -> None:
        self.root.after(0, lambda: self._apply_action(action))

    def _apply_action(self, action: ActionPayload) -> None:
        if action.type == ActionType.SELECT_OBJECT:
            self._handle_select(action)
            return
        if action.type == ActionType.MOVE_OBJECT:
            self._handle_move(action)
            return
        if action.type == ActionType.ROTATE_OBJECT:
            self._handle_rotate(action)
            return
        if action.type == ActionType.DELETE_OBJECT:
            self._handle_delete(action)
            return
        if action.type == ActionType.OPEN_MENU:
            self._menu_open = True
            self.menu_label.config(text="Menu open")
            self.status_var.set("Open-palm gesture mapped to menu open.")
            return
        if action.type == ActionType.CLOSE_MENU:
            self._menu_open = False
            self.menu_label.config(text="Menu closed")
            self.status_var.set("Fist gesture mapped to menu close.")
            return

    def start_gesture_input(self) -> None:
        if self._gesture_detector is not None:
            self.status_var.set("Gesture input already running.")
            return
        try:
            detector = GestureDetector(
                GestureDetectorOptions(
                    show_preview=False,
                    on_error=self._handle_gesture_error,
                    on_preview=self._handle_gesture_preview,
                )
            )
            detector.on(self.runtime.handle_gesture)
            detector.start(blocking=False)
        except Exception as exc:
            self.status_var.set(f"Could not start camera input: {exc}")
            return
        self._gesture_detector = detector
        self.status_var.set("Camera gesture input started.")

    def start_voice_input(self) -> None:
        if self._voice_adapter is not None:
            self.status_var.set("Voice input already running.")
            return
        try:
            adapter = VoskVoiceAdapter(
                on_voice_event=self.runtime.handle_voice,
                on_error=self._handle_voice_error,
            )
            adapter.start()
        except Exception as exc:
            self.status_var.set(f"Could not start voice input: {exc}")
            return
        self._voice_adapter = adapter
        self.status_var.set("Voice input started.")

    def stop_inputs(self) -> None:
        if self._gesture_detector is not None:
            self._gesture_detector.stop()
            self._gesture_detector = None
            self._preview_image = None
            if self._camera_background_id is not None:
                self.canvas.delete(self._camera_background_id)
                self._camera_background_id = None
            self.canvas.configure(bg="#f4f1ea")
        if self._voice_adapter is not None:
            self._voice_adapter.stop()
            self._voice_adapter = None
        self.status_var.set("Stopped camera and voice inputs.")

    def _handle_select(self, action: ActionPayload) -> None:
        target_id = action.target_id or self._find_square_at(action.position)
        if target_id is None:
            self.status_var.set("Nothing selected at that position.")
            return
        self._select_square(target_id)
        self.status_var.set(f"Selected {target_id}.")

    def _handle_move(self, action: ActionPayload) -> None:
        target_id = action.target_id or self._selected_object_id
        if target_id is None or target_id not in self._squares or action.delta is None:
            self.status_var.set("Move ignored: no selected square.")
            return

        dx = action.delta.dx * CANVAS_WIDTH
        dy = action.delta.dy * CANVAS_HEIGHT
        square = self._squares[target_id]
        self.canvas.move(square.rect_id, dx, dy)
        self.canvas.move(square.label_id, dx, dy)
        self.status_var.set(f"Moved {target_id} by ({dx:.0f}, {dy:.0f}).")

    def _handle_rotate(self, action: ActionPayload) -> None:
        target_id = action.target_id or self._selected_object_id
        if target_id is None or target_id not in self._squares or action.rotation is None:
            self.status_var.set("Rotate ignored: no selected square.")
            return

        square = self._squares[target_id]
        square.angle = (square.angle + action.rotation) % 360
        self.canvas.itemconfigure(square.label_id, text=f"{target_id}\n{square.angle:.0f}°")
        self.status_var.set(f"Rotated {target_id} to {square.angle:.0f}°.")

    def _handle_delete(self, action: ActionPayload) -> None:
        target_id = action.target_id or self._selected_object_id
        if target_id is None or target_id not in self._squares:
            self.status_var.set("Delete ignored: no selected square.")
            return

        square = self._squares.pop(target_id)
        self.canvas.delete(square.rect_id)
        self.canvas.delete(square.label_id)
        self._selected_object_id = None
        self.status_var.set(f"Deleted {target_id}.")

    def _on_canvas_click(self, event: tk.Event) -> None:
        position = NormalizedPosition(
            x=max(0.0, min(1.0, event.x / CANVAS_WIDTH)),
            y=max(0.0, min(1.0, event.y / CANVAS_HEIGHT)),
        )
        gesture = GestureEvent(
            confidence=1.0,
            gesture=GestureType.POINT,
            position=position,
            hand="unknown",
        )
        self.runtime.handle_gesture(gesture)

    def _emit_voice_intent(self, intent: str, transcript: str) -> None:
        voice = VoiceEvent(
            confidence=1.0,
            transcript=transcript,
            is_final=True,
            intent=intent,
        )
        self.runtime.handle_voice(voice)

    def _emit_menu_toggle(self) -> None:
        action_type = ActionType.CLOSE_MENU if self._menu_open else ActionType.OPEN_MENU
        self.handle_action(ActionPayload(type=action_type))

    def _emit_delete_action(self) -> None:
        self.handle_action(ActionPayload(type=ActionType.DELETE_OBJECT))

    def _delete_selected_locally(self) -> None:
        self._emit_delete_action()

    def _find_square_at(self, position: object) -> str | None:
        if position is None:
            return None
        canvas_x = position.x * CANVAS_WIDTH
        canvas_y = position.y * CANVAS_HEIGHT
        overlapping = self.canvas.find_overlapping(canvas_x, canvas_y, canvas_x, canvas_y)

        for item_id in reversed(overlapping):
            for object_id, square in self._squares.items():
                if square.rect_id == item_id or square.label_id == item_id:
                    return object_id
        return None

    def _select_square(self, object_id: str) -> None:
        self._selected_object_id = object_id
        for current_id, square in self._squares.items():
            outline = "#111111" if current_id == object_id else "#333333"
            width = 4 if current_id == object_id else 2
            self.canvas.itemconfigure(square.rect_id, outline=outline, width=width)

    def _on_runtime_event(self, event: BaseEvent) -> None:
        def update() -> None:
            if isinstance(event, GestureEvent):
                self.event_var.set(
                    f"Last modality event: gesture={event.gesture.value} confidence={event.confidence:.2f}"
                )
                self._append_log(
                    f"GESTURE  gesture={event.gesture.value} hand={event.hand or 'unknown'} "
                    f"pos=({event.position.x:.2f}, {event.position.y:.2f}) conf={event.confidence:.2f}"
                )
            elif isinstance(event, VoiceEvent):
                self.event_var.set(
                    f"Last modality event: voice='{event.transcript}' intent={event.intent or 'none'}"
                )
                self._append_log(
                    f"VOICE    transcript='{event.transcript}' intent={event.intent or 'none'} "
                    f"conf={event.confidence:.2f}"
                )

        self.root.after(0, update)

    def _on_runtime_action(self, action: ActionPayload) -> None:
        def update() -> None:
            self._append_log(
                f"ACTION   type={action.type.value} target={action.target_id or 'auto'} "
                f"delta={action.delta.model_dump() if action.delta else None} "
                f"rotation={action.rotation} "
                f"position={action.position.model_dump() if action.position else None}"
            )

        self.root.after(0, update)

    def _handle_voice_error(self, error: str) -> None:
        def update() -> None:
            self.status_var.set(f"Voice input error: {error}")
            self._append_log(f"VOICEERR error={error}")

        self.root.after(0, update)

    def _handle_gesture_error(self, error: str) -> None:
        def update() -> None:
            self.status_var.set(f"Gesture input error: {error}")
            self._append_log(f"GESTERR error={error}")
            self._gesture_detector = None
            self._preview_image = None
            if self._camera_background_id is not None:
                self.canvas.delete(self._camera_background_id)
                self._camera_background_id = None
            self.canvas.configure(bg="#f4f1ea")

        self.root.after(0, update)

    def _handle_gesture_preview(self, frame) -> None:
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        image = Image.fromarray(rgb)
        image = image.resize((CANVAS_WIDTH, CANVAS_HEIGHT))

        def update() -> None:
            self._preview_image = ImageTk.PhotoImage(image=image)
            if self._camera_background_id is None:
                self._camera_background_id = self.canvas.create_image(
                    0,
                    0,
                    image=self._preview_image,
                    anchor="nw",
                )
            else:
                self.canvas.itemconfigure(self._camera_background_id, image=self._preview_image)
            self.canvas.tag_lower(self._camera_background_id)

        self.root.after(0, update)

    def _on_close(self) -> None:
        self.stop_inputs()
        self.root.destroy()

    def _append_log(self, line: str) -> None:
        self.log_widget.configure(state=tk.NORMAL)
        self.log_widget.insert(tk.END, f"{line}\n")
        self.log_widget.see(tk.END)
        self.log_widget.configure(state=tk.DISABLED)


def main() -> None:
    runtime = CollaborationRuntime()
    app = DemoCanvasApp(runtime)
    app.run()


if __name__ == "__main__":
    main()
