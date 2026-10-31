/** An .nd to view: its URL is null for a file from this computer. */
export interface Source {
  name: string;
  text: string;
  url: string | null;
}

/** The .nd URL in the page's ?src=, if any. */
export function sourceUrl(search: string): string | null {
  return new URLSearchParams(search).get("src");
}

/** The page's URL with ?src= pointing at an .nd, to share. */
export function withSourceUrl(href: string, url: string): string {
  const page = new URL(href);
  page.searchParams.set("src", url);
  return page.toString();
}

/** The file name at the end of a URL's path. */
export function nameOf(url: string): string {
  // Any base will do: only the path's last part is wanted, and ?src= may be relative
  const last = new URL(url, "file:///").pathname.split("/").filter(Boolean).pop();
  return last ? decodeURIComponent(last) : "source.nd";
}

export async function fetchSource(url: string, fetchFn: typeof fetch = fetch): Promise<Source> {
  let response: Response;
  try {
    response = await fetchFn(url);
  } catch {
    // The browser hides why: CORS and network failures look the same
    throw new Error(
      `Could not open ${url}: the server does not let other sites read it, or it cannot be reached. ` +
        `Use the raw file: on GitHub, "Raw" (raw.githubusercontent.com) or a gist's raw URL.`,
    );
  }
  if (!response.ok) {
    throw new Error(
      `Could not open ${url}: the server answered ${response.status} ${response.statusText}. Check the URL.`,
    );
  }
  return { name: nameOf(url), text: await response.text(), url };
}

export async function readFile(file: Blob & { name: string }): Promise<Source> {
  return { name: file.name, text: await file.text(), url: null };
}
