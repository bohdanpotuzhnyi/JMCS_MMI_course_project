import tkinter as tk
import math
import random
from typing import Dict, Any, Optional

import cv2
from PIL import Image, ImageTk

from contracts.actions import ActionPayload, ActionType
from contracts.events import BaseEvent, GestureEvent, VoiceEvent, GestureType
from core.runtime import CollaborationRuntime
from modalities.gesture import GestureDetector, GestureDetectorOptions
from modalities.voice import VoskVoiceAdapter

import sys
import modalities.voice.intent_from_transcript
import modalities.voice.speech_recognition_adapter as sra

ift = sys.modules['modalities.voice.intent_from_transcript']

# MONKEY-PATCH: Expand the toolkit's locked vocabulary!
new_rules = list(ift._RULES)
new_rules.extend([
    ift._Rule("vocab1", ("create sphere", "create cube", "create cuboid", "create diamond")),
    ift._Rule("vocab2", ("select", "drag", "move here", "rotate", "resize", "done", "insert", "restart", "delete")),
])
ift._RULES = tuple(new_rules)
ift.COMMAND_GRAMMAR = tuple(phrase for r in ift._RULES for phrase in r.phrases)
sra.COMMAND_GRAMMAR = ift.COMMAND_GRAMMAR

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

    def __init__(self, runtime: CollaborationRuntime):
        self.runtime = runtime
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
        self.last_palm_x = 0
        self.last_palm_y = 0
        
        self.mode = "idle" 
        self.last_pinch_distance = None
        
        self.game_over_score = None

        self._build_ui()
        self._spawn_targets()
        
        self.runtime.register_app(self)
        self.runtime.bus.subscribe_events(self._on_runtime_event)
        
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
        pass

    def _on_runtime_event(self, event: BaseEvent):
        # 1. ------------- VOICE PARSING -------------
        if isinstance(event, VoiceEvent):
            t = event.transcript.lower().strip()
            if not t: return
            self.log_var.set(f"Heard: '{t}'")
            
            # RESTART GAME STATE
            if "restart" in t:
                self.objects.clear()
                self.object_counter = 0
                self._spawn_targets() # Generates entirely new random board
                self.game_over_score = None
                self.selected_object_id = None
                self.mode = "idle"
                self.log_var.set("Game Restarted with new Targets!")
                self.root.after(0, self.update_canvas)

            # CREATE
            elif "create sphere" in t: self.root.after(0, self._create_object, "sphere")
            elif "create cuboid" in t: self.root.after(0, self._create_object, "cuboid")
            elif "create cube" in t: self.root.after(0, self._create_object, "cube")
            elif "create diamond" in t: self.root.after(0, self._create_object, "diamond")
            
            # SELECT
            elif "select" in t:
                best_dist = 99999
                best_id = None
                for obj_id, obj in self.objects.items():
                    if obj.matched: continue
                    dist = math.hypot(obj.x - self.last_pointer_x, obj.y - self.last_pointer_y)
                    if dist < 120 and dist < best_dist:
                        best_dist = dist
                        best_id = obj_id
                if best_id:
                    self.selected_object_id = best_id
                    self.mode = "idle"
                    self.root.after(0, self.update_canvas)
                    
            # MOVE HERE (Teleport)
            elif "move here" in t:
                if self.selected_object_id and self.selected_object_id in self.objects:
                    obj = self.objects[self.selected_object_id]
                    obj.x = self.last_pointer_x
                    obj.y = self.last_pointer_y
                    self.mode = "idle"
                    self.selected_object_id = None
                    self.root.after(0, self.update_canvas)
            
            # DRAG (Continuous Follow)
            elif "drag" in t:
                if self.selected_object_id:
                    self.mode = "dragging"
                    
            # ROTATE
            elif "rotate" in t:
                if self.selected_object_id:
                    self.mode = "rotating"
                    
            # RESIZE
            elif "resize" in t:
                if self.selected_object_id:
                    self.mode = "resizing"
                    
            # DONE / UNSELECT
            elif "done" in t:
                self.selected_object_id = None
                self.mode = "idle"
                self.log_var.set("UNSELECTED and DONE")
                self.root.after(0, self.update_canvas)
                
            # DELETE
            elif "delete" in t:
                if self.selected_object_id and self.selected_object_id in self.objects:
                    del self.objects[self.selected_object_id]
                    self.selected_object_id = None
                    self.mode = "idle"
                    self.log_var.set("Shape deleted.")
                    self.root.after(0, self.update_canvas)
                
            # INSERT SCORING LOGIC WITH SYMMETRY METRICS
            elif "insert" in t:
                if self.selected_object_id and self.selected_object_id in self.objects:
                    obj = self.objects[self.selected_object_id]
                    
                    best_hole = None
                    best_dist = 9999
                    for hole in self.targets.values():
                        if hole.filled: continue
                        dist = math.hypot(obj.x - hole.x, obj.y - hole.y)
                        if dist < best_dist:
                            best_dist = dist
                            best_hole = hole
                            
                    if best_hole and best_dist < 150:
                        # Match native type exactly!
                        if best_hole.obj_type == obj.obj_type:
                            pos_score = max(0.0, 100 - (best_dist * 0.7))
                            
                            # Scale ratio scoring: 80% size means exactly 80 points!
                            ratio = min(obj.size, best_hole.size) / max(obj.size, best_hole.size)
                            scale_score = ratio * 100.0
                            
                            # Rotational symmetry mapping (avoiding 0/90 degree illusion penalties)
                            sym_x, sym_y = 360, 360
                            if obj.obj_type == "cube": sym_x, sym_y = 90, 90
                            elif obj.obj_type == "cuboid": sym_x, sym_y = 180, 180
                            elif obj.obj_type == "diamond": sym_y = 90
                            
                            # Calculate shortest distance accounting for periodicity over symmetries
                            dx = abs((round(obj.angle_x) % sym_x) - (round(best_hole.angle_x) % sym_x))
                            dx = min(dx, sym_x - dx)
                            dy = abs((round(obj.angle_y) % sym_y) - (round(best_hole.angle_y) % sym_y))
                            dy = min(dy, sym_y - dy)
                            
                            total_angle_error = dx + dy
                            
                            # Sphere has no specific rotation
                            if obj.obj_type == "sphere": rot_score = 100.0
                            else: rot_score = max(0.0, 100 - (total_angle_error * 2.0))
                                
                            final_score = (pos_score + scale_score + rot_score) / 3.0
                            
                            obj.matched = True
                            best_hole.filled = True
                            best_hole.score_text = final_score
                            
                            # Leave the player's object physically locked EXACTLY where they spun/dropped it!
                            self.selected_object_id = None
                            self.mode = "idle"
                            
                            self.log_var.set(f"INSERT SUCCESS! Metric Score: {final_score:.1f}%")
                            self.root.after(0, self._check_game_over)
                        else:
                            self.log_var.set("Wait, that is the wrong 3D geometry for this target!")
                    else:
                        self.log_var.set("No valid target underneath pointer to insert!")
                        
                self.root.after(0, self.update_canvas)

        # 2. ------------- GESTURE PARSING -------------
        elif isinstance(event, GestureEvent):
            palm_x = event.position.x * CANVAS_WIDTH
            palm_y = event.position.y * CANVAS_HEIGHT
            palm_delta_x = palm_x - self.last_palm_x
            palm_delta_y = palm_y - self.last_palm_y
            self.last_palm_x = palm_x
            self.last_palm_y = palm_y

            pointer_pos = event.position
            if event.landmarks and len(event.landmarks) > 8:
                pointer_pos = event.landmarks[8]
                
            if pointer_pos:
                new_x = pointer_pos.x * CANVAS_WIDTH
                new_y = pointer_pos.y * CANVAS_HEIGHT
                delta_x = new_x - self.last_pointer_x
                delta_y = new_y - self.last_pointer_y
                self.last_pointer_x = new_x
                self.last_pointer_y = new_y
                
                if self.selected_object_id and self.selected_object_id in self.objects:
                    obj = self.objects[self.selected_object_id]
                    
                    if self.mode == "dragging":
                        obj.x += delta_x
                        obj.y += delta_y
                    
                    elif self.mode == "rotating":
                        if abs(palm_delta_x) > 2: obj.angle_y += palm_delta_x * 0.15
                        if abs(palm_delta_y) > 2: obj.angle_x -= palm_delta_y * 0.15
                        
                    elif self.mode == "resizing":
                        if event.landmarks and len(event.landmarks) > 8:
                            thumb = event.landmarks[4]
                            index = event.landmarks[8]
                            dist = math.hypot((thumb.x - index.x)*CANVAS_WIDTH, (thumb.y - index.y)*CANVAS_HEIGHT)
                            if self.last_pinch_distance is not None:
                                pinch_delta = dist - self.last_pinch_distance
                                obj.size = max(10, min(300, obj.size + pinch_delta * 0.8))
                            self.last_pinch_distance = dist
                
                if self.mode != "resizing":
                    self.last_pinch_distance = None

                self.root.after(0, self.update_canvas)

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
    runtime = CollaborationRuntime()
    app = ShapePuzzleApp(runtime)
    app.root.mainloop()

if __name__ == "__main__":
    main()
