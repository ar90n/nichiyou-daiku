import type { View } from "./types";

const KEYS = ["valid", "error", "pieces", "problems", "connections", "holes"] as const;

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

/** Load the core's WebAssembly; the function it gives views an .nd source. */
export async function loadCore(): Promise<ViewFn> {
  const core = await import("./wasm/nichiyou_daiku_wasm.js");
  await core.default();
  return (source) => parseView(core.view(source));
}

/** The view of a source; a core that throws (a panic traps in WebAssembly) gives an internal error. */
export function safeView(viewFn: ViewFn, source: string): View {
  try {
    return viewFn(source);
  } catch (error) {
    const reason = error instanceof Error ? error.message : String(error);
    return { valid: false, overall_size: null, size_reference: null, pieces: [], problems: [],
      connections: [], holes: [], error: { kind: "internal", line: null, column: null,
        message: `Internal error in the core: ${reason}. Please report it with the .nd file.` } };
  }
}
