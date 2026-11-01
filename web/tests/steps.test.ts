import { describe, expect, it } from "vitest";
import { boundsOf, clampStep, partScene, stepFromSearch, stepHeading, stepHighlight, stepKey, stepScene, stepsTab, withStep } from "../src/steps";
import type { PieceView, StepView, View } from "../src/types";

const piece = (id: string, x: number): PieceView => ({ id, type: "2x4", length: 400, group: 0, min: [x, 0, 0],
  max: [x + 89, 38, 400], faces: { top: "+z", right: "+x", front: "+y" }, size: [89, 38, 400],
  position: [x, 0, 0], rotation: [[1, 0, 0], [0, 1, 0], [0, 0, 1]], line: 1 });
const step = (number: number, pieces: string[], shown: string[], over: Partial<StepView> = {}): StepView => ({
  number, name: null, kind: "attach", pieces, connections: [], shown, view: { axis: "y", side: 1 }, hardware: [], dimensions: [], ...over });
const v: View = {
  valid: true, error: null, overall_size: [389, 38, 400], size_reference: "a",
  pieces: [piece("a", 0), piece("b", 100), piece("c", 300)], problems: [], connections: [], holes: [],
  parts: [{ pieces: ["a", "b", "c"], type: "2x4", length: 400, count: 3, drilled: false }],
  steps: [step(1, ["a", "b"], ["a", "b"], { kind: "first", name: "Frame" }), step(2, ["c"], ["c"], { kind: "sub-assembly" })],
  steps_declared: true, steps_hint: null,
};

describe("a step", () => {
  it("draws the part it leaves: earlier pieces grey, its own blue", () => {
    const scene = stepScene({ ...v, steps: [step(1, ["a"], ["a"]), step(2, ["b"], ["a", "b"])] }, 2);
    expect([...scene.visible!]).toEqual(["a", "b"]);
    expect([...scene.earlier]).toEqual(["a"]);
    expect([...scene.current]).toEqual(["b"]);
    expect(scene.bounds).toEqual({ min: [0, 0, 0], max: [189, 38, 400] });
  });

  it("built apart leaves out what was built before", () => {
    const scene = stepScene(v, 2);
    expect([...scene.visible!]).toEqual(["c"]);
    expect(scene.earlier.size).toBe(0);
  });

  it("0 is the parts list: the whole model, a picked part in blue", () => {
    expect(stepScene(v, 0)).toEqual({ visible: null, earlier: new Set(), current: new Set(), bounds: null });
    expect([...partScene(v, 0).current]).toEqual(["a", "b", "c"]);
    expect(partScene(v, null).current.size).toBe(0);
  });

  it("paints as the highlight does", () => {
    const h = stepHighlight(stepScene({ ...v, steps: [step(1, ["a"], ["a"]), step(2, ["b"], ["a", "b"])] }, 2));
    expect([...h.paint]).toEqual([["a", "earlier"], ["b", "selected"]]);
  });

  it("is headed as the CLI heads it", () => {
    expect(stepHeading(v.steps[0])).toBe("Step 1 - Frame");
    expect(stepHeading(v.steps[1])).toBe("Step 2 (sub-assembly)");
    expect(stepHeading(step(3, ["a"], ["a"], { kind: "join", name: "All" }))).toBe("Step 3 - All (join)");
  });
});

it("bounds hold the pieces named", () => {
  expect(boundsOf(v, ["b", "c"])).toEqual({ min: [100, 0, 0], max: [389, 38, 400] });
  expect(boundsOf(v, [])).toBeNull();
});

describe("the step number", () => {
  it("stays in range, as for a file reopened with fewer steps", () => {
    expect([clampStep(v, -1), clampStep(v, 1), clampStep(v, 99), clampStep(v, Number.NaN)]).toEqual([0, 1, 2, 0]);
  });

  it("comes from ?step= only when it is a whole number", () => {
    expect(["?step=2", "?step=0", "?step=abc", "?step=-1", "?step=2.5", ""].map(stepFromSearch))
      .toEqual([2, 0, null, null, null, null]);
  });

  it("goes into the address, and out of it on the Model tab", () => {
    expect(withStep("https://e.com/?src=a.nd", 3)).toBe("https://e.com/?src=a.nd&step=3");
    expect(withStep("https://e.com/?src=a.nd&step=3#x", null)).toBe("https://e.com/?src=a.nd#x");
  });
});

it("arrow keys step, but not while typing", () => {
  expect([stepKey("ArrowLeft", "BODY"), stepKey("ArrowRight", "BUTTON"), stepKey("ArrowRight", "INPUT"), stepKey("a", "BODY")])
    .toEqual([-1, 1, 0, 0]);
});

describe("the Steps tab", () => {
  it("opens for a design that reads", () => {
    expect(stepsTab(v)).toEqual({ enabled: true, reason: null });
  });

  it("stays shut with the reason otherwise", () => {
    expect(stepsTab(null).reason).toBe("Open an .nd first");
    expect(stepsTab({ ...v, error: { kind: "syntax", message: "", line: 1, column: 1 } }).reason)
      .toBe("Fix the error first: the steps need a design that reads");
    expect(stepsTab({ ...v, pieces: [], steps: [] }).reason).toBe("Nothing to assemble: the design has no pieces");
  });
});
