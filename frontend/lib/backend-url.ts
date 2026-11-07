/**
 * Validation for BACKEND_URL, the base URL next.config.ts proxies /api/* to.
 *
 * next.config.ts runs at build time, so the rewrite is baked into the build: on Vercel,
 * set BACKEND_URL on the website project and redeploy after changing it.
 * A missing or invalid value must never break the build: we skip the rewrite instead, and the
 * browser then gets a non-JSON 404 for /api/simulate, which lib/api.ts shows as the friendly
 * "data unavailable" error.
 */

export type BackendUrlResult =
  | { ok: true; url: string }
  | { ok: false; reason: "missing" | "invalid"; detail: string };

/** Parse BACKEND_URL into an origin (+ optional base path) with no trailing slash. */
export function parseBackendUrl(raw: string | undefined): BackendUrlResult {
  const value = raw?.trim();
  if (!value) return { ok: false, reason: "missing", detail: "BACKEND_URL is not set" };

  let parsed: URL;
  try {
    parsed = new URL(value);
  } catch {
    return {
      ok: false,
      reason: "invalid",
      detail: `BACKEND_URL "${value}" is not a URL; use the full address, e.g. https://my-api.vercel.app`,
    };
  }
  if (parsed.protocol !== "http:" && parsed.protocol !== "https:") {
    return { ok: false, reason: "invalid", detail: `BACKEND_URL "${value}" must start with http:// or https://` };
  }
  if (parsed.search || parsed.hash) {
    return { ok: false, reason: "invalid", detail: `BACKEND_URL "${value}" must not contain a query string or #fragment` };
  }
  // Users often paste the health or docs URL; the rewrite appends /api/... itself.
  const path = parsed.pathname.replace(/\/+$/, "").replace(/\/api$/, "");
  return { ok: true, url: `${parsed.origin}${path}` };
}
