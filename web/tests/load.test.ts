import { describe, expect, it } from "vitest";
import { fetchSource, nameOf, readFile, sourceUrl, withSourceUrl } from "../src/load";

describe("the page's URL", () => {
  it("names the .nd to open", () => {
    expect(sourceUrl("?src=https%3A%2F%2Fexample.com%2Fa.nd")).toBe("https://example.com/a.nd");
    expect(sourceUrl("")).toBeNull();
  });

  it("points at an .nd to share", () => {
    expect(withSourceUrl("https://ar90n.github.io/nichiyou-daiku/?x=1#v", "https://e.com/w.nd"))
      .toBe("https://ar90n.github.io/nichiyou-daiku/?x=1&src=https%3A%2F%2Fe.com%2Fw.nd#v");
  });

  it("names a file by its URL", () => {
    expect(nameOf("https://raw.githubusercontent.com/u/r/main/file%20wagon.nd?token=1")).toBe("file wagon.nd");
  });

  it("names a file by a URL relative to the page", () => {
    expect(nameOf("examples/table.nd")).toBe("table.nd");
  });
});

describe("fetchSource", () => {
  it("reads the text", async () => {
    const ok = async () => new Response("(a:2x4 =100)", { status: 200 });
    expect(await fetchSource("https://e.com/a.nd", ok)).toEqual({ name: "a.nd", text: "(a:2x4 =100)", url: "https://e.com/a.nd" });
  });

  it("says what the server answered", async () => {
    const missing = async () => new Response("", { status: 404, statusText: "Not Found" });
    await expect(fetchSource("https://e.com/a.nd", missing)).rejects.toThrow("the server answered 404 Not Found. Check the URL.");
  });

  it("points at the raw file when another site cannot read it", async () => {
    const blocked = async (): Promise<Response> => { throw new TypeError("Failed to fetch"); };
    await expect(fetchSource("https://github.com/u/r/blob/main/a.nd", blocked)).rejects.toThrow(/Use the raw file/);
  });
});

it("reads a file", async () => {
  const file = Object.assign(new Blob(["(a:2x4 =100)"]), { name: "a.nd" });
  expect(await readFile(file)).toEqual({ name: "a.nd", text: "(a:2x4 =100)", url: null });
});
