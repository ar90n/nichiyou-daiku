import type { View } from "./types";

const KEYS = [
  "valid", "error", "pieces", "problems", "connections", "holes",
  "parts", "steps", "steps_declared", "steps_hint",
] as const;

/** The core's view JSON, checked for the keys this viewer reads. */
export function parseView(json: string): View {
  const value = JSON.parse(json);
  for (const key of KEYS) {
    if (!(key in value)) {
      throw new Error(`The core's answer has no "${key}"; rebuild the WebAssembly (make wasm)`);
    }
  }
  return value as View;
}

export type ViewFn = (source: string) => View;

export interface DrawingAnswer {
  svg: string | null;
  /** Values that do not fit, as the CLI warns */
  notes: string[];
  error: string | null;
}
/** A part's drawing (its number in the parts list) or a step's (from 1) */
export type DrawingFn = (source: string, index: number) => DrawingAnswer;
export interface Core {
  view: ViewFn;
  partDrawing: DrawingFn;
  stepDrawing: DrawingFn;
}

/** Load the core's WebAssembly: views, part and step drawings of an .nd source. */
export async function loadCore(): Promise<Core> {
  const core = await import("./wasm/nichiyou_daiku_wasm.js");
  await core.default();
  return {
    view: (source) => parseView(core.view(source)),
    partDrawing: (source, part) => JSON.parse(core.part_drawing(source, part)) as DrawingAnswer,
    stepDrawing: (source, step) => JSON.parse(core.step_drawing(source, step)) as DrawingAnswer,
  };
}

export function safeDrawing(fn: DrawingFn, source: string, index: number): DrawingAnswer {
  try {
    return fn(source, index);
  } catch (error) {
    const reason = error instanceof Error ? error.message : String(error);
    return { svg: null, notes: [], error: `Internal error in the core while drawing: ${reason}. Please report it with the .nd file.` };
  }
}

/** A view with nothing to draw but an error. */
export function failedView(kind: string, message: string): View {
  return { valid: false, overall_size: null, size_reference: null, pieces: [], problems: [],
    connections: [], holes: [], parts: [], steps: [], steps_declared: false, steps_hint: null,
    error: { kind, line: null, column: null, message } };
}

/** The view of a source; a core that throws (a panic traps in WebAssembly) gives an internal error. */
export function safeView(viewFn: ViewFn, source: string): View {
  try {
    return viewFn(source);
  } catch (error) {
    const reason = error instanceof Error ? error.message : String(error);
    return failedView("internal", `Internal error in the core: ${reason}. Please report it with the .nd file.`);
  }
}
