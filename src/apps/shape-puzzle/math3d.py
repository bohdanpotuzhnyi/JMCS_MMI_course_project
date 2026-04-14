import math
from typing import List, Tuple

def create_cube(size: float = 1.0) -> Tuple[List[List[float]], List[Tuple[int, ...]]]:
    s = size / 2
    vertices = [
        [-s, -s, -s],
        [ s, -s, -s],
        [ s,  s, -s],
        [-s,  s, -s],
        [-s, -s,  s],
        [ s, -s,  s],
        [ s,  s,  s],
        [-s,  s,  s],
    ]
    faces = [
        (0, 1, 2, 3),
        (4, 5, 6, 7),
        (0, 1, 5, 4),
        (3, 2, 6, 7),
        (0, 3, 7, 4),
        (1, 2, 6, 5)
    ]
    return vertices, faces

def create_cuboid(width: float = 1.0, height: float = 2.0, depth: float = 0.5) -> Tuple[List[List[float]], List[Tuple[int, ...]]]:
    w, h, d = width/2, height/2, depth/2
    vertices = [
        [-w, -h, -d],
        [ w, -h, -d],
        [ w,  h, -d],
        [-w,  h, -d],
        [-w, -h,  d],
        [ w, -h,  d],
        [ w,  h,  d],
        [-w,  h,  d],
    ]
    faces = [
        (0, 1, 2, 3),
        (4, 5, 6, 7),
        (0, 1, 5, 4),
        (3, 2, 6, 7),
        (0, 3, 7, 4),
        (1, 2, 6, 5)
    ]
    return vertices, faces

def create_diamond(size: float = 1.0) -> Tuple[List[List[float]], List[Tuple[int, ...]]]:
    vertices = [
        [0, -size, 0],  # Bottom 0
        [size, 0, 0],   # Right 1
        [0, 0, -size],  # Back 2
        [-size, 0, 0],  # Left 3
        [0, 0, size],   # Front 4
        [0, size, 0],   # Top 5
    ]
    faces = [
        (0, 1, 4), (0, 4, 3), (0, 3, 2), (0, 2, 1),
        (5, 1, 4), (5, 4, 3), (5, 3, 2), (5, 2, 1)
    ]
    return vertices, faces

def create_sphere(radius: float = 1.0, segments: int = 8, rings: int = 8) -> Tuple[List[List[float]], List[Tuple[int, ...]]]:
    vertices = []
    faces = []
    
    # Generate vertices
    for i in range(rings + 1):
        theta = i * math.pi / rings
        sin_theta = math.sin(theta)
        cos_theta = math.cos(theta)
        
        for j in range(segments):
            phi = j * 2 * math.pi / segments
            sin_phi = math.sin(phi)
            cos_phi = math.cos(phi)
            
            x = radius * cos_phi * sin_theta
            y = radius * cos_theta
            z = radius * sin_phi * sin_theta
            vertices.append([x, y, z])
            
    # Generate faces
    for i in range(rings):
        for j in range(segments):
            current = i * segments + j
            next_j = (i * segments) + ((j + 1) % segments)
            below = current + segments
            below_next = next_j + segments
            
            faces.append((current, next_j, below_next, below))
            
    return vertices, faces

def rotate_3d(points: List[List[float]], angle_x: float, angle_y: float, angle_z: float) -> List[List[float]]:
    px, py, pz = math.radians(angle_x), math.radians(angle_y), math.radians(angle_z)
    cx, sx = math.cos(px), math.sin(px)
    cy, sy = math.cos(py), math.sin(py)
    cz, sz = math.cos(pz), math.sin(pz)
    
    rotated = []
    for p in points:
        x, y, z = p[0], p[1], p[2]
        # Rotate X
        xy = y * cx - z * sx
        xz = y * sx + z * cx
        y, z = xy, xz
        # Rotate Y
        yx = x * cy + z * sy
        yz = -x * sy + z * cy
        x, z = yx, yz
        # Rotate Z
        zx = x * cz - y * sz
        zy = x * sz + y * cz
        x, y = zx, zy
        rotated.append([x, y, z])
        
    return rotated

def project_to_2d(points: List[List[float]], fov: float, viewer_distance: float, scale: float, screen_center: Tuple[float, float]) -> List[Tuple[float, float]]:
    projected = []
    for p in points:
        x, y, z = p[0], p[1], p[2]
        if z + viewer_distance == 0:
            factor = fov
        else:
            factor = fov / (viewer_distance + z)
            
        x_proj = x * factor * scale + screen_center[0]
        y_proj = y * factor * scale + screen_center[1]
        projected.append((x_proj, y_proj))
    return projected
