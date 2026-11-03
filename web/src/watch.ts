/** Following a source as it is saved: `view` serves the page with &watch. */

export function watching(search: string): boolean {
  return new URLSearchParams(search).has("watch");
}

/**
 * Reads `url` every `interval` ms and calls `changed` with its text when it
 * differs from what is shown. A failed read changes nothing: the file may be
 * mid-save or gone for a moment. Returns a function that stops it.
 */
export function watchSource(
  url: string,
  shown: () => string | null,
  changed: (text: string) => void,
  interval = 1000,
  fetchFn: typeof fetch = fetch,
): () => void {
  let busy = false;
  let last: string | null = null;
  const timer = setInterval(async () => {
    if (busy) return;
    busy = true;
    try {
      const response = await fetchFn(url, { cache: "no-store" });
      if (!response.ok) return;
      const text = await response.text();
      // `last` keeps a slow reopen from being asked twice
      if (text !== shown() && text !== last) {
        last = text;
        changed(text);
      }
    } catch {
      // Unreachable for now: the next read tries again
    } finally {
      busy = false;
    }
  }, interval);
  return () => clearInterval(timer);
}

/** A place in the Steps tab: the step, or the part of step 0. */
export interface StepsPlace {
  step: number;
  part: number | null;
}

/**
 * Where a followed save should reopen in the Steps tab: where the user is,
 * or, when a slip mid-edit took the steps away (and the page to the Model
 * tab), where they were then. Null: not in the Steps tab.
 */
export function placeToKeep(
  tab: string,
  step: number | null,
  part: number | null,
  away: StepsPlace | null,
): StepsPlace | null {
  return tab === "steps" ? { step: step ?? 0, part } : away;
}
