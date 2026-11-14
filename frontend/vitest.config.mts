import { defineConfig } from "vitest/config";

// Unit and data checks only; the Playwright specs under e2e/ are not Vitest's.
export default defineConfig({ test: { include: ["src/**/*.test.ts"] } });
