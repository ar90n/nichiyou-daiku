import "./style.css";
import { dimensionDirection, layoutDimensions } from "./dimensions";
import { atLine, forPiece, forProblem, NONE, type Highlight, type Paint } from "./highlight";
import { fetchSource, readFile, sourceUrl, takeFile, withSourceUrl, type Source } from "./load";
import { failedView, loadCore, safeView } from "./model";
import { markLine, renderHeader, renderPiece, renderProblems, renderSource } from "./panels";
import {
  clampStep, partScene, stepFromSearch, stepHighlight, stepKey, stepScene, stepsTab, withStep,
} from "./steps";
import { renderSteps, renderUnavailable } from "./stepsPanel";
import type { View } from "./types";
import { openViewer, VIEWS, type ViewName } from "./viewer";

const byId = <T extends HTMLElement>(id: string) => document.getElementById(id) as T;
const status = byId("status");
const sourceEl = byId("source");
const problemsEl = byId("problems");
const problemsTitle = byId("problems-title");
const pieceEl = byId("piece");
const stepsEl = byId("steps");
const modelTab = byId<HTMLButtonElement>("tab-model");
const stepsTabButton = byId<HTMLButtonElement>("tab-steps");
const viewer = openViewer(byId("scene"));
let current: View | null = null;
let tab: "model" | "steps" = "model";
// The Steps tab's step (0: the parts list); null on the Model tab, or when
// the Steps tab only says why it cannot show the steps
let step: number | null = null;
let part: number | null = null;
let dims = true;

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
  const state = stepsTab(view);
  stepsTabButton.classList.toggle("unavailable", !state.enabled);
  stepsTabButton.title = state.reason ?? "";
}

function setTab(next: "model" | "steps"): void {
  tab = next;
  document.body.classList.toggle("steps-mode", next === "steps");
  modelTab.classList.toggle("active", next === "model");
  stepsTabButton.classList.toggle("active", next === "steps");
}

/** The current step's dimensions, when the Steps tab shows a step and they are on. */
function drawDimensions(): void {
  const planned = current && step ? current.steps[step - 1] : undefined;
  const bounds = planned && current ? stepScene(current, step!).bounds : null;
  viewer.showDimensions(planned && bounds && dims ? layoutDimensions(planned, bounds) : null);
  document.body.classList.toggle("on-step", planned !== undefined);
}

function openStepsTab(wanted: number): void {
  const state = stepsTab(current);
  if (state.enabled) {
    showStep(wanted);
    return;
  }
  step = null;
  part = null;
  renderUnavailable(stepsEl, state.reason ?? "");
  viewer.showDimensions(null);
  document.body.classList.remove("on-step");
  setTab("steps");
}

function showStep(next: number, picked: number | null = null): void {
  if (!current || !stepsTab(current).enabled) return;
  step = clampStep(current, next);
  part = step === 0 ? picked : null;
  const scene = step === 0 ? partScene(current, part) : stepScene(current, step);
  viewer.showOnly(scene.visible);
  viewer.apply(stepHighlight(scene));
  // Drawn first, so that the camera frames the dimension rows too
  drawDimensions();
  viewer.fit(scene.bounds);
  renderSteps(stepsEl, current, step, part, { onStep: (n) => showStep(n), onPart: (i) => showStep(0, i) });
  setTab("steps");
  history.replaceState(null, "", withStep(location.href, step));
}

function showModel(): void {
  step = null;
  part = null;
  viewer.showOnly(null);
  viewer.apply(NONE);
  viewer.showDimensions(null);
  document.body.classList.remove("on-step");
  viewer.fit(null);
  setTab("model");
  history.replaceState(null, "", withStep(location.href, null));
}

async function open(load: () => Promise<Source>, name: string | null, wanted: number | null = step): Promise<void> {
  let source: Source;
  try {
    source = await load();
  } catch (error) {
    render(name, "", failedView("file", error instanceof Error ? error.message : String(error)));
    if (tab === "steps") showModel();
    return;
  }
  let viewOf;
  try {
    viewOf = await core;
  } catch (error) {
    const reason = error instanceof Error ? error.message : String(error);
    render(source.name, source.text, failedView("internal",
      `Could not load the core (WebAssembly): ${reason}. Use a browser with WebAssembly, or rebuild it (make wasm).`));
    if (tab === "steps") showModel();
    return;
  }
  render(source.name, source.text, safeView(viewOf, source.text));
  // The address bar shares what is open: a file from this computer has no URL
  const page = source.url ? withSourceUrl(location.href, source.url) : withoutSource(location.href);
  history.replaceState(null, "", page);
  // Reopened, a file keeps its step; one with fewer steps goes to its last
  if ((wanted !== null || tab === "steps") && stepsTab(current).enabled) showStep(wanted ?? 0);
  else if (tab === "steps") showModel();
}

function withoutSource(href: string): string {
  const page = new URL(href);
  page.searchParams.delete("src");
  return page.toString();
}

function openUrl(url: string, wanted: number | null = step): void {
  byId<HTMLInputElement>("url").value = url;
  void open(() => fetchSource(url), url, wanted);
}

function openFile(file: File): void {
  void open(() => readFile(file), file.name);
}

viewer.onPick = (id) => {
  if (!current || step !== null) return; // The Steps tab only shows
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
const dimensionView = document.createElement("button");
dimensionView.textContent = "Dimensions";
dimensionView.className = "steps-only";
dimensionView.title = "Look from where the step's dimensions read best";
dimensionView.addEventListener("click", () => {
  if (current && step) viewer.lookAlong(dimensionDirection(current.steps[step - 1].view));
});
views.append(dimensionView);
byId<HTMLInputElement>("dims").addEventListener("change", (e) => {
  dims = (e.target as HTMLInputElement).checked;
  drawDimensions();
});
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

modelTab.addEventListener("click", () => showModel());
stepsTabButton.addEventListener("click", () => openStepsTab(step ?? 0));
document.addEventListener("keydown", (e) => {
  if (step === null) return;
  const move = stepKey(e.key, (e.target as HTMLElement | null)?.tagName);
  if (move !== 0) {
    e.preventDefault();
    showStep(step + move);
  }
});

const initial = sourceUrl(location.search);
if (initial) openUrl(initial, stepFromSearch(location.search));
