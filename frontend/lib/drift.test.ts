import { describe, expect, it } from "vitest";
import { describeRateSource, isDrift, parseRatePercent, readDriftParams, writeDriftParams } from "./drift";

describe("isDrift", () => {
  it("accepts only the two API values", () => {
    expect(isDrift("historical")).toBe(true);
    expect(isDrift("risk_free")).toBe(true);
    expect(isDrift("risk-free")).toBe(false);
    expect(isDrift(null)).toBe(false);
  });
});

describe("parseRatePercent", () => {
  it("treats blank as 'use the default'", () => {
    expect(parseRatePercent("")).toEqual({ ok: true, rate: undefined });
    expect(parseRatePercent("   ")).toEqual({ ok: true, rate: undefined });
  });

  it("converts percent to a clean decimal", () => {
    expect(parseRatePercent("4.5")).toEqual({ ok: true, rate: 0.045 });
    expect(parseRatePercent(" 3.7% ")).toEqual({ ok: true, rate: 0.037 });
    expect(parseRatePercent("5,35")).toEqual({ ok: true, rate: 0.0535 });
    expect(parseRatePercent("0")).toEqual({ ok: true, rate: 0 });
    expect(parseRatePercent(".5")).toEqual({ ok: true, rate: 0.005 });
  });

  it("accepts the API bounds inclusively", () => {
    expect(parseRatePercent("-5")).toEqual({ ok: true, rate: -0.05 });
    expect(parseRatePercent("25")).toEqual({ ok: true, rate: 0.25 });
  });

  it("rejects out-of-range and non-numeric input", () => {
    for (const bad of ["25.01", "-5.5", "abc", "4.5.1", "1e2", "Infinity"]) {
      expect(parseRatePercent(bad).ok, bad).toBe(false);
    }
    expect(parseRatePercent("30")).toEqual({ ok: false, error: "Rate must be between -5% and 25%." });
  });
});

describe("describeRateSource", () => {
  it("makes sources readable", () => {
    expect(describeRateSource("live ^IRX")).toBe("Live 13-week T-bill (^IRX)");
    expect(describeRateSource("default for INR")).toBe("Default for INR");
    expect(describeRateSource("user override")).toBe("Your override");
    expect(describeRateSource("generic default")).toBe("Generic default");
    expect(describeRateSource(null)).toBe("Unknown source");
  });
});

describe("drift URL params", () => {
  const roundTrip = (search: string) => readDriftParams(new URLSearchParams(search));

  it("defaults to historical with no rate", () => {
    expect(roundTrip("ticker=AAPL&horizon=6m")).toEqual({ drift: "historical", rate: "" });
    expect(roundTrip("drift=bogus&rate=4")).toEqual({ drift: "historical", rate: "" });
  });

  it("reads risk-free and a valid rate", () => {
    expect(roundTrip("drift=risk_free")).toEqual({ drift: "risk_free", rate: "" });
    expect(roundTrip("drift=RISK_FREE&rate=4.5")).toEqual({ drift: "risk_free", rate: "4.5" });
    expect(roundTrip("drift=risk_free&rate=99")).toEqual({ drift: "risk_free", rate: "" });
  });

  it("leaves default URLs untouched and removes stale params", () => {
    const p = new URLSearchParams("ticker=AAPL&horizon=6m&drift=risk_free&rate=4");
    writeDriftParams(p, { drift: "historical", rate: "4" });
    expect(p.toString()).toBe("ticker=AAPL&horizon=6m");
  });

  it("writes drift, and rate only when overridden", () => {
    const p = new URLSearchParams("ticker=AAPL&horizon=6m");
    writeDriftParams(p, { drift: "risk_free", rate: "" });
    expect(p.toString()).toBe("ticker=AAPL&horizon=6m&drift=risk_free");
    writeDriftParams(p, { drift: "risk_free", rate: " 4.5% " });
    expect(p.toString()).toBe("ticker=AAPL&horizon=6m&drift=risk_free&rate=4.5");
    writeDriftParams(p, { drift: "risk_free", rate: "junk" });
    expect(p.toString()).toBe("ticker=AAPL&horizon=6m&drift=risk_free");
  });
});
