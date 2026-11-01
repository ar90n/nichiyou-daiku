// @vitest-environment jsdom
import { expect, it } from "vitest";
import { fastenerTotals, manualTitle, renderManual, type Drawings } from "../src/manual";
import type { HardwareView, PieceView, StepView, View } from "../src/types";

const step = (number: number, pieces: string[], hardware: HardwareView[] = []): StepView => ({
  number, name: number === 1 ? "Leg" : null, kind: number === 1 ? "first" : "attach", pieces, connections: [],
  shown: pieces, view: { axis: "y", side: 1 }, hardware, dimensions: [],
});

const v = (over: Partial<View> = {}): View => ({
  valid: true, error: null, overall_size: [440, 530, 750], size_reference: null,
  pieces: [
    { id: "leg", type: "2x4", length: 750, line: 1 } as PieceView,
    { id: "rail", type: "1x4", length: 364.5, line: 2 } as PieceView,
    { id: "top", type: "1x4", length: 440, line: 3 } as PieceView,
  ],
  problems: [], connections: [], holes: [],
  parts: [
    { pieces: ["leg"], type: "2x4", length: 750, count: 1, drilled: true },
    { pieces: ["rail"], type: "1x4", length: 364.5, count: 1, drilled: false },
    { pieces: ["top"], type: "1x4", length: 440, count: 1, drilled: true },
  ],
  steps: [step(1, ["leg"]), step(2, ["rail", "top"], [{ name: "Slim screw 3.8x65", count: 2 }])],
  steps_declared: true, steps_hint: null, ...over,
});

const svg = (label: string) =>
  `<svg xmlns="http://www.w3.org/2000/svg" width="280mm" height="140mm" viewBox="0 0 280 140"><text>${label}</text></svg>`;
const draw: Drawings = {
  part: (i) => ({ svg: svg(`part ${i}`), notes: [], error: null }),
  step: (n) => ({ svg: svg(`step ${n}`), notes: [], error: null }),
};

const rows = (table: Element | null) =>
  [...(table?.querySelectorAll("tr") ?? [])].slice(1).map((tr) => [...tr.querySelectorAll("td")].map((td) => td.textContent));

const manual = (view: View = v(), drawings: Drawings = draw) => {
  const root = document.createElement("div");
  renderManual(root, view, "file-wagon.nd", drawings);
  return root;
};

it("fastenerTotals sums each fastener over the steps, in the order they first come", () => {
  const steps = [
    step(1, ["a"], [{ name: "Dowel 8x30", count: 4 }]),
    step(2, ["b"], [{ name: "Slim screw 3.8x65", count: 2 }, { name: "Dowel 8x30", count: 2 }]),
  ];
  expect(fastenerTotals(steps)).toEqual([{ name: "Dowel 8x30", count: 6 }, { name: "Slim screw 3.8x65", count: 2 }]);
  expect(fastenerTotals([step(1, ["a"])])).toEqual([]);
});

it("the title is the file's name, as the CLI's steps.md takes it", () => {
  expect(manualTitle("file-wagon.nd")).toBe("file-wagon: assembly manual");
  expect(manualTitle("shelf")).toBe("shelf: assembly manual");
  expect(manualTitle(null)).toBe("Assembly manual");
});

it("the first page says what to get: the parts, numbered as their drawings, and the fasteners", () => {
  const cover = manual().querySelector(".sheet.cover")!;
  expect(cover.querySelector("h1")?.textContent).toBe("file-wagon: assembly manual");
  expect(cover.querySelector(".size")?.textContent).toBe("Overall size 440×530×750mm");
  expect(rows(cover.querySelector("table.parts"))).toEqual([
    ["Part 1", "leg", "2x4", "750", "1"],
    ["", "rail", "1x4", "364.5", "1"],
    ["Part 2", "top", "1x4", "440", "1"],
  ]);
  expect(rows(cover.querySelector("table.fasteners"))).toEqual([["Slim screw 3.8x65", "2"]]);
  expect(cover.querySelector(".problems")).toBeNull();
});

