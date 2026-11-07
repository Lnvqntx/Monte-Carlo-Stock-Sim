import type { NextConfig } from "next";
import { parseBackendUrl } from "./lib/backend-url";

// The browser always calls the relative /api/*. When BACKEND_URL is set, /api/* is proxied
// there: http://localhost:8000 in local dev, the API project's URL on Vercel.
// This file runs at build time, so the rewrite is baked into the build: after changing
// BACKEND_URL on Vercel, redeploy. A missing or invalid value skips the rewrite (with a
// build-log warning) instead of failing the build; the site then shows "data unavailable".
const backend = parseBackendUrl(process.env.BACKEND_URL);

if (!backend.ok && (backend.reason === "invalid" || process.env.VERCEL)) {
  console.warn(`\n⚠ ${backend.detail}. /api/* will not be proxied; simulations will fail until it is fixed.\n`);
}

const nextConfig: NextConfig = {
  cacheComponents: true,
  partialPrefetching: true,
  turbopack: {
    rules: {
      "*.css": {
        loaders: ["@tailwindcss/turbopack"],
        as: "*.css",
      },
    },
  },
  async rewrites() {
    if (!backend.ok) return [];
    return [{ source: "/api/:path*", destination: `${backend.url}/api/:path*` }];
  },
};

export default nextConfig;
