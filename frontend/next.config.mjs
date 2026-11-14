import { fileURLToPath } from "node:url";

// The repository root, so the HUD can import the shared contract (shared/telemetry.schema.json, shared/examples/).
const root = fileURLToPath(new URL("..", import.meta.url));

const nextConfig = { turbopack: { root }, outputFileTracingRoot: root };
export default nextConfig;
