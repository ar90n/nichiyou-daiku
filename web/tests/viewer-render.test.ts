// @vitest-environment jsdom
import * as THREE from "three";
import { beforeEach, expect, it, vi } from "vitest";
import type { PieceView, View } from "../src/types";

// jsdom has no WebGL: a renderer that counts the meshes each frame shows,
// and the points of the dimension lines
const frames: number[] = [];
const dimensionPoints: number[] = [];
vi.mock("three", async (importOriginal) => {
  const actual = await importOriginal<typeof import("three")>();
  class CountingRenderer {
    domElement = document.createElement("canvas");
    setPixelRatio() {}
    setSize() {}
    render(scene: THREE.Scene) {
      let meshes = 0;
      scene.traverseVisible((object) => { if ((object as THREE.Mesh).isMesh) meshes++; });
      frames.push(meshes);
      let points = 0;
      scene.traverseVisible((object) => {
        if (object.userData.dimensions) points += (object as THREE.LineSegments).geometry.getAttribute("position").count;
      });
      dimensionPoints.push(points);
    }
  }
  return { ...actual, WebGLRenderer: CountingRenderer };
});
globalThis.ResizeObserver ??= class { observe() {} unobserve() {} disconnect() {} } as unknown as typeof ResizeObserver;

const { Viewer } = await import("../src/viewer");

const piece: PieceView = {
  id: "b", type: "2x4", length: 300, group: 0, min: [0, 0, 0], max: [89, 38, 300],
  faces: { top: "+z", right: "+x", front: "+y" }, size: [89, 38, 300], position: [0, 0, 0],
  rotation: [[1, 0, 0], [0, 1, 0], [0, 0, 1]], line: 1,
};
const view = (pieces: PieceView[]): View => ({ valid: true, error: null, overall_size: null,
  size_reference: null, pieces, problems: [], connections: [], holes: [], parts: [], steps: [], steps_declared: false, steps_hint: null });

beforeEach(() => {
  frames.length = 0;
  dimensionPoints.length = 0;
});

it("a view with no pieces clears the model already drawn", () => {
  const viewer = new Viewer(document.createElement("div"));
  viewer.show(view([piece]));
  expect(frames.at(-1)).toBe(1);
  viewer.show(view([])); // e.g. a file with only variables so far
  expect(frames.at(-1)).toBe(0);
});

const second: PieceView = { ...piece, id: "c", min: [200, 0, 0], max: [289, 38, 300], position: [200, 0, 0] };

it("a step draws only the pieces it shows", () => {
  const viewer = new Viewer(document.createElement("div"));
  viewer.show(view([piece, second]));
  expect(frames.at(-1)).toBe(2);
  viewer.showOnly(new Set(["c"]));
  expect(frames.at(-1)).toBe(1);
  viewer.showOnly(null);
  expect(frames.at(-1)).toBe(2);
});

it("fitting a step keeps the way the camera looks", () => {
  const viewer = new Viewer(document.createElement("div"));
  viewer.show(view([piece, second]));
  viewer.setView("Front");
  viewer.fit({ min: second.min, max: second.max });
  const looking = viewer.camera.position.clone().sub(viewer.controls.target).normalize();
  expect(looking.toArray().map((x) => Math.round(x * 1000) / 1000 + 0)).toEqual([0, 1, 0]);
  // OrbitControls.update() clamps the target, so it is off by a rounding
  const [x, y, z] = viewer.controls.target.toArray();
  expect([x, y, z].map((v) => Math.round(v * 1000) / 1000)).toEqual([244.5, 19, 150]);
});

it("on a step, the view buttons look at the step's part, not the whole model", () => {
  const viewer = new Viewer(document.createElement("div"));
  viewer.show(view([piece, second]));
  viewer.fit({ min: second.min, max: second.max });
  viewer.setView("Top");
  const [x, y, z] = viewer.controls.target.toArray();
  expect([x, y, z].map((v) => Math.round(v * 1000) / 1000)).toEqual([244.5, 19, 150]);
  viewer.fit(null);
  viewer.setView("Top");
  expect(Math.round(viewer.controls.target.x * 1000) / 1000).toBe(144.5);
});

