import type {
  ApiErrorBody,
  BacktestRequest,
  BacktestResponse,
  SimulateRequest,
  SimulateResponse,
} from "./types";

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

/** Short pause so loading states are visible in demo mode. */
function demoDelay(signal?: AbortSignal): Promise<void> {
  return new Promise<void>((resolve, reject) => {
    const t = setTimeout(resolve, 650);
    signal?.addEventListener("abort", () => {
      clearTimeout(t);
      reject(new DOMException("Aborted", "AbortError"));
    });
  });
}

async function simulateDemo(req: SimulateRequest, signal?: AbortSignal): Promise<SimulateResponse> {
  await demoDelay(signal);
  const mod =
    req.drift === "risk_free"
      ? await import("@/mocks/sample-response-risk-free.json")
      : await import("@/mocks/sample-response.json");
  return (mod.default ?? mod) as unknown as SimulateResponse;
}

async function backtestDemo(req: BacktestRequest, signal?: AbortSignal): Promise<BacktestResponse> {
  await demoDelay(signal);
  const mod =
    req.mode === "rolling"
      ? await import("@/mocks/sample-backtest-rolling.json")
      : await import("@/mocks/sample-backtest-single.json");
  return (mod.default ?? mod) as unknown as BacktestResponse;
}

/** POST JSON to a relative /api path, mapping failures to SimulationError. */
async function postJson<T>(
  path: string,
  req: object,
  isResult: (body: object) => boolean,
  signal?: AbortSignal,
): Promise<T> {
  let res: Response;
  try {
    res = await fetch(path, {
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
  if (!body || typeof body !== "object" || !isResult(body)) {
    throw new SimulationError(backendUnreachableCode(), "Response was not a valid result", res.status);
  }
  return body as T;
}

/** POST /api/simulate (relative path; proxied to the Python API by the BACKEND_URL rewrite in next.config). */
export async function simulate(req: SimulateRequest, signal?: AbortSignal): Promise<SimulateResponse> {
  if (DEMO_MODE) return simulateDemo(req, signal);
  return postJson<SimulateResponse>("/api/simulate", req, (b) => "analysis" in b, signal);
}

/** POST /api/backtest: compare a past forecast (single) or many (rolling) with what actually happened. */
export async function backtest(req: BacktestRequest, signal?: AbortSignal): Promise<BacktestResponse> {
  if (DEMO_MODE) return backtestDemo(req, signal);
  return postJson<BacktestResponse>(
    "/api/backtest",
    req,
    (b) => (req.mode === "rolling" ? "summary" in b : "backtest" in b),
    signal,
  );
}