it("the first page lists the design's problems when it has some", () => {
  const view = v({ problems: [{ kind: "overlap", message: "leg and rail overlap", pieces: ["leg", "rail"], volume_mm3: 1 }] });
  const cover = manual(view).querySelector(".sheet.cover")!;
  expect([...cover.querySelectorAll("ul.problems li")].map((li) => li.textContent)).toEqual(["leg and rail overlap"]);
});

it("drilled parts have drawings, captioned with their numbers", () => {
  const sheets = manual().querySelector(".sheet.part-drawings")!;
  expect([...sheets.querySelectorAll("figure.part figcaption")].map((c) => c.textContent)).toEqual(["Part 1", "Part 2"]);
  expect([...sheets.querySelectorAll("figure.part text")].map((t) => t.textContent)).toEqual(["part 0", "part 2"]);
});

it("a design without holes has no part drawings", () => {
  const view = v({ parts: v().parts.map((p) => ({ ...p, drilled: false })) });
  const root = manual(view);
  expect(root.querySelector(".part-drawings")).toBeNull();
  expect(rows(root.querySelector("table.parts")).map((r) => r[0])).toEqual(["", "", ""]);
});

it("each step has a page: its drawing, then its pieces beside its fasteners", () => {
  const root = manual();
  expect([...root.children].map((c) => c.className)).toEqual(["sheet cover", "sheet part-drawings", "sheet step", "sheet step"]);
  const second = root.querySelector('.sheet.step[data-step="2"]')!;
  expect(second.querySelector("figure.step text")?.textContent).toBe("step 2");
  expect(rows(second.querySelector(".step-tables table.pieces"))).toEqual([["rail", "1x4", "364.5"], ["top", "1x4", "440"]]);
  expect(rows(second.querySelector(".step-tables table.fasteners"))).toEqual([["Slim screw 3.8x65", "2"]]);
});

it("steps list their pieces, and fasteners only when they have some", () => {
  const first = manual().querySelector('.sheet.step[data-step="1"]')!;
  expect(rows(first.querySelector("table.pieces"))).toEqual([["leg", "2x4", "750"]]);
  expect(first.querySelector("table.fasteners")).toBeNull();
  const bare = manual(v({ steps: [step(1, ["leg"]), step(2, ["rail", "top"])] }));
  expect(bare.querySelector(".cover table.fasteners")).toBeNull();
});

it("a drawing keeps its view box but sizes to its page", () => {
  const drawn = manual().querySelector("figure.step svg")!;
  expect(drawn.getAttribute("viewBox")).toBe("0 0 280 140");
  expect(drawn.getAttribute("width")).toBeNull();
  expect(drawn.getAttribute("height")).toBeNull();
});

it("a drawing that cannot be made says why, and notes follow each drawing", () => {
  const failing: Drawings = {
    part: () => ({ svg: null, notes: [], error: "Internal error in the core while drawing: boom. Please report it with the .nd file." }),
    step: (n) => n === 2
      ? { svg: null, notes: [], error: "There is no step 2: the design has steps 1 to 1" }
      : { svg: svg("step 1"), notes: ["2 dimension values along x in step 1 do not fit: Split the step"], error: null },
  };
  const root = manual(v(), failing);
  const part = root.querySelector("figure.part")!;
  expect(part.querySelector("svg")).toBeNull();
  expect(part.querySelector("p.error")?.textContent).toContain("Internal error in the core while drawing");
  const first = root.querySelector('.sheet.step[data-step="1"]')!;
  expect([...first.querySelectorAll("figure.step ul.notes li")].map((li) => li.textContent))
    .toEqual(["2 dimension values along x in step 1 do not fit: Split the step"]);
  const second = root.querySelector('.sheet.step[data-step="2"]')!;
  expect(second.querySelector("h2")?.textContent).toBe("Step 2");
  expect(second.querySelector("p.error")?.textContent).toBe("There is no step 2: the design has steps 1 to 1");
  expect(first.querySelector("h2")).toBeNull();
});
