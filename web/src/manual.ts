import { importSvg } from "./drawingPane";
import type { DrawingAnswer } from "./model";
import { element, formatSize, mm } from "./panels";
import { stepHeading } from "./steps";
import type { HardwareView, StepView, View } from "./types";

/** The drawings the manual shows: a part's (its number in the parts list) and a step's (from 1). */
export interface Drawings {
  part(index: number): DrawingAnswer;
  step(number: number): DrawingAnswer;
}

/** Every fastener the steps use, summed by name in the order they first come. */
export function fastenerTotals(steps: StepView[]): HardwareView[] {
  const totals = new Map<string, number>();
  for (const step of steps) {
    for (const h of step.hardware) totals.set(h.name, (totals.get(h.name) ?? 0) + h.count);
  }
  return [...totals].map(([name, count]) => ({ name, count }));
}

/** The manual's title from the file's name, as the CLI's steps.md takes it. */
export function manualTitle(name: string | null): string {
  const stem = name?.split("/").pop()?.replace(/\.nd$/, "");
  return stem ? `${stem}: assembly manual` : "Assembly manual";
}

function table(head: string[], rows: string[][], className: string): HTMLTableElement {
  const table = element("table", "", className);
  const top = document.createElement("tr");
  for (const title of head) top.append(element("th", title));
  table.append(top);
  for (const cells of rows) {
    const row = document.createElement("tr");
    for (const cell of cells) row.append(element("td", cell));
    table.append(row);
  }
  return table;
}

function figure(answer: DrawingAnswer, caption: string | null, className: string): HTMLElement {
  const box = element("figure", "", className);
  if (caption) box.append(element("figcaption", caption));
  box.append(answer.svg ? importSvg(answer.svg) : element("p", answer.error ?? "No drawing", "error"));
  // On paper too: the reader has to know which values are missing
  if (answer.notes.length > 0) {
    const notes = element("ul", "", "notes");
    for (const note of answer.notes) notes.append(element("li", note));
    box.append(notes);
  }
  return box;
}

/** The whole manual as pages: what to get, the drilled parts' drawings, then a page per step. */
export function renderManual(root: HTMLElement, view: View, name: string | null, draw: Drawings): void {
  const cover = element("section", "", "sheet cover");
  cover.append(element("h1", manualTitle(name)));
  if (view.overall_size) cover.append(element("p", `Overall size ${formatSize(view.overall_size)}`, "size"));
  // Pages have no numbers when printed from HTML: a drilled part's number
  // ties its row to its drawing
  const numbers = new Map<number, number>();
  view.parts.forEach((p, i) => {
    if (p.drilled) numbers.set(i, numbers.size + 1);
  });
  const parts = view.parts.map((p, i) => {
    const number = numbers.get(i);
    return [number ? `Part ${number}` : "", p.pieces.join(", "), p.type, mm(p.length), String(p.count)];
  });
  cover.append(element("h2", "Parts"), table(["Drawing", "Pieces", "Lumber", "Length (mm)", "Count"], parts, "parts"));
  const fasteners = fastenerTotals(view.steps);
  if (fasteners.length > 0) {
    cover.append(element("h2", "Fasteners"), table(["Fastener", "Count"], fasteners.map((f) => [f.name, String(f.count)]), "fasteners"));
  }
  if (view.problems.length > 0) {
    const list = element("ul", "", "problems");
    for (const problem of view.problems) list.append(element("li", problem.message));
    cover.append(element("h2", "Problems"), list);
  }
  const sheets: HTMLElement[] = [cover];
  if (numbers.size > 0) {
    const drawings = element("section", "", "sheet part-drawings");
    for (const [index, number] of numbers) drawings.append(figure(draw.part(index), `Part ${number}`, "part"));
    sheets.push(drawings);
  }
  for (const planned of view.steps) {
    const sheet = element("section", "", "sheet step");
    sheet.dataset.step = String(planned.number);
    const answer = draw.step(planned.number);
    // The heading is drawn in the step's drawing; without one, the page keeps it
    if (!answer.svg) sheet.append(element("h2", stepHeading(planned)));
    sheet.append(figure(answer, null, "step"));
    const tables = element("div", "", "step-tables");
    const pieces = planned.pieces.map((id) => {
      const piece = view.pieces.find((p) => p.id === id);
      return [id, piece?.type ?? "", piece ? mm(piece.length) : ""];
    });
    tables.append(table(["Piece", "Lumber", "Length (mm)"], pieces, "pieces"));
    if (planned.hardware.length > 0) {
      tables.append(table(["Fastener", "Count"], planned.hardware.map((h) => [h.name, String(h.count)]), "fasteners"));
    }
    sheet.append(tables);
    sheets.push(sheet);
  }
  root.replaceChildren(...sheets);
}
