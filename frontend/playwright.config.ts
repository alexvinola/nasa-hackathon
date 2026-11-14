import { defineConfig } from "@playwright/test";

const URL = "http://localhost:3000";

// End-to-end acceptance checks (e2e/acceptance/, one spec per goal). They drive the HUD on the dev server: the one
// already running if there is one (Next.js allows a single `next dev` per project), a fresh one otherwise.
export default defineConfig({
  testDir: "e2e",
  use: { baseURL: URL },
  webServer: { command: "pnpm next dev", url: URL, reuseExistingServer: true },
});
