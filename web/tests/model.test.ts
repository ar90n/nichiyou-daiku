import { describe, expect, it } from "vitest";
import { parseView, safeView } from "../src/model";

describe("parseView", () => {
  it("reads the core's answer", () => {
    const view = parseView(JSON.stringify({ valid: true, error: null, overall_size: [1, 2, 3],
      size_reference: "a", pieces: [], problems: [], connections: [], holes: [], parts: [], steps: [], steps_declared: false, steps_hint: null }));
    expect(view.overall_size).toEqual([1, 2, 3]);
  });

  it("says how to fix an answer from an older core", () => {
    expect(() => parseView('{"valid": true}')).toThrow(/rebuild the WebAssembly \(make wasm\)/);
  });
});

it("a core that throws (a panic in WebAssembly) gives an internal error, not a dead page", () => {
  const view = safeView(() => { throw new Error("unreachable"); }, "(a:2x4 =100)");
  expect(view.error).toEqual({ kind: "internal", line: null, column: null,
    message: "Internal error in the core: unreachable. Please report it with the .nd file." });
  expect([view.pieces, view.problems, view.connections, view.holes]).toEqual([[], [], [], []]);
});
