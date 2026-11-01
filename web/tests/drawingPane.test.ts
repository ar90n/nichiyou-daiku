// @vitest-environment jsdom
import { expect, it, vi } from "vitest";
import { DrawingPane } from "../src/drawingPane";
import { safeDrawing } from "../src/model";

const root = () => {
  const el = document.createElement("div");
  el.innerHTML = '<div class="drawing-tools"><button class="close">3D</button><button class="fit">Fit</button></div><div class="drawing-page"></div>';
  return el;
};

it("shows a drawing, fitted, and closes back to the 3D", () => {
  const el = root();
  const onClose = vi.fn();
  const pane = new DrawingPane(el, onClose);
  pane.show({ svg: '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 280 100"><text>A</text></svg>', error: null });
  expect(el.hidden).toBe(false);
  const svg = el.querySelector("svg")!;
  expect(svg.getAttribute("viewBox")).not.toBe("0 0 280 100");
  el.querySelector<HTMLButtonElement>(".close")!.click();
  expect(onClose).toHaveBeenCalled();
});

it("says what is wrong instead of a drawing", () => {
  const el = root();
  const pane = new DrawingPane(el, () => {});
  pane.show({ svg: null, error: "a has no holes, so it has no drawing: it is only cut to length" });
  expect(el.querySelector(".drawing-error")?.textContent).toBe("a has no holes, so it has no drawing: it is only cut to length");
  expect(el.querySelector("svg")).toBeNull();
  pane.hide();
  expect(el.hidden).toBe(true);
});

it("a core that throws while drawing says so", () => {
  const answer = safeDrawing(() => { throw new Error("unreachable"); }, "", 0);
  expect(answer).toEqual({ svg: null, error: "Internal error in the core while drawing: unreachable. Please report it with the .nd file." });
});
