// @vitest-environment jsdom
import { expect, it } from "vitest";
import { openViewer, VIEWS } from "../src/viewer";

it("views look as render's do: front from +y, right from -x", () => {
  expect(VIEWS.Front).toEqual([0, 1, 0]);
  expect(VIEWS.Right).toEqual([-1, 0, 0]);
  expect(VIEWS.Iso).toEqual([-1, 1, 1]);
});

it("a browser without WebGL is told so, and the rest of the page goes on", () => {
  const container = document.createElement("div");
  const viewer = openViewer(container); // jsdom has no WebGL
  expect(container.querySelector(".no-webgl")?.textContent).toMatch(/cannot draw 3D \(WebGL\).*use another browser/);
  expect(() => viewer.show(null)).not.toThrow();
});
