export type GestureEvent = {
  type: "gesture";
  timestamp: number;
  hand: "left" | "right";
  gesture: "point" | "grab" | "release" | "rotate" | "pinch";
  position2d?: { x: number; y: number };
  position3d?: { x: number; y: number; z: number };
  targetObjectId?: string;
  confidence: number;
};

export type VoiceEvent = {
  type: "voice";
  timestamp: number;
  transcript: string;
  intent?: "select" | "move" | "rotate" | "delete" | "confirm" | "cancel";
  slots?: Record<string, string | number>;
  confidence: number;
};

export type ModalityEvent = GestureEvent | VoiceEvent;
