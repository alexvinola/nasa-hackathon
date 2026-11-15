import { fileURLToPath } from "node:url";

// The repository root, so the HUD can import the shared contract (shared/telemetry.schema.json, shared/examples/).
const root = fileURLToPath(new URL("..", import.meta.url));

const nextConfig = {
  turbopack: { root },
  outputFileTracingRoot: root,
  // The MediaPipe models and wasm (about 25 MB) never change between downloads: let the browser keep them for a
  // day instead of asking the server again on every reload, which also lets it reuse the compiled wasm.
  // Home (/) is the landing page (docs/brand/pulsar-landing.html, copied to public/landing/); the app lives at /pulsar.
  rewrites: async () => [
    { source: "/", destination: "/landing/index.html" },
    { source: "/pulsar-intro.html", destination: "/landing/pulsar-intro.html" },
  ],
  headers: async () => [{ source: "/mediapipe/:path*", headers: [{ key: "Cache-Control", value: "public, max-age=86400" }] }],
};
export default nextConfig;
