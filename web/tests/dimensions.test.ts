import { describe, expect, it } from "vitest";
import { dimensionDirection, dimensionGap, formatMm, labelOrder, layoutDimensions, visibleLabels } from "../src/dimensions";
import type { StepView } from "../src/types";

const box = { min: [0, 0, 0] as [number, number, number], max: [500, 100, 300] as [number, number, number] };
const step = (view: StepView["view"], dimensions: StepView["dimensions"]): StepView => ({
  number: 2, name: null, kind: "attach", pieces: ["b"], connections: [], shown: ["a", "b"], view, hardware: [], dimensions });
const across = { axis: "x" as const, side: "below" as const, stops: [0, 200, 219, 500], segments: [
  { start: 0, end: 200, lumber: false }, { start: 200, end: 219, lumber: true }, { start: 219, end: 500, lumber: false }] };
const upright = { axis: "z" as const, side: "left" as const, stops: [0, 300], segments: [] };

describe("seen from the front", () => {
  const layout = layoutDimensions(step({ axis: "y", side: 1 }, [across, upright]), box);

  it("runs a chain below on the face toward the viewer, the overall size outside it", () => {
    expect(layout.lines[0]).toEqual([[0, 100, -40], [500, 100, -40]]);
    expect(layout.lines[1]).toEqual([[0, 100, -80], [500, 100, -80]]);
  });

  it("draws extension lines from the part to the chain they stop on", () => {
    expect(layout.lines).toContainEqual([[0, 100, 0], [0, 100, -88]]);
    expect(layout.lines).toContainEqual([[200, 100, 0], [200, 100, -48]]);
  });

  it("puts an upright chain left of the view: +x here, as the view sees +x on its left", () => {
    expect(layout.lines).toContainEqual([[540, 100, 0], [540, 100, 300]]);
  });

  it("writes the values beside their stretches", () => {
    expect(layout.labels).toEqual([
      { text: "200", position: [100, 100, -54], kind: "normal" },
      { text: "19", position: [209.5, 100, -54], kind: "lumber" },
      { text: "281", position: [359.5, 100, -54], kind: "normal" },
      { text: "500", position: [250, 100, -94], kind: "overall" },
      { text: "300", position: [554, 100, 150], kind: "overall" },
    ]);
  });

  it("ticks every stop", () => {
    // across: 4 on the segment row and 2 on the overall row; upright: 2
    expect(layout.lines).toHaveLength(2 + 4 + 6 + 1 + 2 + 2);
    expect(layout.lines).toContainEqual([[194, 100, -46], [206, 100, -34]]);
  });
});

it("seen from above, the chain across goes to the front edge", () => {
  const layout = layoutDimensions(step({ axis: "z", side: 1 }, [across]), box);
  expect(layout.lines[0]).toEqual([[0, 140, 300], [500, 140, 300]]);
});

it("seen from below, chains sit on the bottom face", () => {
  const layout = layoutDimensions(step({ axis: "z", side: -1 }, [across]), box);
  expect(layout.lines[0][0][2]).toBe(0);
});

it("a step at the part's ends has the overall size only, just outside", () => {
  const layout = layoutDimensions(step({ axis: "y", side: 1 }, [{ axis: "x", side: "below", stops: [0, 500], segments: [] }]), box);
  expect(layout.lines[0]).toEqual([[0, 100, -40], [500, 100, -40]]);
  expect(layout.labels).toEqual([{ text: "500", position: [250, 100, -54], kind: "overall" }]);
});

it("the gap between rows is 8% of the longest side, at least 20mm", () => {
  expect(dimensionGap(box)).toBe(40);
  expect(dimensionGap({ min: [0, 0, 0], max: [100, 38, 89] })).toBe(20);
});

it("the Dimensions button looks as the CLI's dimension view does", () => {
  expect(dimensionDirection({ axis: "y", side: 1 })).toEqual([0, 1, 0]);
  expect(dimensionDirection({ axis: "x", side: -1 })).toEqual([-1, 0, 0]);
  expect(dimensionDirection({ axis: "z", side: 1 })).toEqual([0, 1e-4, 1]);
  expect(dimensionDirection({ axis: "z", side: -1 })).toEqual([0, -1e-4, -1]);
});

it("values read as the CLI writes them", () => {
  expect([formatMm(19), formatMm(364.5), formatMm(281.04), formatMm(0.05)]).toEqual(["19", "364.5", "281", "0.05"]);
});

describe("crowded values", () => {
  it("show the overall sizes first, then the others, then lumber", () => {
    const labels = [
      { text: "19", position: [0, 0, 0] as [number, number, number], kind: "lumber" as const },
      { text: "500", position: [0, 0, 0] as [number, number, number], kind: "overall" as const },
      { text: "200", position: [0, 0, 0] as [number, number, number], kind: "normal" as const },
    ];
    expect(labelOrder(labels)).toEqual([1, 2, 0]);
  });

  it("hide what overlaps a value shown before it", () => {
    const rects = [
      { left: 0, top: 0, right: 10, bottom: 10 },
      { left: 5, top: 5, right: 15, bottom: 15 },
      { left: 20, top: 0, right: 30, bottom: 10 },
    ];
    expect(visibleLabels(rects, [1, 0, 2])).toEqual([false, true, true]);
  });

  it("off screen (no size), hide nothing", () => {
    const rects = [{ left: 5, top: 5, right: 5, bottom: 5 }, { left: 0, top: 0, right: 10, bottom: 10 }];
    expect(visibleLabels(rects, [0, 1])).toEqual([true, true]);
  });
});
