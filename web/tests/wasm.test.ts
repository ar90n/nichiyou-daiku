import { readFileSync } from "node:fs";
import { expect, it } from "vitest";
import { initSync, part_drawing, view } from "../src/wasm/nichiyou_daiku_wasm.js";
import { parseView } from "../src/model";

initSync({ module: readFileSync(new URL("../src/wasm/nichiyou_daiku_wasm_bg.wasm", import.meta.url)) });

it("the built WebAssembly views an example", () => {
  const source = readFileSync(new URL("../../examples/nd_files/simple_table_unknowns.nd", import.meta.url), "utf8");
  const result = parseView(view(source));
  expect(result.valid).toBe(true);
  expect(result.pieces).toHaveLength(16);
  expect(result.connections.length).toBeGreaterThan(0);
  expect(result.steps.length).toBeGreaterThan(0);
});

it("the built WebAssembly draws a part", () => {
  const shelf = "(left_side:2x4 =800)\n(right_side:2x4 =800)\n(shelf:2x4 =600)\n" +
    "left_side -[BL<300 DL<0 D(:8x30)]- shelf\nright_side -[FL<300 TL<0 D(:8x30)]- shelf\n";
  const answer = JSON.parse(part_drawing(shelf, 0));
  expect(answer.svg.startsWith("<svg")).toBe(true);
});
