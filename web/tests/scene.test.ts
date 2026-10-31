import * as THREE from "three";
import { describe, expect, it } from "vitest";
import { buildScene, directionVector, holeMesh, pieceMatrix } from "../src/scene";
import type { PieceView, View } from "../src/types";

const piece = (id: string, over: Partial<PieceView> = {}): PieceView => ({
  id, type: "2x4", length: 300, group: 0, min: [0, 38, 11], max: [38, 338, 100],
  faces: { top: "+y", right: "-z", front: "-x" }, size: [89, 38, 300], position: [38, 38, 100],
  rotation: [[0, -1, 0], [0, 0, 1], [-1, 0, 0]], line: 2, ...over,
});

const view = (over: Partial<View> = {}): View => ({ valid: true, error: null, overall_size: [38, 338, 100],
  size_reference: "b", pieces: [piece("b")], problems: [], connections: [], holes: [], ...over });

describe("pieces", () => {
  it("are boxes placed by their rotation and position", () => {
    const box = new THREE.Box3().setFromObject(buildScene(view()).pieces.get("b")!.mesh);
    expect(box.min.toArray()).toEqual([0, 38, 11]);
    expect(box.max.toArray()).toEqual([38, 338, 100]);
  });

  it("matrices are the view's", () => {
    const m = pieceMatrix(piece("b")).elements; // column-major
    expect([m[0], m[4], m[8], m[12]]).toEqual([0, -1, 0, 38]);
    expect([m[13], m[14]]).toEqual([38, 100]);
  });
});

describe("holes", () => {
  it("run from their entry the way they point", () => {
    const mesh = holeMesh(view(), { piece: "b", center: [10, 0, 50], direction: "+y", diameter: 2.5, depth: 27 }, 0);
    mesh.updateMatrixWorld();
    const box = new THREE.Box3().setFromObject(mesh);
    expect(box.min.y).toBeCloseTo(-0.2);
    expect(box.max.y).toBeCloseTo(27.2);
  });

  it("go through the whole piece when they have no depth", () => {
    const parts = buildScene(view({ holes: [{ piece: "b", kind: "pilot", center: [19, 38, 50], direction: "+y", diameter: 2.5, depth: null }] }));
    parts.holes[0].updateMatrixWorld();
    const box = new THREE.Box3().setFromObject(parts.holes[0]);
    expect(box.max.y - box.min.y).toBeCloseTo(300.4);
  });

  it("directions are axes", () => {
    expect(directionVector("-x").toArray()).toEqual([-1, 0, 0]);
  });
});

it("labels sit at the pieces' centres and the bounds hold them all", () => {
  const parts = buildScene(view());
  expect(parts.labels[0].position.toArray()).toEqual([19, 188, 55.5]);
  expect(parts.bounds.max.toArray()).toEqual([38, 338, 100]);
});
