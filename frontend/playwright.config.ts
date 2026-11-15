import { defineConfig } from "@playwright/test";

// Its own port: a HUD from another checkout may already be running on 3000 and must not be the one under test.
// The specs mock the backend (http://localhost:8000) themselves, so only the Next.js dev server is started.
const PORT = 3100;

export default defineConfig({
  testDir: "e2e",
  timeout: 60_000,
  use: { baseURL: `http://localhost:${PORT}`, viewport: { width: 1440, height: 900 } },
  webServer: { env: { NEXT_PUBLIC_LANG: "en" }, command: `pnpm dev --port ${PORT}`, url: `http://localhost:${PORT}`, reuseExistingServer: true, timeout: 120_000 },
});
