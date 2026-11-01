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

/** The values the rules under an @media matching `media` give `el` for `property`. */
function declared(el: Element, property: string, media: string): string[] {
  const values: string[] = [];
  for (const sheet of Array.from(document.styleSheets)) {
    for (const rule of Array.from(sheet.cssRules)) {
      const group = rule as CSSMediaRule;
      if (!group.media?.mediaText.includes(media)) continue;
      for (const inner of Array.from(group.cssRules) as CSSStyleRule[]) {
        if (inner.selectorText && el.matches(inner.selectorText)) values.push(inner.style.getPropertyValue(property));
      }
    }
  }
  return values.filter(Boolean);
}

const printed = (el: Element, property: string) => declared(el, property, "print");
const onPhones = (el: Element, property: string) => declared(el, property, "max-width: 759px");

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

it("a drawing leaves room on its page for its caption and two lines of notes", () => {
  document.body.className = "manual-mode";
  const heights = printed(at("figure.part svg"), "max-height").map((h) => parseFloat(h));
  expect(heights.length).toBeGreaterThan(0);
  // 190mm of page, less the caption (about 6mm) and two notes (about 12mm)
  for (const height of heights) expect(height).toBeLessThanOrEqual(190 - 6 - 12);
});

it("on a phone the sheets keep narrow margins and long names wrap, so the tables stay on the paper", () => {
  document.body.className = "manual-mode";
  expect(onPhones(at("#manual"), "padding")).toContain("6px");
  expect(onPhones(at(".sheet.cover"), "padding")).toContain("12px");
  expect(onPhones(at("table.parts td"), "overflow-wrap")).toContain("anywhere");
});
