// @vitest-environment jsdom
import * as THREE from "three";
import { beforeEach, expect, it, vi } from "vitest";
import type { PieceView, View } from "../src/types";

// jsdom has no WebGL: a renderer that counts the meshes each frame shows
const frames: number[] = [];
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

beforeEach(() => { frames.length = 0; });

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
