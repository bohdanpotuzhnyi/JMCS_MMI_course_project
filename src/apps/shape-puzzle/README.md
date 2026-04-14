# Multimodal 3D Shape Puzzle Game

The **3D Shape Puzzle** is an advanced interactive gamification application built on top of a custom-built Event-Bus Multimodal Toolkit. Instead of relying on traditional keyboard or mouse inputs, this game challenges users to manipulate solid 3D models strictly using real-time **Speech Recognition (Vosk)** and **Computer Vision Hand Tracking (MediaPipe)**.

## Overview

Your objective is to complete the 3D Puzzle by accurately inserting geometric shapes (Cubes, Cuboids, Spheres, Diamonds) into their corresponding 3D target silhouettes. To succeed, you must use combined voice and physical gesture mechanisms to seamlessly generate, drag, scale, and geometrically rotate objects to perfectly match the target's complex predefined orientation.

The underlying physics and scoring engine mathematically evaluates how accurately your shape mathematically aligns with the target on three independent geometric planes.

## How to Execute

This application is built as an integrated module within the Multimodal Toolkit environment.

1. Ensure the toolkit dependencies are installed in your Python Virtual Environment.
2. From the root directory of the project, execute the following PowerShell command to launch the `shape-puzzle` app:
   ```powershell
   powershell -ExecutionPolicy Bypass -Command ". .\scripts\activate_windows.ps1; cd src; python -m apps.shape-puzzle.app"
   ```

## How to Play: Command Cheatsheet

Control over the game is achieved by pairing your pointing finger with precise voice mechanics.

#### 1. Generate & Select Shapes
* Point your finger at the screen and say **`"Create Cube"`** (or Sphere, Cuboid, Diamond). The shape drops exactly on your pointer.
* Point your laser dot at a yellow shape and say **`"Select"`**. It turns Pink!

#### 2. Spatial Translation
* **Continuous Drag:** Say **`"Drag"`**. The shape now rigidly locks to your finger's every movement and glides across the screen.
* **Instant Teleport:** Alternatively, point your finger far away and say **`"Move Here"`** to instantly warp the shape to your pointer coordinates.

#### 3. Manipulation & Sizing
* **Rotation:** Say **`"Rotate"`**. Open your full palm and gently wave your hand. The game intelligently tracks your *Palm Center* to provide ultra-smooth, jitter-free 3D tumbling physics.
* **Resizing:** Say **`"Resize"`** and use your Thumb and Index finger to physically **Pinch and Pull**. The 3D engine strictly tracks the Euclidean distance between your physical fingers to accurately swell or shrink the geometry. 

#### 4. Scoring & Game Loop 
* **Insertion:** When your rotating shape visually matches the orientation of one of the Cyan glowing target holes, drag it perfectly over the target and confidently declare **`"Insert"`**.
* **Done:** Speak **`"Done"`** to drop a piece or cancel a mode at any time.
* **Delete:** Speak **`"Delete"`** while an object is selected to instantly destroy it and clean up the board.
* **Restart:** Speak **`"Restart"`** to flush the memory matrices and generate an entirely new, randomly assigned puzzle session.

## Underlying Application Architecture (Under the Hood)

Though built alongside the toolkit, all Game Logic and interactive mechanics are driven by entirely custom subsystem features built strictly internal to this isolated module:

1. **Procedural 3D Painter Engine**: No external 3D libraries were used. The `math3d.py` script houses a custom mathematically modeled physics engine applying 3D rotation matrices and field-of-view projections. A genuine **Painter's Algorithm (Z-Sorting Engine)** automatically processes the Z-depth index of every drawn face across every item simultaneously, allowing pieces to realistically intersect visibly during gameplay overlap.
2. **Symmetric Gamification Algorithm**: The "Insertion" scoring metric is entirely native. To combat 90-degree rotational illusion penalties (e.g. rotating a cube 90-degrees makes it identical visually but structurally distinct in math memory), the grading algorithm applies periodic modulo symmetries across all targeted geometric permutations to yield objective, flawless % scores.
3. **Dynamic Grammar Virtualization**: The toolkit inherently hardcoded specific voice vocabularies. To solve this restriction without mutating global toolkit architecture dependencies, the `shape-puzzle` module dynamically relies on **Runtime Monkey-Patching** against the `intent_from_transcript.py` schema to stealthily inject game-specific dictionary terms directly into memory.
4. **Physicality Stabilization Mapping**: The Event engine passes raw coordinates. This puzzle intelligently isolates context. *Rotation State* bypasses pointer-index targeting in favor of solid Palm-Geometry derivation to erase skeletal jitter, while *Resizing* mathematically resolves physical thumb-to-pointer Hypotenuse geometry.
