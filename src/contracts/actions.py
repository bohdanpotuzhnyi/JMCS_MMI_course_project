

from __future__ import annotations
from enum import Enum
from typing import Optional
from pydantic import BaseModel


class ActionType(str, Enum):
    MOVE_OBJECT      = "move_object"
    RESIZE_OBJECT    = "resize_object"
    ROTATE_OBJECT    = "rotate_object"
    SELECT_OBJECT    = "select_object"
    DESELECT_OBJECT  = "deselect_object"
    DELETE_OBJECT    = "delete_object"
    DUPLICATE_OBJECT = "duplicate_object"
    UNDO             = "undo"
    REDO             = "redo"
    ZOOM_IN          = "zoom_in"
    ZOOM_OUT         = "zoom_out"
    PAN              = "pan"
    OPEN_MENU        = "open_menu"
    CLOSE_MENU       = "close_menu"
    NOOP             = "noop" 


class Delta(BaseModel):
    dx: float
    dy: float
    dz: Optional[float] = None


class Position(BaseModel):
    x: float
    y: float


class ActionPayload(BaseModel):
    type: ActionType
    target_id: Optional[str] = None  
    delta: Optional[Delta] = None
    position: Optional[Position] = None
    scale: Optional[float] = None   
    rotation: Optional[float] = None
    source_events: list[str] = []    