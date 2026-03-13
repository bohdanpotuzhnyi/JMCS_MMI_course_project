export type CanonicalAction =
  | { type: "select"; objectId: string }
  | { type: "move"; objectId: string; target: { x: number; y: number; z: number } }
  | { type: "rotate"; objectId: string; delta: number }
  | { type: "delete"; objectId: string }
  | { type: "confirm" }
  | { type: "cancel" };