const layout = {
  lines: [[[0, 0, -40], [89, 0, -40]], [[0, 0, 0], [0, 0, -48]]] as [[number, number, number], [number, number, number]][],
  labels: [{ text: "89", position: [44.5, 0, -54] as [number, number, number], kind: "overall" as const }],
};

it("draws a step's dimensions and takes them away", () => {
  const container = document.createElement("div");
  const viewer = new Viewer(container);
  viewer.show(view([piece]));
  viewer.showDimensions(layout);
  expect(dimensionPoints.at(-1)).toBe(4);
  expect(container.querySelectorAll(".dim-label.overall")).toHaveLength(1);
  viewer.showDimensions(null);
  expect(dimensionPoints.at(-1)).toBe(0);
  expect(container.querySelectorAll(".dim-label")).toHaveLength(0);
});

it("opening another view leaves no dimensions behind", () => {
  const viewer = new Viewer(document.createElement("div"));
  viewer.show(view([piece]));
  viewer.showDimensions(layout);
  viewer.show(view([piece]));
  expect(dimensionPoints.at(-1)).toBe(0);
});

it("the Dimensions button looks along the step's view at the step's part", () => {
  const viewer = new Viewer(document.createElement("div"));
  viewer.show(view([piece, second]));
  viewer.fit({ min: second.min, max: second.max });
  viewer.lookAlong([0, 1, 0]);
  const looking = viewer.camera.position.clone().sub(viewer.controls.target).normalize();
  expect(looking.toArray().map((x) => Math.round(x * 1000) / 1000 + 0)).toEqual([0, 1, 0]);
  expect(Math.round(viewer.controls.target.x * 1000) / 1000).toBe(244.5);
});

it("turning the piece names off keeps the dimension values", () => {
  const container = document.createElement("div");
  const viewer = new Viewer(container);
  viewer.show(view([piece]));
  viewer.showDimensions(layout);
  viewer.setLabels(false);
  expect(container.querySelector<HTMLElement>(".labels")!.style.display).not.toBe("none");
  expect(container.querySelector<HTMLElement>(".label")!.style.display).toBe("none");
  expect(container.querySelector<HTMLElement>(".dim-label")!.style.display).not.toBe("none");
});

it("the camera frames the dimension rows with the part", () => {
  const viewer = new Viewer(document.createElement("div"));
  viewer.show(view([piece]));
  viewer.showDimensions({ lines: [[[0, 0, -200], [89, 0, -200]]], labels: [] });
  viewer.fit({ min: piece.min, max: piece.max });
  expect(Math.round(viewer.controls.target.z * 1000) / 1000).toBe(50);
  viewer.lookAlong([0, 1, 0]);
  expect(Math.round(viewer.controls.target.z * 1000) / 1000).toBe(50);
});

it("piece names stay off after opening another view", () => {
  const container = document.createElement("div");
  const viewer = new Viewer(container);
  viewer.show(view([piece]));
  viewer.setLabels(false);
  viewer.show(view([piece]));
  const shown = () => [...container.querySelectorAll<HTMLElement>(".label")].filter((e) => e.style.display !== "none");
  expect(shown()).toHaveLength(0);
  viewer.setLabels(true);
  expect(shown()).toHaveLength(1); // the first view's names left with it
});

it("a model shown again keeps the camera where it was put", () => {
  const viewer = new Viewer(document.createElement("div"));
  viewer.show(view([piece]));
  viewer.camera.position.set(1, 2, 3);
  viewer.show(view([piece]), true);
  expect(viewer.camera.position.toArray()).toEqual([1, 2, 3]);
  viewer.show(view([piece]));
  expect(viewer.camera.position.toArray()).not.toEqual([1, 2, 3]);
});
