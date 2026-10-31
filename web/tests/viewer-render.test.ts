// @vitest-environment jsdom
import * as THREE from "three";
import { beforeEach, expect, it, vi } from "vitest";
import type { PieceView, View } from "../src/types";

// jsdom has no WebGL: a renderer that counts the meshes each frame draws
const frames: number[] = [];
vi.mock("three", async (importOriginal) => {
  const actual = await importOriginal<typeof import("three")>();
  class CountingRenderer {
    domElement = document.createElement("canvas");
    setPixelRatio() {}
    setSize() {}
    render(scene: THREE.Scene) {
      let meshes = 0;
      scene.traverse((object) => { if ((object as THREE.Mesh).isMesh) meshes++; });
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
  size_reference: null, pieces, problems: [], connections: [], holes: [] });

beforeEach(() => { frames.length = 0; });

it("a view with no pieces clears the model already drawn", () => {
  const viewer = new Viewer(document.createElement("div"));
  viewer.show(view([piece]));
  expect(frames.at(-1)).toBe(1);
  viewer.show(view([])); // e.g. a file with only variables so far
  expect(frames.at(-1)).toBe(0);
});
