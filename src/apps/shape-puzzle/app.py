import tkinter as tk
import math
import random
from pathlib import Path
from typing import Dict, Optional

import cv2
from PIL import Image, ImageTk

from contracts.actions import ActionPayload, ActionType
from core.runtime import CollaborationRuntime
from infra.config.fusion_config import FusionConfig, load_fusion_config
from modalities.gesture import GestureDetector, GestureDetectorOptions
from modalities.voice.intent_from_transcript import configure_intent_rules
from modalities.voice import VoskVoiceAdapter

from .math3d import create_cube, create_cuboid, create_sphere, create_diamond, rotate_3d, project_to_2d

CANVAS_WIDTH = 1000
CANVAS_HEIGHT = 700

class GeometricObject:
    def __init__(self, obj_id: str, obj_type: str, vertices: list, faces: list, x: float, y: float, size: float):
        self.obj_id = obj_id
        self.obj_type = obj_type
        self.vertices = vertices
        self.faces = faces
        self.x = x
        self.y = y
        self.size = size
        self.angle_x = 0.0
        self.angle_y = 0.0
        self.angle_z = 0.0
        self.matched = False
        self.is_target = False
        self.filled = False
        self.score_text = None

class ShapePuzzleApp:
    app_id = "shape-puzzle"

    def __init__(self, runtime: CollaborationRuntime, fusion_config: FusionConfig | None = None):
        self.runtime = runtime
        self.fusion_config = fusion_config
        self.root = tk.Tk()
        self.root.title("3D-to-2D Shape Puzzle Game")

        self.objects: Dict[str, GeometricObject] = {}
        self.targets: Dict[str, GeometricObject] = {}
        self.selected_object_id: Optional[str] = None
        self.object_counter = 0

        self._gesture_detector = None
        self._voice_adapter = None
        
        self._preview_image = None
        self._camera_background_id = None
        
        self.last_pointer_x = 0
        self.last_pointer_y = 0
        self.mode = "idle" 
        
        self.game_over_score = None
        if self.fusion_config is not None and self.fusion_config.voice_phrases:
            configure_intent_rules(self.fusion_config.voice_phrases)

        self._build_ui()
        self._spawn_targets()
        
        self.runtime.register_app(self)
        
        self.root.bind("<n>", lambda _: self._create_object("sphere"))
        self.root.bind("<c>", lambda _: self._create_object("cube"))
        self.root.bind("<b>", lambda _: self._create_object("cuboid"))
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        
        self.update_canvas()

    def _build_ui(self):
        top_frame = tk.Frame(self.root)
        top_frame.pack(fill=tk.X, padx=10, pady=5)

        tk.Button(top_frame, text="Start Game Engine", command=self.start_inputs, bg="#44ff44", font=("Arial", 10, "bold")).pack(side=tk.LEFT)
        tk.Button(top_frame, text="Stop Stream", command=self.stop_inputs).pack(side=tk.LEFT)
        
        self.log_var = tk.StringVar(value="Waiting to start...")
        tk.Label(top_frame, textvariable=self.log_var, fg="#00ccff", bg="#000000", font=("Arial", 12, "bold")).pack(side=tk.LEFT, padx=30)

        self.canvas = tk.Canvas(self.root, width=CANVAS_WIDTH, height=CANVAS_HEIGHT, bg="#1a1a1a")
        self.canvas.pack(fill=tk.BOTH, expand=True)

        self.canvas.create_text(
            CANVAS_WIDTH // 2, 40, text="FIT THE 3D OBJECTS IN THIS", 
            fill="#ffffff", font=("Impact", 28, "normal"), tags="static", justify="center"
        )
        self.canvas.create_text(
            CANVAS_WIDTH // 2, 80, text="Say 'Insert' to lock your piece into the matched Cyan 3D Silhouette!", 
            fill="#ffcc00", font=("Arial", 12, "bold"), tags="static", justify="center"
        )

    def _spawn_targets(self):
        self.targets.clear()
        
        shapes = ["cube", "cuboid", "sphere", "diamond"]
        # Generate 3 random unique target shapes for this puzzle session
        chosen_shapes = random.sample(shapes, 3)
        positions = [(800, 150), (800, 350), (800, 550)]

        for i, shape_type in enumerate(chosen_shapes):
            target_id = f"target-{shape_type}-{i}"
            pos_x, pos_y = positions[i]

            if shape_type == "cube":
                v, e = create_cube(1.0)
            elif shape_type == "cuboid":
                v, e = create_cuboid(2.0, 1.0, 0.5)
            elif shape_type == "sphere":
                v, e = create_sphere(0.8)
            elif shape_type == "diamond":
                v, e = create_diamond(1.0)

            obj = GeometricObject(target_id, shape_type, v, e, pos_x, pos_y, size=60)
            obj.is_target = True
            
            # Randomize 3D orientations wildly to increase puzzle difficulty
            if shape_type in ["cube", "cuboid", "diamond"]:
                obj.angle_x = random.randint(-180, 180)
                obj.angle_y = random.randint(-180, 180)
                
            self.targets[target_id] = obj

    def start_inputs(self):
        if not self._gesture_detector:
            self._gesture_detector = GestureDetector(GestureDetectorOptions(
                show_preview=False,
                on_preview=self._handle_gesture_preview
            ))
            self._gesture_detector.on(self.runtime.handle_gesture)
            self._gesture_detector.start(blocking=False)
            
        if not self._voice_adapter:
            self._voice_adapter = VoskVoiceAdapter(on_voice_event=self.runtime.handle_voice)
            self._voice_adapter.start()

        self.log_var.set("Camera logic active! Have fun playing.")

    def stop_inputs(self):
        if self._gesture_detector:
            self._gesture_detector.stop()
            self._gesture_detector = None
        if self._voice_adapter:
            self._voice_adapter.stop()
            self._voice_adapter = None
        self.log_var.set("Inputs stopped.")

    def _create_object(self, shape_type: str):
        self.object_counter += 1
        obj_id = f"{shape_type}-{self.object_counter}"
        
        start_x, start_y = self.last_pointer_x, self.last_pointer_y
        if start_x == 0 and start_y == 0:
            start_x, start_y = CANVAS_WIDTH / 2, CANVAS_HEIGHT / 2
        
        if shape_type == "cube":
            v, e = create_cube(1.0)
        elif shape_type == "cuboid":
            v, e = create_cuboid(2.0, 1.0, 0.5)
        elif shape_type == "sphere":
            v, e = create_sphere(0.8)
        elif shape_type == "diamond":
            v, e = create_diamond(1.0)
        else: return

        obj = GeometricObject(obj_id, shape_type, v, e, start_x, start_y, size=40)
        self.objects[obj_id] = obj
        self.root.after(0, self.update_canvas)
        self.log_var.set(f"Created solid '{shape_type}'")

    def handle_action(self, action: ActionPayload):
        self.root.after(0, lambda: self._apply_action(action))

    def _apply_action(self, action: ActionPayload):
        if action.type == ActionType.UPDATE_POINTER:
            self._handle_pointer_update(action)
        elif action.type == ActionType.CREATE_OBJECT and action.object_type:
            self._create_object(action.object_type)
        elif action.type == ActionType.SELECT_OBJECT:
            if action.metadata.get("modality") != "gesture":
                self._select_nearest_object(action.position)
        elif action.type == ActionType.MOVE_OBJECT:
            self._move_selected(action)
        elif action.type == ActionType.SET_INTERACTION_MODE and action.mode:
            self._set_mode(action.mode)
        elif action.type == ActionType.DELETE_OBJECT:
            self._delete_selected()
        elif action.type == ActionType.INSERT_OBJECT:
            self._insert_selected()
        elif action.type == ActionType.RESET_APP:
            self._restart_game()

    def _handle_pointer_update(self, action: ActionPayload):
        if action.position is None:
            return

        new_x = action.position.x * CANVAS_WIDTH
        new_y = action.position.y * CANVAS_HEIGHT
        delta_x = action.delta.dx * CANVAS_WIDTH if action.delta else new_x - self.last_pointer_x
        delta_y = action.delta.dy * CANVAS_HEIGHT if action.delta else new_y - self.last_pointer_y
        self.last_pointer_x = new_x
        self.last_pointer_y = new_y

        if self.selected_object_id and self.selected_object_id in self.objects:
            obj = self.objects[self.selected_object_id]

            if self.mode == "dragging":
                obj.x += delta_x
                obj.y += delta_y

            elif self.mode == "rotating":
                palm_delta = action.metadata.get("palm_delta") or {}
                palm_delta_x = palm_delta.get("dx", 0.0) * CANVAS_WIDTH
                palm_delta_y = palm_delta.get("dy", 0.0) * CANVAS_HEIGHT
                if abs(palm_delta_x) > 2:
                    obj.angle_y += palm_delta_x * 0.15
                if abs(palm_delta_y) > 2:
                    obj.angle_x -= palm_delta_y * 0.15

            elif self.mode == "resizing":
                pinch_delta = action.metadata.get("pinch_delta")
                if pinch_delta is not None:
                    obj.size = max(10, min(300, obj.size + pinch_delta * CANVAS_WIDTH * 0.8))

        self.root.after(0, self.update_canvas)

    def _select_nearest_object(self, position):
        if position is not None:
            self.last_pointer_x = position.x * CANVAS_WIDTH
            self.last_pointer_y = position.y * CANVAS_HEIGHT

        best_dist = 99999
        best_id = None
        for obj_id, obj in self.objects.items():
            if obj.matched:
                continue
            dist = math.hypot(obj.x - self.last_pointer_x, obj.y - self.last_pointer_y)
            if dist < 120 and dist < best_dist:
                best_dist = dist
                best_id = obj_id
        if best_id:
            self.selected_object_id = best_id
            self.mode = "idle"
            self.update_canvas()

    def _move_selected(self, action: ActionPayload):
        if not self.selected_object_id or self.selected_object_id not in self.objects:
            return

        obj = self.objects[self.selected_object_id]
        if action.position is not None and action.delta is None:
            obj.x = action.position.x * CANVAS_WIDTH
            obj.y = action.position.y * CANVAS_HEIGHT
            self.selected_object_id = None
            self.mode = "idle"
        elif action.delta is not None:
            obj.x += action.delta.dx * CANVAS_WIDTH
            obj.y += action.delta.dy * CANVAS_HEIGHT
        self.update_canvas()

    def _set_mode(self, mode: str):
        if mode == "idle":
            self.selected_object_id = None
            self.mode = "idle"
            self.log_var.set("UNSELECTED and DONE")
            self.update_canvas()
            return

        if self.selected_object_id:
            self.mode = mode
            self.log_var.set(f"Mode: {mode}")
            self.update_canvas()

    def _delete_selected(self):
        if self.selected_object_id and self.selected_object_id in self.objects:
            del self.objects[self.selected_object_id]
            self.selected_object_id = None
            self.mode = "idle"
            self.log_var.set("Shape deleted.")
            self.update_canvas()

    def _restart_game(self):
        self.objects.clear()
        self.object_counter = 0
        self._spawn_targets()
        self.game_over_score = None
        self.selected_object_id = None
        self.mode = "idle"
        self.log_var.set("Game Restarted with new Targets!")
        self.update_canvas()

    def _insert_selected(self):
        if not self.selected_object_id or self.selected_object_id not in self.objects:
            return

        obj = self.objects[self.selected_object_id]
        best_hole = None
        best_dist = 9999
        for hole in self.targets.values():
            if hole.filled:
                continue
            dist = math.hypot(obj.x - hole.x, obj.y - hole.y)
            if dist < best_dist:
                best_dist = dist
                best_hole = hole

        if best_hole and best_dist < 150:
            if best_hole.obj_type == obj.obj_type:
                final_score = self._score_insert(obj, best_hole, best_dist)
                obj.matched = True
                best_hole.filled = True
                best_hole.score_text = final_score
                self.selected_object_id = None
                self.mode = "idle"
                self.log_var.set(f"INSERT SUCCESS! Metric Score: {final_score:.1f}%")
                self._check_game_over()
            else:
                self.log_var.set("Wait, that is the wrong 3D geometry for this target!")
        else:
            self.log_var.set("No valid target underneath pointer to insert!")
        self.update_canvas()

    def _score_insert(self, obj, best_hole, best_dist):
        pos_score = max(0.0, 100 - (best_dist * 0.7))
        ratio = min(obj.size, best_hole.size) / max(obj.size, best_hole.size)
        scale_score = ratio * 100.0

        sym_x, sym_y = 360, 360
        if obj.obj_type == "cube":
            sym_x, sym_y = 90, 90
        elif obj.obj_type == "cuboid":
            sym_x, sym_y = 180, 180
        elif obj.obj_type == "diamond":
            sym_y = 90

        dx = abs((round(obj.angle_x) % sym_x) - (round(best_hole.angle_x) % sym_x))
        dx = min(dx, sym_x - dx)
        dy = abs((round(obj.angle_y) % sym_y) - (round(best_hole.angle_y) % sym_y))
        dy = min(dy, sym_y - dy)

        total_angle_error = dx + dy
        rot_score = 100.0 if obj.obj_type == "sphere" else max(0.0, 100 - (total_angle_error * 2.0))
        return (pos_score + scale_score + rot_score) / 3.0

    def _check_game_over(self):
        filled_holes = [t for t in self.targets.values() if t.filled]
        if len(filled_holes) == len(self.targets):
            total = sum(t.score_text for t in self.targets.values() if t.score_text is not None)
            average = total / len(self.targets)
            self.game_over_score = average
            self.log_var.set(f"VICTORY! OVERALL SCORE: {average:.1f}%. Say 'RESTART' to play again!")

    def update_canvas(self):
        self.canvas.delete("dynamic")
        
        # Cursor
        if not self.game_over_score:
            self.canvas.create_oval(
                self.last_pointer_x - 5, self.last_pointer_y - 5, 
                self.last_pointer_x + 5, self.last_pointer_y + 5, 
                fill="red" if self.mode == "idle" else "white", tags="dynamic"
            )
        
        # Draw Targets (Bottom Layer)
        for obj in self.targets.values():
            rotated_v = rotate_3d(obj.vertices, obj.angle_x, obj.angle_y, obj.angle_z)
            projected = project_to_2d(
                rotated_v, fov=400, viewer_distance=4, scale=obj.size / 60.0, 
                screen_center=(obj.x, obj.y)
            )
            faces_with_z = []
            for face in obj.faces:
                avg_z = sum(rotated_v[idx][2] for idx in face) / len(face)
                faces_with_z.append((avg_z, face))
            faces_with_z.sort(key=lambda x: x[0], reverse=True)
            
            fill_color = "#00e5ff" # Target Cyan
            for avg_z, face in faces_with_z:
                points = []
                for idx in face:
                    points.extend([projected[idx][0], projected[idx][1]])
                self.canvas.create_polygon(points, fill=fill_color, outline="#0088aa", width=1, tags="dynamic")
                
            if obj.score_text:
                self.canvas.create_rectangle(
                    obj.x + 60, obj.y - 18, obj.x + 190, obj.y + 18, 
                    fill="#111111", outline="#32a852", width=2, tags="dynamic"
                )
                self.canvas.create_text(
                    obj.x + 125, obj.y, text=f"{obj.score_text:.1f}%", 
                    fill="#32a852", font=("Consolas", 16, "bold"), tags="dynamic"
                )

        # Draw Player Objects (Top Layer)
        for obj in self.objects.values():
            rotated_v = rotate_3d(obj.vertices, obj.angle_x, obj.angle_y, obj.angle_z)
            projected = project_to_2d(
                rotated_v, fov=400, viewer_distance=4, scale=obj.size / 60.0, 
                screen_center=(obj.x, obj.y)
            )
            faces_with_z = []
            for face in obj.faces:
                avg_z = sum(rotated_v[idx][2] for idx in face) / len(face)
                faces_with_z.append((avg_z, face))
            faces_with_z.sort(key=lambda x: x[0], reverse=True)
            
            if obj.matched: fill_color = "#32a852" # Dark green success
            elif self.selected_object_id == obj.obj_id:
                if self.mode == "dragging": fill_color = "#ff66cc"
                elif self.mode == "rotating": fill_color = "#ffaa00"
                elif self.mode == "resizing": fill_color = "#44ffff"
                else: fill_color = "#ff00ff"
            else: fill_color = "yellow"

            for avg_z, face in faces_with_z:
                points = []
                for idx in face:
                    points.extend([projected[idx][0], projected[idx][1]])
                self.canvas.create_polygon(points, fill=fill_color, outline="#222222", width=1, tags="dynamic")

        if self.game_over_score is not None:
            self.canvas.create_rectangle(
                CANVAS_WIDTH//2 - 250, CANVAS_HEIGHT//2 - 100,
                CANVAS_WIDTH//2 + 250, CANVAS_HEIGHT//2 + 100,
                fill="#000000", outline="#32a852", width=4, tags="dynamic"
            )
            self.canvas.create_text(
                CANVAS_WIDTH//2, CANVAS_HEIGHT//2 - 30, text="3D PUZZLE CLEARED!", 
                fill="#ffffff", font=("Impact", 32, "normal"), tags="dynamic"
            )
            self.canvas.create_text(
                CANVAS_WIDTH//2, CANVAS_HEIGHT//2 + 30, text=f"FINAL SCORE: {self.game_over_score:.1f}%", 
                fill="#32a852", font=("Consolas", 28, "bold"), tags="dynamic"
            )
            self.canvas.create_text(
                CANVAS_WIDTH//2, CANVAS_HEIGHT//2 + 75, text="Say 'Restart' to try again", 
                fill="#aaaaaa", font=("Arial", 12, "italic"), tags="dynamic"
            )

    def _handle_gesture_preview(self, frame):
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        image = Image.fromarray(rgb)
        image = image.resize((CANVAS_WIDTH, CANVAS_HEIGHT))

        def update() -> None:
            self._preview_image = ImageTk.PhotoImage(image=image)
            if self._camera_background_id is None:
                self._camera_background_id = self.canvas.create_image(
                    0, 0, image=self._preview_image, anchor="nw", tags="background"
                )
            else:
                self.canvas.itemconfigure(self._camera_background_id, image=self._preview_image)
            self.canvas.tag_lower("background")

        self.root.after(0, update)

    def _on_close(self):
        self.stop_inputs()
        self.root.destroy()

def main():
    config_path = Path(__file__).with_name("fusion-3d.conf")
    fusion_config = load_fusion_config(config_path)
    runtime = CollaborationRuntime(fusion_config=fusion_config)
    app = ShapePuzzleApp(runtime, fusion_config=fusion_config)
    app.root.mainloop()

if __name__ == "__main__":
    main()
