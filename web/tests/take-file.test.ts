// @vitest-environment jsdom
import { expect, it } from "vitest";
import { takeFile } from "../src/load";

it("an emptied file input lets the same file, edited, be opened again", () => {
  const input = document.createElement("input");
  input.type = "file";
  const file = new File(["(a:2x4 =100)"], "a.nd");
  Object.defineProperty(input, "files", { value: [file] });
  let value = "C:\\fakepath\\a.nd";
  Object.defineProperty(input, "value", { get: () => value, set: (v: string) => (value = v) });
  expect(takeFile(input)).toBe(file);
  expect(input.value).toBe("");
});
