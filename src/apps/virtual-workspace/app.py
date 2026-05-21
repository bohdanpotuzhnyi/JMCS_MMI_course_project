from __future__ import annotations

import random
import sys
import tkinter as tk
from dataclasses import dataclass
from pathlib import Path
from tkinter import scrolledtext
from typing import Iterable

import cv2
from PIL import Image, ImageTk

from contracts.actions import ActionPayload, ActionType
from contracts.events import BaseEvent, GestureEvent, GestureType, VoiceEvent
from core.runtime import CollaborationRuntime
from infra.config.fusion_config import FusionConfig, load_fusion_config
from modalities.gesture import GestureDetector, GestureDetectorOptions
from modalities.voice import VoskVoiceAdapter
from modalities.voice.intent_from_transcript import configure_intent_rules

if __package__ in (None, ""):
    shape_puzzle_dir = Path(__file__).resolve().parents[1] / "shape-puzzle"
    sys.path.insert(0, str(shape_puzzle_dir))
    from math3d import create_cube, create_cuboid, create_diamond, create_sphere, project_to_2d, rotate_3d
else:
    shape_puzzle_dir = Path(__file__).resolve().parents[1] / "shape-puzzle"
    sys.path.insert(0, str(shape_puzzle_dir))
    from math3d import create_cube, create_cuboid, create_diamond, create_sphere, project_to_2d, rotate_3d


CANVAS_WIDTH = 1000
CANVAS_HEIGHT = 700


@dataclass
class WorkspaceObject:
    object_id: str
    object_type: str
    vertices: list
    faces: list
    x: float
    y: float
    size: float
    fill_color: str
    angle_x: float = 0.0
    angle_y: float = 0.0
    angle_z: float = 0.0


