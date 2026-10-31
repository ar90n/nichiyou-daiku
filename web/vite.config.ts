import { defineConfig } from "vitest/config";

export default defineConfig({
  // Relative, so that the same build works under a GitHub Pages subpath
  base: "./",
  test: { environment: "node" },
});
