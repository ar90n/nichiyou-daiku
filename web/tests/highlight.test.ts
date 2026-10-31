import { describe, expect, it } from "vitest";
import { atLine, connectionLine, connectionsOf, forPiece, forProblem } from "../src/highlight";
import type { PieceView, View } from "../src/types";

const piece = (id: string, line: number) => ({ id, line } as PieceView);
const v: View = {
  valid: false, error: null, overall_size: null, size_reference: null,
  pieces: [piece("a", 1), piece("b", 2), piece("c", 3)],
  connections: [
    { base: "a", target: "b", kind: "screw", diameter: 3.8, length: 65, screw_type: "slim", line: 5 },
    { base: "b", target: "c", kind: "vanilla", diameter: null, length: null, screw_type: null, line: 6 },
  ],
  holes: [], problems: [],
};

it("a piece is selected with its line and connections", () => {
  const h = forPiece(v, "b");
  expect([...h.paint]).toEqual([["b", "selected"]]);
  expect(h.line).toBe(2);
  expect(connectionsOf(v, "b").map((c) => c.line)).toEqual([5, 6]);
});

describe("problems", () => {
  it("conflicts paint their loop at the connection's line", () => {
    const h = forProblem(v, { kind: "conflict", message: "", connection: ["b", "c"], constraint: "contact", axis: "x", mismatch_mm: -38, loop: ["b", "a", "c"] });
    expect([...h.paint.keys()].sort()).toEqual(["a", "b", "c"]);
    expect(h.line).toBe(6);
  });

  it("unconnected groups get a colour each", () => {
    const h = forProblem(v, { kind: "unconnected", message: "", groups: [["a", "b"], ["c"]] });
    expect(h.paint.get("c")).toEqual({ group: 1 });
    expect(h.line).toBeNull();
  });

  it("hole collisions fade the piece and show both holes", () => {
    const hole = { entry: [0, 0, 0], direction: "+x", depth: 10, diameter: 3.8 } as const;
    const h = forProblem(v, { kind: "hole_collision", message: "", connection: ["a", "b"], other_connection: ["b", "c"], piece: "b", fastener: "screw", holes: [{ ...hole, entry: [0, 0, 0] }, { ...hole, entry: [1, 0, 0] }] });
    expect([...h.faded]).toEqual(["b"]);
    expect(h.holes[1]).toEqual({ piece: "b", center: [1, 0, 0], direction: "+x", diameter: 3.8, depth: 10 });
    expect(h.line).toBe(5);
  });

  it("overlaps go to the first piece's line", () => {
    expect(forProblem(v, { kind: "overlap", message: "", pieces: ["c", "a"], volume_mm3: 1 }).line).toBe(3);
  });
});

it("a line names its piece or connection", () => {
  expect(atLine(v, 2)).toEqual({ piece: "b" });
  expect(atLine(v, 6)).toEqual({ connection: ["b", "c"] });
  expect(atLine(v, 4)).toBeNull();
  expect(connectionLine(v, ["b", "a"])).toBe(5);
});
