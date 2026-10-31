import { connectionsOf } from "./highlight";
import type { ConnectionView, Problem, Vec3, View } from "./types";

/** Millimetres with one decimal at most: 659.99999 reads 660. */
export function mm(value: number): string {
  return String(Number(value.toFixed(1)));
}

export function formatSize(size: Vec3): string {
  return `${size.map(mm).join("×")}mm`;
}

export function describeConnection(c: ConnectionView): string {
  if (c.kind === "vanilla" || c.diameter === null || c.length === null) return c.kind;
  const size = `${c.kind} ${mm(c.diameter)}×${mm(c.length)}`;
  return c.screw_type ? `${size} (${c.screw_type})` : size;
}

export function element<K extends keyof HTMLElementTagNameMap>(
  tag: K,
  text: string,
  className?: string,
): HTMLElementTagNameMap[K] {
  const el = document.createElement(tag);
  el.textContent = text;
  if (className) el.className = className;
  return el;
}

function count(n: number): string {
  return n === 1 ? "1 problem" : `${n} problems`;
}

export function renderHeader(el: HTMLElement, name: string | null, view: View | null): void {
  el.replaceChildren();
  if (name) el.append(element("span", name, "name"));
  if (!view) return;
  if (view.overall_size) el.append(element("span", formatSize(view.overall_size), "size"));
  if (view.error) el.append(element("span", "Error", "status error"));
  else if (view.problems.length === 0) el.append(element("span", "No problems", "status ok"));
  else el.append(element("span", `⚠ ${count(view.problems.length)}`, "status problem"));
}

export function renderProblems(el: HTMLElement, view: View, onPick: (problem: Problem) => void): void {
  el.replaceChildren();
  if (view.error) {
    el.append(element("li", `${view.error.kind}: ${view.error.message}`, "error"));
    return;
  }
  if (view.problems.length === 0) {
    el.append(element("li", "No problems", "none"));
    return;
  }
  for (const problem of view.problems) {
    const li = element("li", problem.message, `problem ${problem.kind}`);
    li.addEventListener("click", () => onPick(problem));
    el.append(li);
  }
}

export function renderPiece(el: HTMLElement, view: View, id: string | null, onLine: (line: number) => void): void {
  el.replaceChildren();
  const piece = id === null ? undefined : view.pieces.find((p) => p.id === id);
  if (!piece) {
    el.append(element("p", "Click a piece to see it", "hint"));
    return;
  }
  const title = element("p", "", "piece");
  const line = element("button", `line ${piece.line}`, "line-link");
  line.addEventListener("click", () => onLine(piece.line));
  title.append(element("strong", piece.id), ` ${piece.type} ${mm(piece.length)}mm `, line);
  el.append(title);
  const connections = connectionsOf(view, piece.id);
  if (connections.length === 0) return;
  const list = document.createElement("ul");
  for (const c of connections) {
    const other = c.base === piece.id ? c.target : c.base;
    const li = element("li", `${other} (${describeConnection(c)}) line ${c.line}`, "connection");
    li.addEventListener("click", () => onLine(c.line));
    list.append(li);
  }
  el.append(list);
}

export function renderSource(el: HTMLElement, source: string, onLine: (line: number) => void): void {
  el.replaceChildren();
  source.split("\n").forEach((text, i) => {
    const row = element("div", "", "line");
    row.dataset.line = String(i + 1);
    row.append(element("span", String(i + 1), "no"), element("code", text));
    row.addEventListener("click", () => onLine(i + 1));
    el.append(row);
  });
}

/** Mark one line of the source (an error's in red) and scroll to it. */
export function markLine(el: HTMLElement, line: number | null, error = false): void {
  for (const row of el.querySelectorAll<HTMLElement>("div.line.current")) row.className = "line";
  if (line === null) return;
  const row = el.querySelector<HTMLElement>(`div.line[data-line="${line}"]`);
  if (!row) return;
  row.className = error ? "line current error" : "line current";
  row.scrollIntoView?.({ block: "nearest" });
}
