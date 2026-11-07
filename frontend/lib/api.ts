import type { ApiErrorBody, SimulateRequest, SimulateResponse } from "./types";

export const DEMO_MODE = process.env.NEXT_PUBLIC_DEMO_MODE === "true";

/** A failed simulation request, carrying the API's error code (or "network_error"). */
export class SimulationError extends Error {
  constructor(
    public readonly code: string,
    message: string,
    public readonly status?: number,
  ) {
    super(message);
    this.name = "SimulationError";
  }
}

function isErrorBody(body: unknown): body is ApiErrorBody {
  const err = (body as ApiErrorBody | null)?.error;
  return typeof err?.code === "string" && typeof err?.message === "string";
}

/**
 * Code for an /api response that isn't the API's own JSON (HTML 404 because BACKEND_URL isn't
 * configured, or a proxy error because the API is down). In production that's shown as
 * "data unavailable"; in dev it's "network_error", whose copy explains how to start the API.
 */
export function backendUnreachableCode(env: string | undefined = process.env.NODE_ENV): string {
  return env === "production" ? "data_unavailable" : "network_error";
}

async function simulateDemo(req: SimulateRequest, signal?: AbortSignal): Promise<SimulateResponse> {
  // Short pause so loading states are visible in demo mode.
  await new Promise<void>((resolve, reject) => {
    const t = setTimeout(resolve, 650);
    signal?.addEventListener("abort", () => {
      clearTimeout(t);
      reject(new DOMException("Aborted", "AbortError"));
    });
  });
  const mod =
    req.drift === "risk_free"
      ? await import("@/mocks/sample-response-risk-free.json")
      : await import("@/mocks/sample-response.json");
  return (mod.default ?? mod) as unknown as SimulateResponse;
}

/** POST /api/simulate (relative path; proxied to the Python API by the BACKEND_URL rewrite in next.config). */
export async function simulate(req: SimulateRequest, signal?: AbortSignal): Promise<SimulateResponse> {
  if (DEMO_MODE) return simulateDemo(req, signal);

  let res: Response;
  try {
    res = await fetch("/api/simulate", {
      method: "POST",
      headers: { "Content-Type": "application/json", Accept: "application/json" },
      body: JSON.stringify(req),
      signal,
    });
  } catch (err) {
    if ((err as Error)?.name === "AbortError") throw err;
    throw new SimulationError("network_error", "Network request failed");
  }

  let body: unknown = null;
  try {
    body = await res.json();
  } catch {
    body = null;
  }

  if (!res.ok) {
    if (isErrorBody(body)) throw new SimulationError(body.error.code, body.error.message, res.status);
    // Non-JSON error (no rewrite configured, or the proxy couldn't reach the API).
    throw new SimulationError(backendUnreachableCode(), `Unexpected ${res.status} response`, res.status);
  }
  if (!body || typeof body !== "object" || !("analysis" in body)) {
    throw new SimulationError(backendUnreachableCode(), "Response was not a simulation result", res.status);
  }
  return body as SimulateResponse;
}
