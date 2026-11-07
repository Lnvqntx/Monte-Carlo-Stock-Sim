import { afterEach, describe, expect, it, vi } from "vitest";
import { friendlyError, normalizeErrorCode } from "./errors";

describe("friendlyError", () => {
  it("names the ticker and the exchange suffixes for invalid_ticker", () => {
    const e = friendlyError("invalid_ticker", { ticker: "reliance" });
    expect(e.code).toBe("invalid_ticker");
    expect(e.title).toContain("RELIANCE");
    expect(e.message).toContain(".NS");
    expect(e.message).toContain(".BO");
  });

  it("suggests a longer lookback for insufficient_data", () => {
    const e = friendlyError("insufficient_data", { ticker: "NEWCO" });
    expect(e.title).toBe("Not enough price history");
    expect(e.message).toContain("NEWCO");
    expect(e.message).toMatch(/longer lookback/i);
  });

  it("shows the API's own detail for invalid_input", () => {
    const e = friendlyError("invalid_input", { detail: "n_sims: Input should be less than or equal to 20000" });
    expect(e.title).toBe("Please check your inputs");
    expect(e.message).toBe("n_sims: Input should be less than or equal to 20000");
  });

  it("has a generic invalid_input message when there is no detail", () => {
    expect(friendlyError("invalid_input").message).toMatch(/isn't valid/);
  });

  it("asks to retry for data_unavailable", () => {
    const e = friendlyError("data_unavailable");
    expect(e.title).toMatch(/temporarily unavailable/);
    expect(e.message).toMatch(/try again/i);
  });

  it("maps internal_error", () => {
    expect(friendlyError("internal_error").title).toBe("Something went wrong");
  });

  it("maps network failures", () => {
    const e = friendlyError("network_error");
    expect(e.title).toBe("Can't reach the simulator");
    expect(e.message).toMatch(/port 8000/);
  });

  describe("in a production build", () => {
    afterEach(() => vi.unstubAllEnvs());

    it("drops the local-dev hint from network failures", () => {
      vi.stubEnv("NODE_ENV", "production");
      expect(friendlyError("network_error").message).not.toMatch(/port 8000|BACKEND_URL/);
    });
  });

  it("does not leak server detail for codes other than invalid_input", () => {
    const e = friendlyError("internal_error", { detail: "Traceback ..." });
    expect(e.message).not.toContain("Traceback");
  });

  it("uses backtest copy and the API's detail for a backtest's insufficient_data", () => {
    const detail = "Not enough price history for AAPL to backtest: the earliest start date is 2018-03-01.";
    const e = friendlyError("insufficient_data", { ticker: "AAPL", detail, backtest: true });
    expect(e.title).toBe("Not enough price history for this backtest");
    expect(e.message).toBe(detail);
    expect(friendlyError("insufficient_data", { ticker: "AAPL", backtest: true }).message).toMatch(/later start date/);
    expect(friendlyError("internal_error", { backtest: true }).message).toMatch(/backtest failed/);
  });

  it("treats unknown or missing codes as internal_error", () => {
    expect(friendlyError("not_found").code).toBe("internal_error");
    expect(friendlyError(undefined).code).toBe("internal_error");
    expect(normalizeErrorCode("teapot")).toBe("internal_error");
    expect(normalizeErrorCode("data_unavailable")).toBe("data_unavailable");
  });

  it("falls back to 'that ticker' when no ticker is given", () => {
    expect(friendlyError("invalid_ticker").title).toBe("We couldn't find that ticker");
  });
});
