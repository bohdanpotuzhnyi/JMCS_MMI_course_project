

from __future__ import annotations
from enum import Enum
from typing import Any, Optional
from pydantic import BaseModel, Field


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
    CREATE_OBJECT    = "create_object"
    SET_INTERACTION_MODE = "set_interaction_mode"
    INSERT_OBJECT    = "insert_object"
    RESET_APP        = "reset_app"
    UPDATE_POINTER   = "update_pointer"
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
    object_type: Optional[str] = None
    mode: Optional[str] = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    source_events: list[str] = Field(default_factory=list)
