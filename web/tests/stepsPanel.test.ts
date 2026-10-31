// @vitest-environment jsdom
import { describe, expect, it, vi } from "vitest";
import { renderSteps, renderUnavailable } from "../src/stepsPanel";
import type { PieceView, View } from "../src/types";

const v = (over: Partial<View> = {}): View => ({
  valid: true, error: null, overall_size: null, size_reference: null,
  pieces: [{ id: "leg", type: "2x4", length: 750, line: 1 } as PieceView, { id: "rail", type: "1x4", length: 364.5, line: 2 } as PieceView],
  problems: [], connections: [], holes: [],
  parts: [{ pieces: ["leg"], type: "2x4", length: 750, count: 1 }, { pieces: ["rail"], type: "1x4", length: 364.5, count: 1 }],
  steps: [
    { number: 1, name: "Leg", kind: "first", pieces: ["leg"], connections: [], shown: ["leg"], view: { axis: "z", side: 1 }, hardware: [] },
    { number: 2, name: null, kind: "attach", pieces: ["rail"], connections: [["rail", "leg"]], shown: ["leg", "rail"],
      view: { axis: "y", side: 1 }, hardware: [{ name: "Slim screw 3.8x65", count: 2 }] },
  ],
  steps_declared: true, steps_hint: null, ...over,
});
const none = { onStep: () => {}, onPart: () => {} };

it("lists the parts and every step, the current one open", () => {
  const root = document.createElement("div");
  renderSteps(root, v(), 2, null, none);
  expect([...root.querySelectorAll(".card h3")].map((h) => h.textContent)).toEqual(["Parts", "Step 1 - Leg", "Step 2"]);
  const open = root.querySelector(".card.open")!;
  expect(open.getAttribute("data-step")).toBe("2");
  expect([...open.querySelectorAll("td")].map((td) => td.textContent)).toEqual(["rail", "1x4", "364.5", "Slim screw 3.8x65", "2"]);
});

it("the parts list picks a part, and lets it go", () => {
  const root = document.createElement("div");
  const onPart = vi.fn();
  renderSteps(root, v(), 0, 1, { ...none, onPart });
  const rows = root.querySelectorAll<HTMLElement>("tr.pickable");
  expect([...rows[0].querySelectorAll("td")].map((td) => td.textContent)).toEqual(["leg", "2x4", "750", "1"]);
  expect(rows[1].className).toBe("pickable picked");
  rows[0].click();
  rows[1].click();
  expect(onPart.mock.calls).toEqual([[0], [null]]);
});

describe("going through the steps", () => {
  it("by the buttons, which stop at the ends", () => {
    const root = document.createElement("div");
    const onStep = vi.fn();
    renderSteps(root, v(), 0, null, { ...none, onStep });
    expect(root.querySelector(".position")?.textContent).toBe("Parts / 2");
    expect(root.querySelector<HTMLButtonElement>("button.prev")!.disabled).toBe(true);
    root.querySelector<HTMLButtonElement>("button.next")!.click();
    renderSteps(root, v(), 2, null, { ...none, onStep });
    expect(root.querySelector(".position")?.textContent).toBe("2 / 2");
    expect(root.querySelector<HTMLButtonElement>("button.next")!.disabled).toBe(true);
    expect(onStep).toHaveBeenCalledWith(1);
  });

  it("by a card's heading", () => {
    const root = document.createElement("div");
    const onStep = vi.fn();
    renderSteps(root, v(), 0, null, { ...none, onStep });
    root.querySelector<HTMLElement>('.card[data-step="1"] h3')!.click();
    expect(onStep).toHaveBeenCalledWith(1);
  });
});

it("says how to group steps, and that problems may spoil them", () => {
  const root = document.createElement("div");
  renderSteps(root, v({ steps_hint: "No steps block: …", problems: [{ kind: "overlap", message: "", pieces: ["leg", "rail"], volume_mm3: 1 }] }), 1, null, none);
  expect(root.querySelector(".notice")?.textContent).toBe("No steps block: …");
  expect(root.querySelector(".warning")?.textContent).toBe("This design has 1 problem (see Model); the steps may be wrong");
});

it("says why the steps cannot be shown, where a phone shows it", () => {
  const root = document.createElement("div");
  renderUnavailable(root, "Fix the error first: the steps need a design that reads");
  expect(root.querySelector(".unavailable")?.textContent).toBe("Fix the error first: the steps need a design that reads");
});
