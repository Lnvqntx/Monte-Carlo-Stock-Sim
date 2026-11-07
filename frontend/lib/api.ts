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

async function simulateDemo(signal?: AbortSignal): Promise<SimulateResponse> {
  // Short pause so loading states are visible in demo mode.
  await new Promise<void>((resolve, reject) => {
    const t = setTimeout(resolve, 650);
    signal?.addEventListener("abort", () => {
      clearTimeout(t);
      reject(new DOMException("Aborted", "AbortError"));
    });
  });
  const mod = await import("@/mocks/sample-response.json");
  return (mod.default ?? mod) as unknown as SimulateResponse;
}

/** POST /api/simulate (relative path; proxied to the Python API by next.config rewrites in dev). */
export async function simulate(req: SimulateRequest, signal?: AbortSignal): Promise<SimulateResponse> {
  if (DEMO_MODE) return simulateDemo(signal);

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
    // Non-JSON error (e.g. the dev proxy couldn't reach the API): treat as unreachable.
    throw new SimulationError("network_error", `Unexpected ${res.status} response`, res.status);
  }
  if (!body || typeof body !== "object" || !("analysis" in body)) {
    throw new SimulationError("network_error", "Response was not a simulation result", res.status);
  }
  return body as SimulateResponse;
}
