// @vitest-environment jsdom
import { readFileSync } from "node:fs";
import { expect, it } from "vitest";

/** The values the top-level rules matching `el` give `property`. */
function declared(el: Element, property: string): string[] {
  return Array.from(document.styleSheets)
    .flatMap((sheet) => Array.from(sheet.cssRules))
    .filter((rule): rule is CSSStyleRule => "selectorText" in rule && el.matches((rule as CSSStyleRule).selectorText))
    .map((rule) => rule.style.getPropertyValue(property))
    .filter(Boolean);
}

it("the 3D's labels stay under a drawing shown in its place", () => {
  // Vitest empties imported CSS, so the sheet is read as text
  document.head.innerHTML = `<style>${readFileSync("src/style.css", "utf8")}</style>`;
  document.body.innerHTML = '<section class="view"><div id="scene"></div><div id="drawing" class="drawing"></div></section>';
  // three's CSS2DRenderer gives every label a z-index of its own; kept inside
  // the scene's own stacking context, they cannot rise over the pane's 2
  expect(declared(document.getElementById("scene")!, "isolation")).toContain("isolate");
  expect(declared(document.getElementById("drawing")!, "z-index")).toContain("2");
});
