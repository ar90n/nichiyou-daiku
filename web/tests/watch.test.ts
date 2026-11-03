import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { placeToKeep, watching, watchSource } from "../src/watch";

beforeEach(() => vi.useFakeTimers());
afterEach(() => vi.useRealTimers());

/** A server whose file reads `text`, or fails while it is null. */
function server(state: { text: string | null }): typeof fetch {
  return (async () => {
    if (state.text === null) return new Response("gone", { status: 404 });
    return new Response(state.text, { status: 200 });
  }) as typeof fetch;
}

it("follows the source only when view asks to", () => {
  expect(watching("?src=a.nd&watch")).toBe(true);
  expect(watching("?src=a.nd")).toBe(false);
});

it("reopens only when the file has changed", async () => {
  const state = { text: "(a:2x4 =100)" as string | null };
  let shown = "(a:2x4 =100)";
  const changes: string[] = [];
  const stop = watchSource("a.nd", () => shown, (text) => { changes.push(text); shown = text; }, 1000, server(state));
  await vi.advanceTimersByTimeAsync(3000);
  expect(changes).toEqual([]);
  state.text = "(a:2x4 =200)";
  await vi.advanceTimersByTimeAsync(1000);
  expect(changes).toEqual(["(a:2x4 =200)"]);
  await vi.advanceTimersByTimeAsync(3000);
  expect(changes).toEqual(["(a:2x4 =200)"]);
  stop();
});

it("a failed read keeps what is shown", async () => {
  const state = { text: null as string | null };
  const changes: string[] = [];
  const stop = watchSource("a.nd", () => "(a:2x4 =100)", (text) => changes.push(text), 1000, server(state));
  await vi.advanceTimersByTimeAsync(3000);
  expect(changes).toEqual([]);
  stop();
});

it("reads without the browser's cache", async () => {
  const seen: RequestInit[] = [];
  const fetchFn = (async (_url: string, init: RequestInit) => {
    seen.push(init);
    return new Response("x", { status: 200 });
  }) as unknown as typeof fetch;
  const stop = watchSource("a.nd", () => "x", () => {}, 1000, fetchFn);
  await vi.advanceTimersByTimeAsync(1000);
  expect(seen[0]?.cache).toBe("no-store");
  stop();
});

it("a save keeps the step and part being looked at", () => {
  expect(placeToKeep("steps", 3, null, null)).toEqual({ step: 3, part: null });
  expect(placeToKeep("steps", 0, 2, null)).toEqual({ step: 0, part: 2 });
  expect(placeToKeep("model", null, null, null)).toBeNull();
});

it("steps a slip mid-edit took away come back with the next good save", () => {
  // The model tab shows a file whose steps cannot be planned; the step it
  // left waits for the steps to come back
  expect(placeToKeep("model", null, null, { step: 3, part: null })).toEqual({ step: 3, part: null });
});
