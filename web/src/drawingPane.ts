import { fitBox, panBy, zoomAt, type ViewBox } from "./drawing";
import type { DrawingAnswer } from "./model";

/** The part drawing in place of the 3D: zoom with the wheel or two fingers, drag to move. */
export class DrawingPane {
  private readonly page: HTMLElement;
  private readonly notes: HTMLElement | null;
  private svg: SVGSVGElement | null = null;
  private box: ViewBox | null = null;
  private size = { width: 1, height: 1 };
  private readonly pointers = new Map<number, { x: number; y: number }>();

  constructor(private readonly root: HTMLElement, onClose: () => void) {
    this.page = root.querySelector<HTMLElement>(".drawing-page")!;
    this.notes = root.querySelector<HTMLElement>(".drawing-notes");
    root.querySelector<HTMLButtonElement>(".close")!.addEventListener("click", onClose);
    root.querySelector<HTMLButtonElement>(".fit")!.addEventListener("click", () => this.fit());
    this.page.addEventListener("wheel", (e) => {
      e.preventDefault();
      const rect = this.page.getBoundingClientRect();
      this.zoom(e.deltaY < 0 ? 1.2 : 1 / 1.2, (e.clientX - rect.left) / Math.max(rect.width, 1), (e.clientY - rect.top) / Math.max(rect.height, 1));
    }, { passive: false });
    this.page.addEventListener("pointerdown", (e) => {
      // A drag moves the page; it must not select the drawing's text
      e.preventDefault();
      this.pointers.set(e.pointerId, { x: e.clientX, y: e.clientY });
      this.page.setPointerCapture?.(e.pointerId);
    });
    this.page.addEventListener("pointermove", (e) => this.move(e));
    const up = (e: PointerEvent) => this.pointers.delete(e.pointerId);
    this.page.addEventListener("pointerup", up);
    this.page.addEventListener("pointercancel", up);
    root.hidden = true;
  }

  show(answer: DrawingAnswer): void {
    this.page.replaceChildren();
    this.notes?.replaceChildren(...answer.notes.map((note) => {
      const line = document.createElement("span");
      line.textContent = note;
      return line;
    }));
    this.svg = null;
    this.root.hidden = false;
    if (!answer.svg) {
      const p = document.createElement("p");
      p.className = "drawing-error";
      p.textContent = answer.error ?? "No drawing";
      this.page.append(p);
      return;
    }
    // Parsed as SVG, never as HTML: the drawing carries the design's names
    const parsed = new DOMParser().parseFromString(answer.svg, "image/svg+xml");
    const svg = document.importNode(parsed.documentElement, true) as unknown as SVGSVGElement;
    svg.removeAttribute("width");
    svg.removeAttribute("height");
    this.page.append(svg);
    this.svg = svg;
    this.fit();
  }

  hide(): void {
    this.root.hidden = true;
    this.notes?.replaceChildren();
    this.page.replaceChildren();
    this.svg = null;
  }

  fit(): void {
    if (!this.svg) return;
    const [, , width, height] = (this.svg.getAttribute("data-page") ?? this.svg.getAttribute("viewBox") ?? "0 0 1 1").split(/\s+/).map(Number);
    this.svg.setAttribute("data-page", `0 0 ${width} ${height}`);
    this.size = { width: Math.max(this.page.clientWidth, 1), height: Math.max(this.page.clientHeight, 1) };
    this.box = fitBox({ width, height }, this.size);
    this.apply();
  }

  private zoom(factor: number, x: number, y: number): void {
    if (!this.box) return;
    this.box = zoomAt(this.box, factor, { x, y });
    this.apply();
  }

  private move(e: PointerEvent): void {
    const last = this.pointers.get(e.pointerId);
    if (!last || !this.box) return;
    if (this.pointers.size === 1) {
      this.box = panBy(this.box, e.clientX - last.x, e.clientY - last.y, this.size);
      this.apply();
    } else if (this.pointers.size === 2) {
      const other = [...this.pointers.entries()].find(([id]) => id !== e.pointerId)![1];
      const before = Math.hypot(last.x - other.x, last.y - other.y);
      const after = Math.hypot(e.clientX - other.x, e.clientY - other.y);
      if (before > 0) {
        const rect = this.page.getBoundingClientRect();
        this.zoom(after / before, ((e.clientX + other.x) / 2 - rect.left) / Math.max(rect.width, 1), ((e.clientY + other.y) / 2 - rect.top) / Math.max(rect.height, 1));
      }
    }
    this.pointers.set(e.pointerId, { x: e.clientX, y: e.clientY });
  }

  private apply(): void {
    if (!this.svg || !this.box) return;
    const { x, y, width, height } = this.box;
    this.svg.setAttribute("viewBox", `${x} ${y} ${width} ${height}`);
  }
}
