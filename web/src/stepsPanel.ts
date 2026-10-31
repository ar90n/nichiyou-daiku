import { element, mm } from "./panels";
import { stepHeading } from "./steps";
import type { View } from "./types";

export interface StepsHandlers {
  onStep(step: number): void;
  onPart(part: number | null): void;
}

function table(head: string[], rows: string[][], onRow?: (row: number) => void, picked?: number | null): HTMLTableElement {
  const table = document.createElement("table");
  const top = document.createElement("tr");
  for (const title of head) top.append(element("th", title));
  table.append(top);
  rows.forEach((cells, i) => {
    const row = document.createElement("tr");
    for (const cell of cells) row.append(element("td", cell));
    if (onRow) {
      row.className = i === picked ? "pickable picked" : "pickable";
      row.addEventListener("click", () => onRow(i));
    }
    table.append(row);
  });
  return table;
}

function card(step: number, title: string, open: boolean, on: StepsHandlers): HTMLElement {
  const section = element("section", "", open ? "card open" : "card");
  section.dataset.step = String(step);
  const heading = element("h3", title);
  heading.addEventListener("click", () => on.onStep(step));
  section.append(heading);
  return section;
}

export function renderSteps(root: HTMLElement, view: View, step: number, part: number | null, on: StepsHandlers): void {
  root.replaceChildren();
  if (view.steps_hint) root.append(element("p", view.steps_hint, "notice"));
  const problems = view.problems.length;
  if (problems > 0) {
    const counted = problems === 1 ? "1 problem" : `${problems} problems`;
    root.append(element("p", `This design has ${counted} (see Model); the steps may be wrong`, "warning"));
  }
  const cards = element("div", "", "cards");
  const parts = card(0, "Parts", step === 0, on);
  if (step === 0) {
    const rows = view.parts.map((p) => [p.pieces.join(", "), p.type, mm(p.length), String(p.count)]);
    parts.append(table(["Pieces", "Lumber", "Length (mm)", "Count"], rows, (i) => on.onPart(i === part ? null : i), part));
  }
  cards.append(parts);
  for (const planned of view.steps) {
    const open = step === planned.number;
    const section = card(planned.number, stepHeading(planned), open, on);
    if (open) {
      const rows = planned.pieces.map((id) => {
        const piece = view.pieces.find((p) => p.id === id);
        return [id, piece?.type ?? "", piece ? mm(piece.length) : ""];
      });
      section.append(table(["Piece", "Lumber", "Length (mm)"], rows));
      if (planned.hardware.length > 0) {
        section.append(table(["Fastener", "Count"], planned.hardware.map((h) => [h.name, String(h.count)])));
      }
    }
    cards.append(section);
  }
  root.append(cards);
  const nav = element("div", "", "step-nav");
  const prev = element("button", "◀ Prev", "prev");
  prev.disabled = step <= 0;
  prev.addEventListener("click", () => on.onStep(step - 1));
  const next = element("button", "Next ▶", "next");
  next.disabled = step >= view.steps.length;
  next.addEventListener("click", () => on.onStep(step + 1));
  const total = view.steps.length;
  nav.append(prev, element("span", step === 0 ? `Parts / ${total}` : `${step} / ${total}`, "position"), next);
  root.append(nav);
}
