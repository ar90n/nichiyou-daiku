import type { Box } from "./steps";
import type { StepView, Vec3 } from "./types";

export type LabelKind = "overall" | "normal" | "lumber";

export interface DimensionLabel {
  text: string;
  position: Vec3;
  kind: LabelKind;
}

/** What the 3D draws for a step's dimensions: line segments and values. */
export interface DimensionLayout {
  lines: [Vec3, Vec3][];
  labels: DimensionLabel[];
}

export interface LabelRect {
  left: number;
  top: number;
  right: number;
  bottom: number;
}

const AXES = { x: 0, y: 1, z: 2 } as const;

/** As the CLI writes lengths: 0.1mm steps without ".0", two significant digits below. */
export function formatMm(value: number): string {
  if (Math.abs(value) >= 0.1) return String(Number(value.toFixed(1)));
  return String(Number(value.toPrecision(2)));
}

export function dimensionGap(bounds: Box): number {
  const longest = Math.max(...[0, 1, 2].map((i) => bounds.max[i] - bounds.min[i]));
  return Math.max(20, longest * 0.08);
}

function cross(a: Vec3, b: Vec3): Vec3 {
  return [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]];
}

/** The CLI's dimension view: from the step's axis and side, with z up, or -y up along z. */
function frame(view: StepView["view"]): { axis: number; toward: Vec3; up: Vec3; right: Vec3 } {
  const axis = AXES[view.axis];
  const toward: Vec3 = [0, 0, 0];
  toward[axis] = view.side;
  const up: Vec3 = axis === 2 ? [0, -1, 0] : [0, 0, 1];
  return { axis, toward, up, right: cross(up, toward) };
}

export function dimensionDirection(view: StepView["view"]): Vec3 {
  if (view.axis === "z") return [0, view.side * 1e-4, view.side];
  return frame(view).toward;
}

export function layoutDimensions(step: StepView, bounds: Box): DimensionLayout {
  const { axis: v, toward, up, right } = frame(step.view);
  const gap = dimensionGap(bounds);
  const lines: [Vec3, Vec3][] = [];
  const labels: DimensionLabel[] = [];
  for (const chain of step.dimensions) {
    const a = AXES[chain.axis];
    const w = 3 - v - a;
    const out = chain.side === "below" ? up.map((x) => -x) : right.map((x) => -x);
    const sign = out[w] > 0 ? 1 : -1;
    const near = toward[v] > 0 ? bounds.max[v] : bounds.min[v];
    const base = sign > 0 ? bounds.max[w] : bounds.min[w];
    const point = (along: number, across: number): Vec3 => {
      const p: Vec3 = [0, 0, 0];
      p[a] = along;
      p[w] = across;
      p[v] = near;
      return p;
    };
    const stops = chain.stops;
    const first = stops[0];
    const last = stops[stops.length - 1];
    const hasSegments = chain.segments.length > 0;
    const seg = base + sign * gap;
    const all = base + sign * gap * (hasSegments ? 2 : 1);
    const t = 0.15 * gap;
    const tick = (s: number, level: number): [Vec3, Vec3] => [point(s - t, level - t), point(s + t, level + t)];
    if (hasSegments) lines.push([point(first, seg), point(last, seg)]);
    lines.push([point(first, all), point(last, all)]);
    stops.forEach((s, i) => {
      const end = i === 0 || i === stops.length - 1;
      lines.push([point(s, base), point(s, (end ? all : seg) + sign * 0.2 * gap)]);
    });
    if (hasSegments) for (const s of stops) lines.push(tick(s, seg));
    lines.push(tick(first, all), tick(last, all));
    for (const s of chain.segments) {
      labels.push({
        text: formatMm(s.end - s.start),
        position: point((s.start + s.end) / 2, seg + sign * 0.35 * gap),
        kind: s.lumber ? "lumber" : "normal",
      });
    }
    labels.push({ text: formatMm(last - first), position: point((first + last) / 2, all + sign * 0.35 * gap), kind: "overall" });
  }
  return { lines, labels };
}

const PRIORITY: Record<LabelKind, number> = { overall: 0, normal: 1, lumber: 2 };

export function labelOrder(labels: DimensionLabel[]): number[] {
  return labels.map((_, i) => i).sort((i, j) => PRIORITY[labels[i].kind] - PRIORITY[labels[j].kind] || i - j);
}

function overlaps(a: LabelRect, b: LabelRect): boolean {
  return a.left < b.right && b.left < a.right && a.top < b.bottom && b.top < a.bottom;
}

/** Which values to show: in order, each that overlaps none shown before it. */
export function visibleLabels(rects: LabelRect[], order: number[]): boolean[] {
  const shown: LabelRect[] = [];
  const visible = rects.map(() => true);
  for (const i of order) {
    const rect = rects[i];
    // No size: off screen or behind the camera, where it covers nothing
    if (rect.right <= rect.left || rect.bottom <= rect.top) continue;
    if (shown.some((other) => overlaps(rect, other))) visible[i] = false;
    else shown.push(rect);
  }
  return visible;
}
