import tkinter as tk
import sys
from tkinter import ttk
from pathlib import Path

from contracts.actions import ActionPayload, ActionType, Delta, Position
from core.runtime import CollaborationRuntime

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from app import CANVAS_HEIGHT, CANVAS_WIDTH, ShapePuzzleApp
else:
    from .app import CANVAS_HEIGHT, CANVAS_WIDTH, ShapePuzzleApp


MOVE_STEP = 20
ROTATION_STEP = 10
SIZE_STEP = 8
LEFT_PANEL_WIDTH = 110
RIGHT_PANEL_WIDTH = 220
STATUS_HEIGHT = 28
TOOL_PANEL_BG = "#d6d6d6"


class MouseKeyboardShapePuzzleApp(ShapePuzzleApp):
    """Mouse/keyboard baseline with a conventional desktop-tool UI."""

    app_id = "shape-puzzle-mouse-keyboard"
    show_input_controls = False
    evaluation_condition = "mouse_keyboard"

    def __init__(self, runtime: CollaborationRuntime):
        self.tool_mode = "select"
        self.shape_var: tk.StringVar | None = None
        self._last_drag_x = 0
        self._last_drag_y = 0
        self._tool_buttons: dict[str, tk.Label] = {}
        self._selected_label: tk.StringVar | None = None
        self._mode_label: tk.StringVar | None = None
        super().__init__(runtime)
        self.root.title("3D Shape Puzzle - Mouse/Keyboard Baseline")
        self.log_var.set("Choose a shape, create it, then use the tools to manipulate it.")
        self._bind_baseline_controls()
        self._refresh_side_panel()

    def _build_ui(self):
        self._build_menu()

        root = tk.Frame(self.root, bg="#2b2d30")
        root.pack(fill=tk.BOTH, expand=True)
        root.grid_rowconfigure(0, weight=1)
        root.grid_columnconfigure(0, weight=1)

        body = tk.Frame(root, bg="#2b2d30")
        body.grid(row=0, column=0, sticky="nsew")
        body.grid_rowconfigure(0, weight=1)
        body.grid_columnconfigure(0, minsize=LEFT_PANEL_WIDTH, weight=0)
        body.grid_columnconfigure(1, weight=1)
        body.grid_columnconfigure(2, minsize=RIGHT_PANEL_WIDTH, weight=0)

        left_tools = tk.Frame(body, bg=TOOL_PANEL_BG, padx=5, pady=6, width=LEFT_PANEL_WIDTH)
        left_tools.grid(row=0, column=0, sticky="ns")
        left_tools.grid_propagate(False)
        left_tools.pack_propagate(False)
        self._build_tool_palette(left_tools)

        canvas_frame = tk.Frame(body, bg="#111111", padx=1, pady=1)
        canvas_frame.grid(row=0, column=1, sticky="nsew")
        canvas_frame.grid_rowconfigure(0, weight=1)
        canvas_frame.grid_columnconfigure(0, weight=1)
        self.canvas = tk.Canvas(
            canvas_frame,
            width=CANVAS_WIDTH,
            height=CANVAS_HEIGHT,
            bg="#1a1a1a",
            highlightthickness=0,
        )
        self.canvas.grid(row=0, column=0, sticky="nsew")

        side_panel = tk.Frame(body, bg="#eeeeee", padx=8, pady=8, width=RIGHT_PANEL_WIDTH)
        side_panel.grid(row=0, column=2, sticky="ns")
        side_panel.grid_propagate(False)
        self._build_side_panel(side_panel)

        status = tk.Frame(root, bg="#1f2023", padx=10, pady=4, height=STATUS_HEIGHT)
        status.grid(row=1, column=0, sticky="ew")
        status.grid_propagate(False)
        self.log_var = tk.StringVar(value="Baseline ready.")
        tk.Label(
            status,
            textvariable=self.log_var,
            fg="#e8e8e8",
            bg="#1f2023",
            font=("Arial", 11),
            anchor="w",
        ).pack(fill=tk.X)

        self.canvas.create_text(
            CANVAS_WIDTH // 2,
            40,
            text="FIT THE 3D OBJECTS IN THIS",
            fill="#ffffff",
            font=("Impact", 28, "normal"),
            tags="static",
            justify="center",
        )
        self._set_instruction_text(
            "Mouse/keyboard baseline: use the left tools and right properties panel."
        )

    def _build_menu(self) -> None:
        menu = tk.Menu(self.root)
        file_menu = tk.Menu(menu, tearoff=0)
        file_menu.add_command(label="Restart Puzzle", command=self._restart_game)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self._on_close)
        menu.add_cascade(label="File", menu=file_menu)

        edit_menu = tk.Menu(menu, tearoff=0)
        edit_menu.add_command(label="Insert Selected", command=self._insert_selected)
        edit_menu.add_command(label="Delete Selected", command=self._delete_selected)
        menu.add_cascade(label="Edit", menu=edit_menu)
        self.root.config(menu=menu)

    def _build_tool_palette(self, parent: tk.Frame) -> None:
        tk.Label(parent, text="Create", bg=TOOL_PANEL_BG, fg="#333333", font=("Arial", 10, "bold")).pack(
            fill=tk.X,
            pady=(0, 6),
        )
        self.shape_var = tk.StringVar(value="cube")
        ttk.Combobox(
            parent,
            textvariable=self.shape_var,
            values=("cube", "cuboid", "sphere", "diamond"),
            width=11,
            state="readonly",
        ).pack(fill=tk.X, pady=(0, 4))
        self._button(parent, "Create", self._create_selected_shape).pack(fill=tk.X, pady=(0, 14))

        tk.Label(parent, text="Tools", bg=TOOL_PANEL_BG, fg="#333333", font=("Arial", 10, "bold")).pack(
            fill=tk.X,
            pady=(0, 6),
        )
        self._tool_button(parent, "Select", "select")
        self._tool_button(parent, "Move", "move")
        self._tool_button(parent, "Rotate", "rotate")
        self._tool_button(parent, "Resize", "resize")

        self._mode_label = tk.StringVar(value="Tool: Select")
        tk.Label(parent, textvariable=self._mode_label, bg=TOOL_PANEL_BG, fg="#333333", anchor="w").pack(
            fill=tk.X,
            pady=(12, 0),
        )
        self._refresh_tool_buttons()

    def _build_side_panel(self, parent: tk.Frame) -> None:
        tk.Label(parent, text="Properties", bg="#eeeeee", font=("Arial", 12, "bold")).pack(
            anchor="w",
            pady=(0, 8),
        )
        self._selected_label = tk.StringVar(value="Selected: none")
        selected_frame = tk.Frame(parent, bg="#eeeeee", height=76)
        selected_frame.pack(fill=tk.X, pady=(0, 10))
        selected_frame.pack_propagate(False)
        tk.Label(selected_frame, textvariable=self._selected_label, bg="#eeeeee", anchor="nw", justify="left").pack(
            fill=tk.X,
            anchor="nw",
        )

        self._panel_section(parent, "Move")
        nudge = tk.Frame(parent, bg="#eeeeee", height=132)
        nudge.pack(fill=tk.X, pady=(0, 10))
        nudge.pack_propagate(False)
        for idx in range(2):
            nudge.grid_columnconfigure(idx, weight=1, uniform="move")
        for idx in range(3):
            nudge.grid_rowconfigure(idx, weight=1, uniform="move")
        self._button(nudge, "Up", lambda: self._move_by(0, -MOVE_STEP), height=1).grid(row=0, column=0, columnspan=2, padx=8, pady=4, sticky="nsew")
        self._button(nudge, "Left", lambda: self._move_by(-MOVE_STEP, 0), height=1).grid(row=1, column=0, padx=(8, 4), pady=4, sticky="nsew")
        self._button(nudge, "Right", lambda: self._move_by(MOVE_STEP, 0), height=1).grid(row=1, column=1, padx=(4, 8), pady=4, sticky="nsew")
        self._button(nudge, "Down", lambda: self._move_by(0, MOVE_STEP), height=1).grid(row=2, column=0, columnspan=2, padx=8, pady=4, sticky="nsew")

        self._panel_section(parent, "Rotate")
        rotate = tk.Frame(parent, bg="#eeeeee", height=70)
        rotate.pack(fill=tk.X, pady=(0, 10))
        rotate.pack_propagate(False)
        self._button(rotate, "X-", lambda: self._rotate_by(-ROTATION_STEP, 0), width=5).grid(row=0, column=0, padx=2, pady=2)
        self._button(rotate, "X+", lambda: self._rotate_by(ROTATION_STEP, 0), width=5).grid(row=0, column=1, padx=2, pady=2)
        self._button(rotate, "Y-", lambda: self._rotate_by(0, -ROTATION_STEP), width=5).grid(row=1, column=0, padx=2, pady=2)
        self._button(rotate, "Y+", lambda: self._rotate_by(0, ROTATION_STEP), width=5).grid(row=1, column=1, padx=2, pady=2)

        self._panel_section(parent, "Resize")
        resize = tk.Frame(parent, bg="#eeeeee", height=38)
        resize.pack(fill=tk.X, pady=(0, 12))
        resize.pack_propagate(False)
        self._button(resize, "Smaller", lambda: self._resize_by(-SIZE_STEP), width=8).pack(side=tk.LEFT, padx=2)
        self._button(resize, "Larger", lambda: self._resize_by(SIZE_STEP), width=8).pack(side=tk.LEFT, padx=2)

        self._panel_section(parent, "Task")
        task = tk.Frame(parent, bg="#eeeeee", height=100)
        task.pack(fill=tk.X)
        task.pack_propagate(False)
        self._button(task, "Insert Selected", self._insert_selected).pack(fill=tk.X, pady=2)
        self._button(task, "Delete Selected", self._delete_selected).pack(fill=tk.X, pady=2)
        self._button(task, "Restart Puzzle", self._restart_game).pack(fill=tk.X, pady=2)

    def _button(
        self,
        parent,
        text: str,
        command,
        width: int | None = None,
        height: int | None = None,
    ) -> tk.Button:
        return tk.Button(
            parent,
            text=text,
            command=command,
            width=width,
            height=height,
            relief=tk.RAISED,
            bd=1,
            padx=6,
            pady=3,
        )

    def _tool_button(self, parent, text: str, mode: str) -> None:
        label = tk.Label(
            parent,
            text=text,
            bg=TOOL_PANEL_BG,
            fg="#111111",
            anchor="w",
            width=12,
            padx=8,
            pady=6,
            cursor="hand2",
        )
        label.bind("<Button-1>", lambda _event: self._set_tool_mode(mode))
        label.pack(fill=tk.X)
        self._tool_buttons[mode] = label

    def _panel_section(self, parent, text: str) -> None:
        tk.Label(parent, text=text, bg="#eeeeee", fg="#444444", font=("Arial", 10, "bold")).pack(
            anchor="w",
            pady=(8, 3),
        )

    def _create_selected_shape(self) -> None:
        self._create_object(self.shape_var.get() if self.shape_var is not None else "cube")

    def start_inputs(self):
        self.log_var.set("Mouse/keyboard baseline does not use camera or voice.")

    def stop_inputs(self):
        self.log_var.set("Mouse/keyboard baseline has no input stream to stop.")

    def _bind_baseline_controls(self):
        self.canvas.bind("<Motion>", self._on_mouse_motion)
        self.canvas.bind("<Button-1>", self._on_mouse_click)
        self.canvas.bind("<ButtonRelease-1>", self._on_mouse_release)
        self.canvas.bind("<B1-Motion>", self._on_mouse_drag)

        self.root.bind("<KeyPress-1>", lambda _: self._create_object("cube"))
        self.root.bind("<KeyPress-2>", lambda _: self._create_object("cuboid"))
        self.root.bind("<KeyPress-3>", lambda _: self._create_object("sphere"))
        self.root.bind("<KeyPress-4>", lambda _: self._create_object("diamond"))
        self.root.bind("<Left>", lambda _: self._move_by(-MOVE_STEP, 0))
        self.root.bind("<Right>", lambda _: self._move_by(MOVE_STEP, 0))
        self.root.bind("<Up>", lambda _: self._move_by(0, -MOVE_STEP))
        self.root.bind("<Down>", lambda _: self._move_by(0, MOVE_STEP))
        self.root.bind("<a>", lambda _: self._rotate_by(0, -ROTATION_STEP))
        self.root.bind("<d>", lambda _: self._rotate_by(0, ROTATION_STEP))
        self.root.bind("<w>", lambda _: self._rotate_by(-ROTATION_STEP, 0))
        self.root.bind("<s>", lambda _: self._rotate_by(ROTATION_STEP, 0))
        self.root.bind("<plus>", lambda _: self._resize_by(SIZE_STEP))
        self.root.bind("<equal>", lambda _: self._resize_by(SIZE_STEP))
        self.root.bind("<minus>", lambda _: self._resize_by(-SIZE_STEP))
        self.root.bind("<Return>", lambda _: self._insert_selected())
        self.root.bind("<Delete>", lambda _: self._delete_selected())
        self.root.bind("<BackSpace>", lambda _: self._delete_selected())
        self.root.bind("<r>", lambda _: self._restart_game())

    def _set_tool_mode(self, mode: str) -> None:
        self.tool_mode = mode
        self.mode = "idle"
        self._refresh_tool_buttons()
        self.log_var.set(f"Tool: {mode}")

    def _refresh_tool_buttons(self) -> None:
        for mode, button in self._tool_buttons.items():
            if mode == self.tool_mode:
                button.configure(text=f"> {mode.title()}", font=("Arial", 10, "bold"))
            else:
                button.configure(text=f"  {mode.title()}", font=("Arial", 10, "normal"))
        if self._mode_label is not None:
            self._mode_label.set(f"Tool: {self.tool_mode.title()}")

    def _refresh_side_panel(self) -> None:
        if self._selected_label is None:
            return
        if self.selected_object_id and self.selected_object_id in self.objects:
            obj = self.objects[self.selected_object_id]
            self._selected_label.set(
                f"Selected: {obj.obj_id}\nSize: {obj.size:.0f}\nRot X: {obj.angle_x:.0f}\nRot Y: {obj.angle_y:.0f}"
            )
        else:
            self._selected_label.set("Selected: none")

    def _on_mouse_motion(self, event):
        self.last_pointer_x = max(0, min(CANVAS_WIDTH, event.x))
        self.last_pointer_y = max(0, min(CANVAS_HEIGHT, event.y))
        self.update_canvas()

    def _on_mouse_click(self, event):
        self.last_pointer_x = max(0, min(CANVAS_WIDTH, event.x))
        self.last_pointer_y = max(0, min(CANVAS_HEIGHT, event.y))
        self._last_drag_x = self.last_pointer_x
        self._last_drag_y = self.last_pointer_y

        position = Position(x=self.last_pointer_x / CANVAS_WIDTH, y=self.last_pointer_y / CANVAS_HEIGHT)
        if self.tool_mode in {"select", "move"} and not self.selected_object_id:
            self._apply_action(
                ActionPayload(
                    type=ActionType.SELECT_OBJECT,
                    position=position,
                    metadata={"modality": "mouse"},
                )
            )
        elif self.tool_mode == "select":
            self._apply_action(
                ActionPayload(
                    type=ActionType.SELECT_OBJECT,
                    position=position,
                    metadata={"modality": "mouse"},
                )
            )
        else:
            self.update_canvas()
        self._refresh_side_panel()

    def _on_mouse_drag(self, event):
        previous_x = self._last_drag_x
        previous_y = self._last_drag_y
        self.last_pointer_x = max(0, min(CANVAS_WIDTH, event.x))
        self.last_pointer_y = max(0, min(CANVAS_HEIGHT, event.y))
        delta_x = self.last_pointer_x - previous_x
        delta_y = self.last_pointer_y - previous_y
        self._last_drag_x = self.last_pointer_x
        self._last_drag_y = self.last_pointer_y

        if self.selected_object_id and self.selected_object_id in self.objects:
            if self.tool_mode == "move":
                self._apply_action(
                    ActionPayload(
                        type=ActionType.MOVE_OBJECT,
                        delta=Delta(dx=delta_x / CANVAS_WIDTH, dy=delta_y / CANVAS_HEIGHT),
                        metadata={"modality": "mouse"},
                    )
                )
            elif self.tool_mode == "rotate":
                self._rotate_by(int(-delta_y * 0.5), int(delta_x * 0.5))
            elif self.tool_mode == "resize":
                self._resize_by(int(-delta_y * 0.4))
            else:
                self.update_canvas()
        else:
            self.update_canvas()
        self._refresh_side_panel()

    def _on_mouse_release(self, _event):
        self.mode = "idle"
        self.update_canvas()
        self._refresh_side_panel()

    def _move_by(self, dx: int, dy: int):
        self._apply_action(
            ActionPayload(
                type=ActionType.MOVE_OBJECT,
                delta=Delta(dx=dx / CANVAS_WIDTH, dy=dy / CANVAS_HEIGHT),
                metadata={"modality": "keyboard"},
            )
        )
        self._refresh_side_panel()

    def _rotate_by(self, angle_x: int, angle_y: int):
        if self.selected_object_id and self.selected_object_id in self.objects:
            obj = self.objects[self.selected_object_id]
            obj.angle_x += angle_x
            obj.angle_y += angle_y
            self.update_canvas()
            self._refresh_side_panel()

    def _resize_by(self, size_delta: int):
        if self.selected_object_id and self.selected_object_id in self.objects:
            obj = self.objects[self.selected_object_id]
            obj.size = max(10, min(300, obj.size + size_delta))
            self.update_canvas()
            self._refresh_side_panel()

    def _select_nearest_object(self, position):
        super()._select_nearest_object(position)
        self._refresh_side_panel()

    def _delete_selected(self):
        super()._delete_selected()
        self._refresh_side_panel()

    def _restart_game(self):
        super()._restart_game()
        self._refresh_side_panel()

    def _insert_selected(self):
        super()._insert_selected()
        self._refresh_side_panel()


def main():
    runtime = CollaborationRuntime()
    app = MouseKeyboardShapePuzzleApp(runtime)
    app.root.mainloop()


if __name__ == "__main__":
    main()
