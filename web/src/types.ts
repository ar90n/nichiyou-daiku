// The view JSON of the core (crates/nichiyou-daiku-core: view)
export type Vec3 = [number, number, number];
export type Mat3 = [Vec3, Vec3, Vec3];

export interface ViewError {
  kind: string;
  message: string;
  line: number | null;
  column: number | null;
}

export interface PieceView {
  id: string;
  type: string;
  length: number;
  group: number;
  min: Vec3;
  max: Vec3;
  faces: { top: string; right: string; front: string };
  size: Vec3;
  position: Vec3;
  rotation: Mat3;
  line: number;
}

export interface ConnectionView {
  base: string;
  target: string;
  kind: "vanilla" | "dowel" | "screw";
  diameter: number | null;
  length: number | null;
  screw_type: "slim" | "coarse" | null;
  line: number;
}

/** A hole to draw: `center` is on the face it enters, depth null goes through. */
export interface HoleShape {
  piece: string;
  center: Vec3;
  direction: string;
  diameter: number;
  depth: number | null;
}

export interface HoleView extends HoleShape {
  kind: "dowel" | "pilot" | "counterbore";
}

/** A hole of a hole_collision problem. */
export interface HolePosition {
  entry: Vec3;
  direction: string;
  depth: number | null;
  diameter: number;
}

export type Problem =
  | { kind: "conflict"; message: string; connection: [string, string]; constraint: string;
      axis: string | null; mismatch_mm: number | null; loop: string[] }
  | { kind: "unconnected"; message: string; groups: string[][] }
  | { kind: "fastener"; message: string; connection: [string, string]; fastener: string }
  | { kind: "hole_collision"; message: string; connection: [string, string];
      other_connection: [string, string]; piece: string; fastener: string;
      holes: [HolePosition, HolePosition] }
  | { kind: "overlap"; message: string; pieces: [string, string]; volume_mm3: number };

export interface PartView {
  pieces: string[];
  type: string;
  length: number;
  count: number;
}

export interface HardwareView {
  name: string;
  count: number;
}

export type StepKind = "first" | "attach" | "sub-assembly" | "join";

export interface DimensionChain {
  axis: "x" | "y" | "z";
  side: "left" | "below";
  stops: number[];
  segments: { start: number; end: number; lumber: boolean }[];
}

export interface StepView {
  number: number;
  name: string | null;
  kind: StepKind;
  pieces: string[];
  connections: [string, string][];
  shown: string[];
  view: { axis: "x" | "y" | "z"; side: number };
  hardware: HardwareView[];
  dimensions: DimensionChain[];
}

export interface View {
  valid: boolean;
  error: ViewError | null;
  overall_size: Vec3 | null;
  size_reference: string | null;
  pieces: PieceView[];
  problems: Problem[];
  connections: ConnectionView[];
  holes: HoleView[];
  parts: PartView[];
  steps: StepView[];
  steps_declared: boolean;
  steps_hint: string | null;
}
