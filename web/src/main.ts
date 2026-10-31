import "./style.css";
import { atLine, forPiece, forProblem, NONE, type Highlight, type Paint } from "./highlight";
import { fetchSource, readFile, sourceUrl, takeFile, withSourceUrl, type Source } from "./load";
import { failedView, loadCore, safeView } from "./model";
import { markLine, renderHeader, renderPiece, renderProblems, renderSource } from "./panels";
import type { View } from "./types";
import { openViewer, VIEWS, type ViewName } from "./viewer";

const byId = <T extends HTMLElement>(id: string) => document.getElementById(id) as T;
const status = byId("status");
const sourceEl = byId("source");
const problemsEl = byId("problems");
const problemsTitle = byId("problems-title");
const pieceEl = byId("piece");
const viewer = openViewer(byId("scene"));
let current: View | null = null;

const core = loadCore();

function showLine(line: number): void {
  markLine(sourceEl, line);
}

function select(highlight: Highlight, piece: string | null): void {
  if (!current) return;
  viewer.apply(highlight);
  renderPiece(pieceEl, current, piece, showLine);
  markLine(sourceEl, highlight.line);
}

function selectLine(line: number): void {
  if (!current) return;
  const found = atLine(current, line);
  if (!found) {
    select(NONE, null);
    markLine(sourceEl, line);
  } else if ("piece" in found) {
    select(forPiece(current, found.piece), found.piece);
  } else {
    const paint = new Map<string, Paint>(found.connection.map((id) => [id, "selected"]));
    select({ ...NONE, paint, line }, null);
  }
}

function render(name: string | null, text: string, view: View): void {
  current = view;
  renderHeader(status, name, view);
  renderSource(sourceEl, text, selectLine);
  problemsTitle.textContent = view.problems.length ? `Problems (${view.problems.length})` : "Problems";
  renderProblems(problemsEl, view, (problem) => select(forProblem(view, problem), null));
  renderPiece(pieceEl, view, null, showLine);
  viewer.show(view.error ? null : view);
  if (view.error) markLine(sourceEl, view.error.line, true);
}

async function open(load: () => Promise<Source>, name: string | null): Promise<void> {
  let source: Source;
  try {
    source = await load();
  } catch (error) {
    render(name, "", failedView("file", error instanceof Error ? error.message : String(error)));
    return;
  }
  let viewOf;
  try {
    viewOf = await core;
  } catch (error) {
    const reason = error instanceof Error ? error.message : String(error);
    render(source.name, source.text, failedView("internal",
      `Could not load the core (WebAssembly): ${reason}. Use a browser with WebAssembly, or rebuild it (make wasm).`));
    return;
  }
  render(source.name, source.text, safeView(viewOf, source.text));
  // The address bar shares what is open: a file from this computer has no URL
  const page = source.url ? withSourceUrl(location.href, source.url) : withoutSource(location.href);
  history.replaceState(null, "", page);
}

function withoutSource(href: string): string {
  const page = new URL(href);
  page.searchParams.delete("src");
  return page.toString();
}

function openUrl(url: string): void {
  byId<HTMLInputElement>("url").value = url;
  void open(() => fetchSource(url), url);
}

function openFile(file: File): void {
  void open(() => readFile(file), file.name);
}

viewer.onPick = (id) => {
  if (!current) return;
  if (id === null) select(NONE, null);
  else select(forPiece(current, id), id);
};

const views = byId("views");
for (const name of Object.keys(VIEWS) as ViewName[]) {
  const button = document.createElement("button");
  button.textContent = name;
  button.addEventListener("click", () => viewer.setView(name));
  views.append(button);
}
byId<HTMLInputElement>("labels").addEventListener("change", (e) =>
  viewer.setLabels((e.target as HTMLInputElement).checked));

byId<HTMLFormElement>("url-form").addEventListener("submit", (e) => {
  e.preventDefault();
  const url = byId<HTMLInputElement>("url").value.trim();
  if (url) openUrl(url);
});
byId<HTMLInputElement>("file").addEventListener("change", (e) => {
  const file = takeFile(e.target as HTMLInputElement);
  if (file) openFile(file);
});
document.addEventListener("dragover", (e) => {
  e.preventDefault();
  document.body.classList.add("dragging");
});
document.addEventListener("dragleave", () => document.body.classList.remove("dragging"));
document.addEventListener("drop", (e) => {
  e.preventDefault();
  document.body.classList.remove("dragging");
  const file = e.dataTransfer?.files[0];
  if (file) openFile(file);
});

const initial = sourceUrl(location.search);
if (initial) openUrl(initial);
