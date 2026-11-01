// @vitest-environment jsdom
import { readFileSync } from "node:fs";
import { afterEach, beforeEach, expect, it } from "vitest";
import { renderManual } from "../src/manual";
import type { PieceView, View } from "../src/types";

// Vitest empties imported CSS, so the sheet is read as text
const css = readFileSync("src/style.css", "utf8");

const view: View = {
  valid: true, error: null, overall_size: [100, 100, 100], size_reference: null,
  pieces: [{ id: "leg", type: "2x4", length: 750, line: 1 } as PieceView],
  problems: [], connections: [], holes: [],
  parts: [{ pieces: ["leg"], type: "2x4", length: 750, count: 1, drilled: true }],
  steps: [{ number: 1, name: null, kind: "first", pieces: ["leg"], connections: [], shown: ["leg"],
    view: { axis: "y", side: 1 }, hardware: [], dimensions: [] }],
  steps_declared: false, steps_hint: null,
};
const drawn = { svg: '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 280 140"></svg>', notes: [], error: null };

beforeEach(() => {
  document.head.innerHTML = `<style>${css}</style>`;
  document.body.innerHTML = `<header><nav id="tabs"></nav></header><main><aside></aside><section class="view"></section>
    <section id="manual"><div class="manual-tools"><button id="print">Print</button></div><div id="manual-pages"></div></section></main>`;
  renderManual(document.getElementById("manual-pages")!, view, "leg.nd", { part: () => drawn, step: () => drawn });
});

afterEach(() => {
  document.head.innerHTML = "";
  document.body.innerHTML = "";
  document.body.className = "";
});

/** The values print gives `el` for `property`: the @media print rules whose selectors match it. */
function printed(el: Element, property: string): string[] {
  const values: string[] = [];
  for (const sheet of Array.from(document.styleSheets)) {
    for (const rule of Array.from(sheet.cssRules)) {
      const media = rule as CSSMediaRule;
      if (!media.media?.mediaText.includes("print")) continue;
      for (const inner of Array.from(media.cssRules) as CSSStyleRule[]) {
        if (inner.selectorText && el.matches(inner.selectorText)) values.push(inner.style.getPropertyValue(property));
      }
    }
  }
  return values.filter(Boolean);
}

const at = (selector: string) => document.querySelector(selector)!;

it("prints the manual on A4 landscape pages of its own", () => {
  expect(css).toMatch(/@page manual\s*\{[^}]*size:\s*A4 landscape/);
  document.body.className = "manual-mode";
  expect(printed(at("#manual"), "page")).toContain("manual");
});

it("starts the part drawings and each step on a new page, and splits no drawing", () => {
  document.body.className = "manual-mode";
  expect(printed(at(".sheet.part-drawings"), "break-before")).toContain("page");
  expect(printed(at(".sheet.step"), "break-before")).toContain("page");
  expect(printed(at(".sheet.cover"), "break-before")).toEqual([]);
  expect(printed(at("figure.part"), "break-inside")).toContain("avoid");
  expect(printed(at("figure.step"), "break-inside")).toContain("avoid");
});

it("leaves the header and the Print button off the paper", () => {
  document.body.className = "manual-mode";
  expect(printed(at("body > header"), "display")).toContain("none");
  expect(printed(at(".manual-tools"), "display")).toContain("none");
});

it("print rules hold only in the manual", () => {
  for (const selector of ["body > header", "#manual", ".sheet.step", "figure.step", ".manual-tools"]) {
    expect(printed(at(selector), "display")).toEqual([]);
    expect(printed(at(selector), "break-before")).toEqual([]);
    expect(printed(at(selector), "page")).toEqual([]);
  }
});
