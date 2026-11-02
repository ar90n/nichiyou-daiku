import * as THREE from "three";
import type { HoleShape, PieceView, View } from "./types";

export const COLORS = {
  wood: 0xd8b48a,
  edge: 0x5c4630,
  hole: 0x2a2018,
  counterbore: 0x4a3828,
  selected: 0x3b82f6,
  earlier: 0xc8c2b8,
  problem: 0xe0433a,
  groups: [0x3b82f6, 0x22a06b, 0xf59e0b, 0x9b5de5, 0x0ea5b7, 0xdb2777],
};

const AXES: Record<string, number> = { x: 0, y: 1, z: 2 };

// Holes stand this far out of the face so that they show on it
const PROUD_MM = 0.2;

export interface PieceParts {
  mesh: THREE.Mesh<THREE.BoxGeometry, THREE.MeshStandardMaterial>;
  edges: THREE.LineSegments;
}

export interface SceneParts {
  root: THREE.Group;
  pieces: Map<string, PieceParts>;
  holes: THREE.Mesh[];
  labels: { id: string; position: THREE.Vector3 }[];
  bounds: THREE.Box3;
}

function axisOf(direction: string): number {
  const axis = AXES[direction[1]];
  if (axis === undefined || !"+-".includes(direction[0]) || direction.length !== 2) {
    throw new Error(`Unknown direction "${direction}": the core gives +x, -x, +y, -y, +z or -z`);
  }
  return axis;
}

export function directionVector(direction: string): THREE.Vector3 {
  const vector = new THREE.Vector3();
  vector.setComponent(axisOf(direction), direction[0] === "+" ? 1 : -1);
  return vector;
}

/** The piece's local box (corner at the origin) to the world: rotation, then position. */
export function pieceMatrix(piece: PieceView): THREE.Matrix4 {
  const [r0, r1, r2] = piece.rotation;
  const [x, y, z] = piece.position;
  return new THREE.Matrix4().set(
    r0[0], r0[1], r0[2], x,
    r1[0], r1[1], r1[2], y,
    r2[0], r2[1], r2[2], z,
    0, 0, 0, 1,
  );
}

/** A hole as a cylinder from its centre on the face; one without depth goes through its piece. */
export function holeMesh(view: View, hole: HoleShape, color: number): THREE.Mesh {
  const along = directionVector(hole.direction);
  let depth = hole.depth;
  if (depth === null) {
    const piece = view.pieces.find((p) => p.id === hole.piece);
    const axis = axisOf(hole.direction);
    depth = piece ? piece.max[axis] - piece.min[axis] : 0;
  }
  const radius = hole.diameter / 2;
  const geometry = new THREE.CylinderGeometry(radius, radius, depth + 2 * PROUD_MM, 20);
  const mesh = new THREE.Mesh(geometry, new THREE.MeshStandardMaterial({ color }));
  mesh.quaternion.setFromUnitVectors(new THREE.Vector3(0, 1, 0), along);
  mesh.position.fromArray(hole.center).addScaledVector(along, depth / 2);
  if (hole.countersink) {
    // The cone a screw head sits in: as wide as the countersink at the face,
    // narrowing to the hole; its parent's visibility and colour carry over
    const sink = (hole.countersink - hole.diameter) / 2;
    const cone = new THREE.Mesh(
      new THREE.CylinderGeometry(radius, hole.countersink / 2, sink + PROUD_MM, 20),
      mesh.material,
    );
    cone.position.y = -depth / 2 + (sink - PROUD_MM) / 2;
    mesh.add(cone);
  }
  mesh.userData.piece = hole.piece;
  return mesh;
}

export function buildScene(view: View): SceneParts {
  const root = new THREE.Group();
  const pieces = new Map<string, PieceParts>();
  const bounds = new THREE.Box3();
  for (const piece of view.pieces) {
    const [w, h, l] = piece.size;
    const geometry = new THREE.BoxGeometry(w, h, l).translate(w / 2, h / 2, l / 2);
    const mesh = new THREE.Mesh(geometry, new THREE.MeshStandardMaterial({ color: COLORS.wood }));
    const edges = new THREE.LineSegments(
      new THREE.EdgesGeometry(geometry),
      new THREE.LineBasicMaterial({ color: COLORS.edge }),
    );
    const matrix = pieceMatrix(piece);
    for (const object of [mesh, edges]) {
      object.matrixAutoUpdate = false;
      object.matrix.copy(matrix);
      object.matrixWorldNeedsUpdate = true;
      root.add(object);
    }
    mesh.userData.id = piece.id;
    pieces.set(piece.id, { mesh, edges });
    bounds.expandByPoint(new THREE.Vector3().fromArray(piece.min));
    bounds.expandByPoint(new THREE.Vector3().fromArray(piece.max));
  }
  const holes = view.holes.map((hole) =>
    holeMesh(view, hole, hole.kind === "counterbore" ? COLORS.counterbore : COLORS.hole),
  );
  for (const hole of holes) root.add(hole);
  const labels = view.pieces.map((piece) => ({
    id: piece.id,
    position: new THREE.Vector3().fromArray(piece.min).add(new THREE.Vector3().fromArray(piece.max)).multiplyScalar(0.5),
  }));
  return { root, pieces, holes, labels, bounds };
}
