import { afterEach, describe, expect, it, vi } from "vitest";
import { backendUnreachableCode, DEMO_MODE, simulate, SimulationError } from "./api";
import type { SimulateRequest } from "./types";

const REQ: SimulateRequest = { ticker: "AAPL", horizon: "6m" };

function stubFetch(res: Response | Error) {
  vi.stubGlobal("fetch", vi.fn(() => (res instanceof Error ? Promise.reject(res) : Promise.resolve(res))));
}

async function codeOf(p: Promise<unknown>): Promise<string> {
  try {
    await p;
  } catch (err) {
    expect(err).toBeInstanceOf(SimulationError);
    return (err as SimulationError).code;
  }
  throw new Error("expected simulate() to fail");
}

afterEach(() => {
  vi.unstubAllGlobals();
  vi.unstubAllEnvs();
});

describe("DEMO_MODE", () => {
  it("is off unless NEXT_PUBLIC_DEMO_MODE is exactly 'true'", () => {
    expect(DEMO_MODE).toBe(false);
  });
});

describe("backendUnreachableCode", () => {
  it("is data_unavailable in production and network_error otherwise", () => {
    expect(backendUnreachableCode("production")).toBe("data_unavailable");
    expect(backendUnreachableCode("development")).toBe("network_error");
    expect(backendUnreachableCode(undefined)).toBe("network_error");
  });
});

describe("simulate", () => {
  it("passes through the API's own error code", async () => {
    stubFetch(Response.json({ error: { code: "invalid_ticker", message: "nope" } }, { status: 404 }));
    expect(await codeOf(simulate(REQ))).toBe("invalid_ticker");
  });

  it("shows data_unavailable in production when /api isn't proxied (HTML 404)", async () => {
    vi.stubEnv("NODE_ENV", "production");
    stubFetch(new Response("<!doctype html><h1>404</h1>", { status: 404, headers: { "Content-Type": "text/html" } }));
    expect(await codeOf(simulate(REQ))).toBe("data_unavailable");
  });

  it("shows data_unavailable in production when BACKEND_URL points at a non-API page", async () => {
    vi.stubEnv("NODE_ENV", "production");
    stubFetch(new Response("<html>hello</html>", { status: 200 }));
    expect(await codeOf(simulate(REQ))).toBe("data_unavailable");
  });

  it("keeps network_error (with the dev hint) for a non-JSON error in dev", async () => {
    vi.stubEnv("NODE_ENV", "development");
    stubFetch(new Response("Internal Server Error", { status: 500 }));
    expect(await codeOf(simulate(REQ))).toBe("network_error");
  });

  it("reports network_error when the request itself fails", async () => {
    stubFetch(new TypeError("Failed to fetch"));
    expect(await codeOf(simulate(REQ))).toBe("network_error");
  });
});
