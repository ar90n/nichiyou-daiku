// @vitest-environment jsdom
import { describe, expect, it, vi } from "vitest";
import { describeConnection, formatSize, markLine, renderHeader, renderPiece, renderProblems, renderSource } from "../src/panels";
import type { PieceView, View } from "../src/types";

const v = (over: Partial<View> = {}): View => ({ valid: true, error: null, overall_size: [530, 440, 659.99999],
  size_reference: "a", pieces: [{ id: "a", type: "2x4", length: 659, line: 3 } as PieceView], problems: [],
  connections: [{ base: "a", target: "b", kind: "dowel", diameter: 8, length: 30, screw_type: null, line: 9 }],
  holes: [], ...over });

it("sizes read as millimetres", () => {
  expect(formatSize([530, 440, 659.99999])).toBe("530×440×660mm");
  expect(describeConnection({ base: "a", target: "b", kind: "screw", diameter: 3.8, length: 65, screw_type: "slim", line: 1 })).toBe("screw 3.8×65 (slim)");
  expect(describeConnection(v().connections[0])).toBe("dowel 8×30");
});

it("the header names the file, its size and its problems", () => {
  const el = document.createElement("header");
  renderHeader(el, "wagon.nd", v());
  expect(el.textContent).toContain("wagon.nd");
  expect(el.textContent).toContain("530×440×660mm");
  expect(el.textContent).toContain("No problems");
});

describe("problems", () => {
  it("list an error first", () => {
    const el = document.createElement("ul");
    renderProblems(el, v({ error: { kind: "syntax", message: "Syntax error at line 1, column 9: …", line: 1, column: 9 }, pieces: [] }), () => {});
    expect(el.querySelector("li.error")?.textContent).toContain("Syntax error at line 1");
  });

  it("say when there are none", () => {
    const el = document.createElement("ul");
    renderProblems(el, v(), () => {});
    expect(el.querySelector("li.none")?.textContent).toBe("No problems");
  });

  it("pick a problem", () => {
    const el = document.createElement("ul");
    const onPick = vi.fn();
    renderProblems(el, v({ problems: [{ kind: "overlap", message: "Pieces 'a' and 'b' overlap", pieces: ["a", "b"], volume_mm3: 1 }] }), onPick);
    (el.querySelector("li") as HTMLElement).click();
    expect(onPick).toHaveBeenCalledOnce();
  });
});

it("a piece's connections lead to their lines", () => {
  const el = document.createElement("div");
  const onLine = vi.fn();
  renderPiece(el, v(), "a", onLine);
  expect(el.textContent).toContain("2x4");
  (el.querySelector("li") as HTMLElement).click();
  expect(onLine).toHaveBeenCalledWith(9);
});

it("an unnamed piece without connections still shows", () => {
  const el = document.createElement("div");
  const id = "00000000-0000-4000-8000-000000000001";
  renderPiece(el, v({ pieces: [{ id, type: "1x4", length: 300, line: 1 } as PieceView], connections: [] }), id, () => {});
  expect(el.textContent).toContain(id);
  expect(el.querySelectorAll("li")).toHaveLength(0);
});

it("the source is text, numbered, and marks a line", () => {
  const el = document.createElement("pre");
  const onLine = vi.fn();
  renderSource(el, "(a:2x4 =100)\n<b>not html</b>", onLine);
  expect(el.querySelectorAll("div.line")).toHaveLength(2);
  expect(el.querySelector("b")).toBeNull();
  markLine(el, 2, true);
  expect(el.querySelector('div.line[data-line="2"]')?.className).toBe("line current error");
  (el.querySelector('div.line[data-line="1"]') as HTMLElement).click();
  expect(onLine).toHaveBeenCalledWith(1);
});
