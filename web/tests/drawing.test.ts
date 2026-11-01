import { expect, it } from "vitest";
import { fitBox, panBy, zoomAt } from "../src/drawing";

it("fits the page into the pane, centred, keeping the pane's shape", () => {
  const box = fitBox({ width: 280, height: 100 }, { width: 560, height: 400 });
  expect(box.width / box.height).toBeCloseTo(560 / 400);
  expect(box.width).toBeCloseTo(280 * 1.06);
  expect(box.x + box.width / 2).toBeCloseTo(140);
  expect(box.y + box.height / 2).toBeCloseTo(50);
});

it("zooms about the pointer", () => {
  const box = { x: 0, y: 0, width: 200, height: 100 };
  const zoomed = zoomAt(box, 2, { x: 0.25, y: 0.5 });
  expect(zoomed).toEqual({ x: 25, y: 25, width: 100, height: 50 });
});

it("drags the page with the pointer", () => {
  const box = { x: 0, y: 0, width: 200, height: 100 };
  expect(panBy(box, 50, -20, { width: 400, height: 200 })).toEqual({ x: -25, y: 10, width: 200, height: 100 });
});
