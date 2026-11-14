import { fileURLToPath } from "node:url";
import { defineConfig } from "vitest/config";

// Unit and data checks live next to the code as *.test.ts; e2e/ belongs to Playwright.
export default defineConfig({
  resolve: { alias: { "@": fileURLToPath(new URL("./src", import.meta.url)) } },
  test: { include: ["src/**/*.test.ts"] },
});
