import { afterEach, describe, expect, it, vi } from "vitest";
import { backendUnreachableCode, backtest, DEMO_MODE, simulate, SimulationError } from "./api";
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

describe("backtest", () => {
  it("posts to /api/backtest and returns a rolling result", async () => {
    const fetchMock = vi.fn(() => Promise.resolve(Response.json({ summary: {}, windows: [] })));
    vi.stubGlobal("fetch", fetchMock);
    const res = await backtest({ mode: "rolling", ticker: "AAPL", horizon: "6m" });
    expect("summary" in res).toBe(true);
    const [url, init] = fetchMock.mock.calls[0] as unknown as [string, RequestInit];
    expect(url).toBe("/api/backtest");
    expect(JSON.parse(String(init.body))).toEqual({ mode: "rolling", ticker: "AAPL", horizon: "6m" });
  });

  it("passes through the API's error code and message", async () => {
    stubFetch(Response.json({ error: { code: "invalid_input", message: "Start date is too recent" } }, { status: 422 }));
    try {
      await backtest({ mode: "single", ticker: "AAPL", horizon: "6m", start_date: "2026-10-01" });
      throw new Error("expected failure");
    } catch (err) {
      expect((err as SimulationError).code).toBe("invalid_input");
      expect((err as SimulationError).message).toBe("Start date is too recent");
    }
  });

  it("rejects a body that isn't the requested kind of result", async () => {
    stubFetch(Response.json({ analysis: {} }));
    expect(await codeOf(backtest({ mode: "single", ticker: "AAPL", horizon: "6m", start_date: "2025-05-01" }))).toBe(
      "network_error",
    );
  });
});
