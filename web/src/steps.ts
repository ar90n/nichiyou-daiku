import type { Highlight, Paint } from "./highlight";
import type { StepView, Vec3, View } from "./types";

export interface Box {
  min: Vec3;
  max: Vec3;
}

/** What the 3D shows at a step of the Steps tab; step 0 is the parts list. */
export interface StepScene {
  /** The pieces drawn; null draws them all */
  visible: Set<string> | null;
  /** Pieces from earlier steps, in grey */
  earlier: Set<string>;
  /** This step's pieces, or a picked part's, in blue */
  current: Set<string>;
  /** What the camera fits; null fits the whole model */
  bounds: Box | null;
}

export function clampStep(view: View, step: number): number {
  if (!Number.isFinite(step)) return 0;
  return Math.min(Math.max(Math.round(step), 0), view.steps.length);
}

export function boundsOf(view: View, ids: Iterable<string>): Box | null {
  const wanted = new Set(ids);
  const pieces = view.pieces.filter((piece) => wanted.has(piece.id));
  if (pieces.length === 0) return null;
  const min = [0, 1, 2].map((i) => Math.min(...pieces.map((p) => p.min[i]))) as Vec3;
  const max = [0, 1, 2].map((i) => Math.max(...pieces.map((p) => p.max[i]))) as Vec3;
  return { min, max };
}

const WHOLE: StepScene = { visible: null, earlier: new Set(), current: new Set(), bounds: null };

export function stepScene(view: View, step: number): StepScene {
  const planned = view.steps[step - 1];
  if (!planned) return { ...WHOLE, earlier: new Set(), current: new Set() };
  const current = new Set(planned.pieces);
  return {
    visible: new Set(planned.shown),
    earlier: new Set(planned.shown.filter((id) => !current.has(id))),
    current,
    bounds: boundsOf(view, planned.shown),
  };
}

export function partScene(view: View, part: number | null): StepScene {
  const pieces = part === null ? [] : (view.parts[part]?.pieces ?? []);
  return { visible: null, earlier: new Set(), current: new Set(pieces), bounds: null };
}

export function stepHighlight(scene: StepScene): Highlight {
  const paint = new Map<string, Paint>();
  for (const id of scene.earlier) paint.set(id, "earlier");
  for (const id of scene.current) paint.set(id, "selected");
  return { paint, faded: new Set(), holes: [], line: null };
}

const KIND_MARKS: Partial<Record<StepView["kind"], string>> = {
  "sub-assembly": " (sub-assembly)",
  join: " (join)",
};

/** As the CLI's steps.md heads a step. */
export function stepHeading(step: StepView): string {
  return `Step ${step.number}${step.name ? ` - ${step.name}` : ""}${KIND_MARKS[step.kind] ?? ""}`;
}

export function stepsTab(view: View | null): { enabled: boolean; reason: string | null } {
  if (!view) return { enabled: false, reason: "Open an .nd first" };
  if (view.error) return { enabled: false, reason: "Fix the error first: the steps need a design that reads" };
  if (view.pieces.length === 0) return { enabled: false, reason: "Nothing to assemble: the design has no pieces" };
  return { enabled: true, reason: null };
}

/** The step in the page's ?step=: a whole number, else none. */
export function stepFromSearch(search: string): number | null {
  const text = new URLSearchParams(search).get("step");
  return text !== null && /^\d+$/.test(text) ? Number(text) : null;
}

export function withStep(href: string, step: number | null): string {
  const page = new URL(href);
  if (step === null) page.searchParams.delete("step");
  else page.searchParams.set("step", String(step));
  return page.toString();
}

/** Which way an arrow key steps; none while typing in a text field. */
export function stepKey(key: string, tag: string | undefined): -1 | 0 | 1 {
  if (tag === "INPUT" || tag === "TEXTAREA") return 0;
  return key === "ArrowLeft" ? -1 : key === "ArrowRight" ? 1 : 0;
}
