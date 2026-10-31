import { readFileSync } from "node:fs";
import { expect, it } from "vitest";
import { initSync, view } from "../src/wasm/nichiyou_daiku_wasm.js";
import { parseView } from "../src/model";

initSync({ module: readFileSync(new URL("../src/wasm/nichiyou_daiku_wasm_bg.wasm", import.meta.url)) });

it("the built WebAssembly views an example", () => {
  const source = readFileSync(new URL("../../examples/nd_files/simple_table_unknowns.nd", import.meta.url), "utf8");
  const result = parseView(view(source));
  expect(result.valid).toBe(true);
  expect(result.pieces).toHaveLength(16);
  expect(result.connections.length).toBeGreaterThan(0);
});