class VirtualWorkspaceApp:
    """Free-form 3D object manipulation sandbox built on the shared runtime."""

    app_id = "virtual-workspace"

    def __init__(
        self,
        runtime: CollaborationRuntime,
        *,
        fusion_config: FusionConfig | None = None,
    ) -> None:
        self.runtime = runtime
        self.fusion_config = fusion_config
        self.root = tk.Tk()
        self.root.title("Virtual Workspace 3D Sandbox")

        self.objects: dict[str, WorkspaceObject] = {}
        self.object_counter = 0
        self.selected_object_id: str | None = None
        self.mode = "idle"
        self._menu_open = False

        self._gesture_detector: GestureDetector | None = None
        self._voice_adapter: VoskVoiceAdapter | None = None
        self._preview_image: ImageTk.PhotoImage | None = None
        self._camera_background_id: int | None = None
        self._helper_widget: scrolledtext.ScrolledText | None = None

        self.last_pointer_x = CANVAS_WIDTH / 2
        self.last_pointer_y = CANVAS_HEIGHT / 2

        if self.fusion_config is not None and self.fusion_config.voice_phrases:
            configure_intent_rules(self.fusion_config.voice_phrases)

        self._build_ui()
        self._bind_shortcuts()
        self.runtime.register_app(self)
        self.runtime.bus.subscribe_events(self._on_runtime_event)
        self.runtime.bus.subscribe_actions(self._on_runtime_action)
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        self.update_canvas()

    def _build_ui(self) -> None:
        outer = tk.Frame(self.root, padx=12, pady=12)
        outer.pack(fill=tk.BOTH, expand=True)

        controls = tk.Frame(outer)
        controls.pack(fill=tk.X, pady=(0, 10))

        tk.Button(controls, text="Start Camera", command=self.start_gesture_input).pack(side=tk.LEFT)
        tk.Button(controls, text="Start Voice", command=self.start_voice_input).pack(side=tk.LEFT, padx=(8, 0))
        tk.Button(controls, text="Stop Inputs", command=self.stop_inputs).pack(side=tk.LEFT, padx=(8, 0))

        self.status_var = tk.StringVar(
            value=(
                "Use voice and gesture only. The helper panel lists the currently configured commands."
            )
        )
        tk.Label(controls, textvariable=self.status_var, anchor="w").pack(
            side=tk.LEFT,
            padx=(12, 0),
            fill=tk.X,
            expand=True,
        )

        body = tk.Frame(outer)
        body.pack(fill=tk.BOTH, expand=True)
        body.grid_columnconfigure(0, weight=1)
        body.grid_columnconfigure(1, weight=0)
        body.grid_rowconfigure(0, weight=1)

        canvas_frame = tk.Frame(body)
        canvas_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 12))

        self.canvas = tk.Canvas(
            canvas_frame,
            width=CANVAS_WIDTH,
            height=CANVAS_HEIGHT,
            bg="#12161c",
            highlightthickness=0,
        )
        self.canvas.pack(fill=tk.BOTH, expand=True)

        self.canvas.create_text(
            CANVAS_WIDTH // 2,
            36,
            text="VIRTUAL WORKSPACE",
            fill="#ffffff",
            font=("Impact", 28, "normal"),
            tags="static",
        )
        self.canvas.create_text(
            CANVAS_WIDTH // 2,
            72,
            text="Say a configured command from the helper panel to create or manipulate objects",
            fill="#ffcc66",
            font=("Arial", 12, "bold"),
            tags="static",
        )

        sidebar = tk.Frame(body, width=360)
        sidebar.grid(row=0, column=1, sticky="ns")
        sidebar.grid_propagate(False)

        self.workspace_var = tk.StringVar(value="Workspace state: idle")
        tk.Label(sidebar, textvariable=self.workspace_var, anchor="w", fg="#666666").pack(fill=tk.X)

        self.event_var = tk.StringVar(value="Last modality event: none")
        tk.Label(sidebar, textvariable=self.event_var, anchor="w", fg="#555555").pack(fill=tk.X, pady=(4, 8))

        tk.Label(sidebar, text="Helper", anchor="w", font=("Arial", 11, "bold")).pack(fill=tk.X)
        self._helper_widget = scrolledtext.ScrolledText(
            sidebar,
            height=18,
            wrap=tk.WORD,
            state=tk.DISABLED,
            font=("Menlo", 10),
        )
        self._helper_widget.pack(fill=tk.BOTH, expand=True)
        self._set_helper_text(self._build_helper_text())

        tk.Label(sidebar, text="Runtime Log", anchor="w", font=("Arial", 11, "bold")).pack(fill=tk.X, pady=(10, 0))
        self.log_widget = scrolledtext.ScrolledText(
            sidebar,
            height=12,
            wrap=tk.WORD,
            state=tk.DISABLED,
            font=("Menlo", 11),
        )
        self.log_widget.pack(fill=tk.BOTH, expand=True, pady=(6, 0))

    def _bind_shortcuts(self) -> None:
        self.root.bind("<Button-1>", self._on_canvas_click)
        self.root.bind("<Escape>", lambda _event: self._set_mode("idle"))

    def run(self) -> None:
        self.root.mainloop()

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
            self.canvas.configure(bg="#12161c")
        if self._voice_adapter is not None:
            self._voice_adapter.stop()
            self._voice_adapter = None
        self.status_var.set("Stopped camera and voice inputs.")

    def handle_action(self, action: ActionPayload) -> None:
        self.root.after(0, lambda: self._apply_action(action))

    def _apply_action(self, action: ActionPayload) -> None:
        if action.type == ActionType.UPDATE_POINTER:
            self._handle_pointer_update(action)
            return
        if action.type == ActionType.CREATE_OBJECT and action.object_type:
            self._create_object(action.object_type)
            return
        if action.type == ActionType.SELECT_OBJECT:
            self._select_nearest_object(action.position)
            return
        if action.type == ActionType.MOVE_OBJECT:
            self._move_selected(action)
            return
        if action.type == ActionType.SET_INTERACTION_MODE and action.mode:
            self._set_mode(action.mode)
            return
        if action.type == ActionType.DELETE_OBJECT:
            self._delete_selected()
            return
        if action.type == ActionType.RESET_APP:
            self._reset_workspace()
            return
        if action.type == ActionType.DESELECT_OBJECT:
            self.selected_object_id = None
            self.mode = "idle"
            self.update_canvas()
            return
        if action.type == ActionType.OPEN_MENU:
            self._menu_open = True
            self.workspace_var.set("Workspace state: menu open")
            return
        if action.type == ActionType.CLOSE_MENU:
            self._menu_open = False
            self.workspace_var.set("Workspace state: menu closed")
            return

    def _geometry_for_type(self, shape_type: str) -> tuple[list, list]:
        if shape_type == "cube":
            return create_cube(1.0)
        if shape_type == "cuboid":
            return create_cuboid(2.0, 1.0, 0.5)
        if shape_type == "sphere":
            return create_sphere(0.8)
        if shape_type == "diamond":
            return create_diamond(1.0)
        raise ValueError(f"Unsupported object type: {shape_type}")

    def _create_object(self, shape_type: str) -> None:
        self.object_counter += 1
        object_id = f"{shape_type}-{self.object_counter}"
        vertices, faces = self._geometry_for_type(shape_type)
        obj = WorkspaceObject(
            object_id=object_id,
            object_type=shape_type,
            vertices=vertices,
            faces=faces,
            x=self.last_pointer_x,
            y=self.last_pointer_y,
            size=55,
            fill_color=random.choice(["#ffd166", "#8ecae6", "#90be6d", "#f4978e"]),
            angle_x=random.choice([0, 15, 30]),
            angle_y=random.choice([0, 20, 40]),
        )
        self.objects[object_id] = obj
        self.selected_object_id = object_id
        self.mode = "idle"
        self.status_var.set(f"Created {object_id}.")
        self.update_canvas()

    def _handle_pointer_update(self, action: ActionPayload) -> None:
        if action.position is None:
            return

        new_x = action.position.x * CANVAS_WIDTH
        new_y = action.position.y * CANVAS_HEIGHT
        delta_x = action.delta.dx * CANVAS_WIDTH if action.delta else new_x - self.last_pointer_x
        delta_y = action.delta.dy * CANVAS_HEIGHT if action.delta else new_y - self.last_pointer_y
        self.last_pointer_x = new_x
        self.last_pointer_y = new_y

        selected = self._selected_object()
        if selected is not None:
            if self.mode == "dragging":
                selected.x += delta_x
                selected.y += delta_y
            elif self.mode == "rotating":
                palm_delta = action.metadata.get("palm_delta") or {}
                palm_delta_x = palm_delta.get("dx", 0.0) * CANVAS_WIDTH
                palm_delta_y = palm_delta.get("dy", 0.0) * CANVAS_HEIGHT
                if abs(palm_delta_x) > 2:
                    selected.angle_y += palm_delta_x * 0.18
                if abs(palm_delta_y) > 2:
                    selected.angle_x -= palm_delta_y * 0.18
            elif self.mode == "resizing":
                pinch_delta = action.metadata.get("pinch_delta")
                if pinch_delta is not None:
                    selected.size = max(20, min(220, selected.size + pinch_delta * CANVAS_WIDTH * 0.8))

        self.update_canvas()

    def _select_nearest_object(self, position) -> None:
        if position is not None:
            self.last_pointer_x = position.x * CANVAS_WIDTH
            self.last_pointer_y = position.y * CANVAS_HEIGHT

        best_id = None
        best_dist = 99999.0
        for object_id, obj in self.objects.items():
            dist = ((obj.x - self.last_pointer_x) ** 2 + (obj.y - self.last_pointer_y) ** 2) ** 0.5
            if dist < 140 and dist < best_dist:
                best_id = object_id
                best_dist = dist

        self.selected_object_id = best_id
        self.mode = "idle" if best_id is not None else self.mode
        if best_id is None:
            self.status_var.set("Nothing selected at that position.")
        else:
            self.status_var.set(f"Selected {best_id}.")
        self.update_canvas()

    def _move_selected(self, action: ActionPayload) -> None:
        selected = self._selected_object()
        if selected is None:
            self.status_var.set("Move ignored: no selected object.")
            return

        if action.position is not None and action.delta is None:
            selected.x = action.position.x * CANVAS_WIDTH
            selected.y = action.position.y * CANVAS_HEIGHT
        elif action.delta is not None:
            selected.x += action.delta.dx * CANVAS_WIDTH
            selected.y += action.delta.dy * CANVAS_HEIGHT
        self.status_var.set(f"Moved {selected.object_id}.")
        self.update_canvas()

    def _set_mode(self, mode: str) -> None:
        if mode == "idle":
            self.mode = "idle"
            self.workspace_var.set("Workspace state: idle")
            self.status_var.set("Interaction mode reset.")
            self.update_canvas()
            return

        if self.selected_object_id is None:
            self.status_var.set(f"Mode '{mode}' ignored: no selected object.")
            return
        self.mode = mode
        self.workspace_var.set(f"Workspace state: {mode}")
        self.status_var.set(f"Mode: {mode}")
        self.update_canvas()

    def _delete_selected(self) -> None:
        selected = self._selected_object()
        if selected is None:
            self.status_var.set("Delete ignored: no selected object.")
            return
        del self.objects[selected.object_id]
        self.selected_object_id = None
        self.mode = "idle"
        self.status_var.set(f"Deleted {selected.object_id}.")
        self.update_canvas()

    def _reset_workspace(self) -> None:
        self.objects.clear()
        self.object_counter = 0
        self.selected_object_id = None
        self.mode = "idle"
        self.workspace_var.set("Workspace state: reset")
        self.status_var.set("Workspace reset.")
        self.update_canvas()

    def _selected_object(self) -> WorkspaceObject | None:
        if self.selected_object_id is None:
            return None
        return self.objects.get(self.selected_object_id)

    def _build_helper_text(self) -> str:
        if self.fusion_config is None:
            return "No fusion config loaded."

        lines: list[str] = []
        lines.append("Voice Commands")
        lines.append("")
        for intent in sorted(self.fusion_config.voice_phrases):
            phrases = self.fusion_config.voice_phrases[intent]
            rule = self.fusion_config.voice_actions.get(intent)
            action_desc = self._describe_action(rule.action if rule is not None else None, rule)
            lines.append(f"{intent}")
            lines.append(f"  phrases: {', '.join(phrases)}")
            if action_desc:
                lines.append(f"  action: {action_desc}")
            lines.append("")

        lines.append("Gesture Commands")
        lines.append("")
        gesture_names = self._gesture_names()
        for gesture_name in gesture_names:
            rule = self.fusion_config.gesture_actions.get(gesture_name)
            action_desc = self._describe_action(rule.action if rule is not None else None, rule)
            lines.append(f"{gesture_name}")
            if action_desc:
                lines.append(f"  action: {action_desc}")
            lines.append("")

        lines.append("Notes")
        lines.append("  click on canvas: synthetic point/select")
        lines.append("  Esc: leave current interaction mode")
        return "\n".join(lines).strip()

    def _gesture_names(self) -> list[str]:
        names: Iterable[str]
        if self.fusion_config is None:
            names = ()
        elif self.fusion_config.gesture_include:
            names = self.fusion_config.gesture_include
        else:
            names = self.fusion_config.gesture_actions.keys()
        return sorted(names)

    def _describe_action(self, action_name: str | None, rule) -> str:
        if action_name is None:
            return ""
        if rule is None:
            return action_name
        if action_name == "create_object" and rule.object_type:
            return f"{action_name} ({rule.object_type})"
        if action_name == "set_interaction_mode" and rule.mode:
            return f"{action_name} ({rule.mode})"
        if action_name == "move_object" and rule.use_position:
            return f"{action_name} (use pointer position)"
        return action_name

    def _set_helper_text(self, text: str) -> None:
        if self._helper_widget is None:
            return
        self._helper_widget.configure(state=tk.NORMAL)
        self._helper_widget.delete("1.0", tk.END)
        self._helper_widget.insert(tk.END, f"{text}\n")
        self._helper_widget.configure(state=tk.DISABLED)

    def update_canvas(self) -> None:
        self.canvas.delete("dynamic")

        self.canvas.create_oval(
            self.last_pointer_x - 5,
            self.last_pointer_y - 5,
            self.last_pointer_x + 5,
            self.last_pointer_y + 5,
            fill="white" if self.mode != "idle" else "#ff5c5c",
            outline="",
            tags="dynamic",
        )

        if not self.objects:
            self.canvas.create_text(
                CANVAS_WIDTH // 2,
                CANVAS_HEIGHT // 2,
                text="Workspace is empty. Create a 3D object to begin.",
                fill="#d8d8d8",
                font=("Arial", 16, "italic"),
                tags="dynamic",
            )
            return

        ordered_objects = sorted(self.objects.values(), key=lambda obj: obj.y)
        for obj in ordered_objects:
            rotated_vertices = rotate_3d(obj.vertices, obj.angle_x, obj.angle_y, obj.angle_z)
            projected = project_to_2d(
                rotated_vertices,
                fov=400,
                viewer_distance=4,
                scale=obj.size / 60.0,
                screen_center=(obj.x, obj.y),
            )
            faces_with_z: list[tuple[float, tuple[int, ...]]] = []
            for face in obj.faces:
                avg_z = sum(rotated_vertices[idx][2] for idx in face) / len(face)
                faces_with_z.append((avg_z, face))
            faces_with_z.sort(key=lambda item: item[0], reverse=True)

            fill_color = obj.fill_color
            outline = "#1e1e1e"
            if obj.object_id == self.selected_object_id:
                if self.mode == "dragging":
                    fill_color = "#ff66cc"
                elif self.mode == "rotating":
                    fill_color = "#ffaa00"
                elif self.mode == "resizing":
                    fill_color = "#44ffff"
                else:
                    fill_color = "#f72585"
                outline = "#ffffff"

            for _avg_z, face in faces_with_z:
                points: list[float] = []
                for idx in face:
                    points.extend([projected[idx][0], projected[idx][1]])
                self.canvas.create_polygon(
                    points,
                    fill=fill_color,
                    outline=outline,
                    width=2 if obj.object_id == self.selected_object_id else 1,
                    tags="dynamic",
                )

            self.canvas.create_text(
                obj.x,
                obj.y + obj.size * 0.9,
                text=obj.object_id,
                fill="#f3f3f3",
                font=("Arial", 10, "bold"),
                tags="dynamic",
            )

    def _on_canvas_click(self, event: tk.Event) -> None:
        gesture = GestureEvent(
            confidence=1.0,
            gesture=GestureType.POINT,
            position={
                "x": max(0.0, min(1.0, event.x / CANVAS_WIDTH)),
                "y": max(0.0, min(1.0, event.y / CANVAS_HEIGHT)),
            },
            hand="unknown",
        )
        self.runtime.handle_gesture(gesture)

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
                f"position={action.position.model_dump() if action.position else None} "
                f"mode={action.mode}"
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
            self.canvas.configure(bg="#12161c")

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
                    tags="background",
                )
            else:
                self.canvas.itemconfigure(self._camera_background_id, image=self._preview_image)
            self.canvas.tag_lower("background")

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
    config_path = Path(__file__).with_name("fusion-3d.conf")
    fusion_config = load_fusion_config(config_path)
    runtime = CollaborationRuntime(fusion_config=fusion_config)
    app = VirtualWorkspaceApp(runtime, fusion_config=fusion_config)
    app.run()


if __name__ == "__main__":
    main()
