import type { ConnectionView, HoleShape, Problem, View } from "./types";

export type Paint = "selected" | "problem" | "earlier" | { group: number };

/** What to colour, fade and draw for a selection, and the source line to show. */
export interface Highlight {
  paint: Map<string, Paint>;
  faded: Set<string>;
  holes: HoleShape[];
  line: number | null;
}

export const NONE: Highlight = { paint: new Map(), faded: new Set(), holes: [], line: null };

function painted(ids: string[], paint: Paint, line: number | null): Highlight {
  return { paint: new Map(ids.map((id) => [id, paint])), faded: new Set(), holes: [], line };
}

function pieceLine(view: View, id: string): number | null {
  return view.pieces.find((piece) => piece.id === id)?.line ?? null;
}

/** The line of the connection between two pieces, in either order. */
export function connectionLine(view: View, [a, b]: [string, string]): number | null {
  const found = view.connections.find(
    (c) => (c.base === a && c.target === b) || (c.base === b && c.target === a),
  );
  return found?.line ?? null;
}

export function connectionsOf(view: View, id: string): ConnectionView[] {
  return view.connections.filter((c) => c.base === id || c.target === id);
}

export function forPiece(view: View, id: string): Highlight {
  return painted([id], "selected", pieceLine(view, id));
}

export function forProblem(view: View, problem: Problem): Highlight {
  switch (problem.kind) {
    case "conflict":
      return painted([...new Set([...problem.loop, ...problem.connection])], "problem",
        connectionLine(view, problem.connection));
    case "unconnected":
      return {
        paint: new Map(problem.groups.flatMap((group, i) => group.map((id): [string, Paint] => [id, { group: i }]))),
        faded: new Set(),
        holes: [],
        line: null,
      };
    case "fastener":
      return painted(problem.connection, "problem", connectionLine(view, problem.connection));
    case "hole_collision":
      return {
        paint: new Map(),
        faded: new Set([problem.piece]),
        holes: problem.holes.map((hole) => ({
          piece: problem.piece,
          center: hole.entry,
          direction: hole.direction,
          diameter: hole.diameter,
          depth: hole.depth,
          // Colliding bores show as plain cylinders
          countersink: null,
        })),
        line: connectionLine(view, problem.connection),
      };
    case "overlap":
      return painted(problem.pieces, "problem", pieceLine(view, problem.pieces[0]));
  }
}

/** The piece or connection written at a line of the source. */
export function atLine(view: View, line: number): { piece: string } | { connection: [string, string] } | null {
  const piece = view.pieces.find((p) => p.line === line);
  if (piece) return { piece: piece.id };
  const connection = view.connections.find((c) => c.line === line);
  return connection ? { connection: [connection.base, connection.target] } : null;
}
