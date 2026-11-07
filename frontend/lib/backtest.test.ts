import { describe, expect, it } from "vitest";
import rolling from "@/mocks/sample-backtest-rolling.json";
import single from "@/mocks/sample-backtest-single.json";
import {
  assessCoverage,
  buildCalibrationData,
  clampStartDate,
  defaultStartDate,
  horizonTradingDays,
  isAppMode,
  isBacktestMode,
  localToday,
  maxStartDate,
  ordinalPercentile,
  parseIsoDate,
  readBacktestParams,
  summarizeCalibration,
  validateStartDate,
  writeBacktestParams,
} from "./backtest";
import { buildFanData, fanAxis } from "./chart";
import { isRollingBacktest, type RollingBacktestResponse, type RollingSummary, type SingleBacktestResponse } from "./types";

const ROLLING = rolling as unknown as RollingBacktestResponse;
const SINGLE = single as unknown as SingleBacktestResponse;
const TODAY = "2026-11-07";

describe("modes", () => {
  it("accepts only known values", () => {
    expect(isAppMode("backtest")).toBe(true);
    expect(isAppMode("simulate")).toBe(true);
    expect(isAppMode("Backtest")).toBe(false);
    expect(isBacktestMode("rolling")).toBe(true);
    expect(isBacktestMode("walk")).toBe(false);
  });
});

describe("start-date limits", () => {
  it("converts horizons to trading days like the backend", () => {
    expect(horizonTradingDays("1m")).toBe(21);
    expect(horizonTradingDays("6m")).toBe(126);
    expect(horizonTradingDays("2y")).toBe(504);
    expect(horizonTradingDays("bad")).toBe(0);
  });

  it("puts the latest start one horizon (in calendar days) plus a data lag before today", () => {
    expect(maxStartDate("6m", TODAY)).toBe("2026-05-03"); // 183 + 5 days
    expect(maxStartDate("1y", TODAY)).toBe("2025-11-01"); // 366 + 5 days
    expect(maxStartDate("1m", "2026-03-01")).toBe("2026-01-24"); // crosses a month and February
  });

  it("defaults to two weeks before the latest allowed start", () => {
    expect(defaultStartDate("6m", TODAY)).toBe("2026-04-19");
    expect(defaultStartDate("6m", TODAY) < maxStartDate("6m", TODAY)).toBe(true);
  });

  it("clamps a start date that is too recent for a new horizon", () => {
    expect(clampStartDate("2026-06-01", "1y", TODAY)).toBe("2025-11-01");
    expect(clampStartDate("2024-01-02", "1y", TODAY)).toBe("2024-01-02");
    expect(clampStartDate("", "1y", TODAY)).toBe("");
  });

  it("validates the picked date", () => {
    expect(validateStartDate("2025-05-01", "6m", TODAY)).toBeUndefined();
    expect(validateStartDate("", "6m", TODAY)).toBe("Pick a start date.");
    expect(validateStartDate("2025-02-30", "6m", TODAY)).toBe("Pick a start date.");
    expect(validateStartDate("1969-12-31", "6m", TODAY)).toMatch(/1970/);
    expect(validateStartDate("2026-12-01", "6m", TODAY)).toMatch(/past/);
    expect(validateStartDate("2026-09-01", "6m", TODAY)).toBe(
      "Pick 2026-05-03 or earlier, so the full 6 months after it has already happened.",
    );
  });

  it("parses only real calendar dates", () => {
    expect(parseIsoDate("2024-02-29")?.toISOString()).toBe("2024-02-29T00:00:00.000Z");
    expect(parseIsoDate("2025-02-29")).toBeNull();
    expect(parseIsoDate("2025-5-1")).toBeNull();
  });

  it("formats the local date", () => {
    expect(localToday(new Date(2026, 0, 5, 23, 59))).toBe("2026-01-05");
  });
});

describe("URL params", () => {
  it("defaults to Simulate so old links are unchanged", () => {
    expect(readBacktestParams(new URLSearchParams("ticker=AAPL&horizon=6m"))).toEqual({
      mode: "simulate",
      backtest: "single",
      startDate: "",
    });
  });

  it("reads mode, test type and start date, ignoring junk", () => {
    expect(readBacktestParams(new URLSearchParams("mode=backtest&test=rolling"))).toEqual({
      mode: "backtest",
      backtest: "rolling",
      startDate: "",
    });
    expect(readBacktestParams(new URLSearchParams("mode=BACKTEST&start=2025-05-01"))).toEqual({
      mode: "backtest",
      backtest: "single",
      startDate: "2025-05-01",
    });
    expect(readBacktestParams(new URLSearchParams("mode=time-travel&test=x&start=yesterday"))).toEqual({
      mode: "simulate",
      backtest: "single",
      startDate: "",
    });
  });

  it("writes nothing for Simulate and only what matters for each backtest type", () => {
    const p = new URLSearchParams("ticker=AAPL&horizon=6m&mode=backtest&test=rolling&start=2025-01-01");
    writeBacktestParams(p, { mode: "simulate", backtest: "rolling", startDate: "2025-01-01" });
    expect(p.toString()).toBe("ticker=AAPL&horizon=6m");

    writeBacktestParams(p, { mode: "backtest", backtest: "single", startDate: "2025-05-01" });
    expect(p.toString()).toBe("ticker=AAPL&horizon=6m&mode=backtest&start=2025-05-01");

    writeBacktestParams(p, { mode: "backtest", backtest: "rolling", startDate: "2025-05-01" });
    expect(p.toString()).toBe("ticker=AAPL&horizon=6m&mode=backtest&test=rolling");
  });

  it("round-trips", () => {
    const state = { mode: "backtest", backtest: "single", startDate: "2024-03-15" } as const;
    const p = new URLSearchParams();
    writeBacktestParams(p, state);
    expect(readBacktestParams(p)).toEqual(state);
  });
});

describe("calibration", () => {
  const summary = (coverage_90: number, n_windows = 40): RollingSummary => ({
    ...ROLLING.summary,
    coverage_90,
    n_windows,
  });

  it("judges coverage against 2 binomial standard errors", () => {
    // n = 40: SE(90%) = 4.74 pts, SE(50%) = 7.91 pts.
    expect(assessCoverage(0.88, 0.9, 40)).toMatchObject({ status: "good", label: "Within sampling noise" });
    expect(assessCoverage(0.63, 0.5, 40)).toMatchObject({ status: "good", label: "Within sampling noise" });
    expect(assessCoverage(0.8, 0.9, 40)).toMatchObject({ status: "over", label: "Bands too narrow" });
    expect(assessCoverage(1, 0.9, 40)).toMatchObject({ status: "under", label: "Bands too wide" });
    expect(assessCoverage(0.3, 0.5, 40).status).toBe("over");
    expect(assessCoverage(0.7, 0.5, 40).status).toBe("under");
    expect(assessCoverage(0.9, 0.9, 40).standardError).toBeCloseTo(Math.sqrt(0.09 / 40), 12);
  });

  it("treats exactly 2 standard errors as within noise and tightens with more windows", () => {
    // n = 25, p = 50%: SE = 10 pts, so 30% and 70% sit exactly on the edge.
    expect(assessCoverage(0.3, 0.5, 25).status).toBe("good");
    expect(assessCoverage(0.7, 0.5, 25).status).toBe("good");
    expect(assessCoverage(0.29, 0.5, 25).status).toBe("over");
    // 63% is noise with 40 windows but not with 400.
    expect(assessCoverage(0.63, 0.5, 400).status).toBe("under");
    expect(assessCoverage(0.85, 0.9, 400).status).toBe("over");
  });

  it("summarizes in plain English", () => {
    expect(summarizeCalibration(summary(0.75))).toMatch(/^10 of 40 start dates ended outside the 90% band, .*overconfident/);
    expect(summarizeCalibration(summary(0.9))).toMatch(/^4 of 40 .*well-calibrated/);
    expect(summarizeCalibration(summary(1))).toMatch(/^0 of 40 .*cautious/);
  });

  it("builds 10 bins whose counts add up to the windows, with a flat ideal", () => {
    const { bins, ideal } = buildCalibrationData(ROLLING.summary);
    expect(bins).toHaveLength(10);
    expect(bins[0].label).toBe("0–10");
    expect(bins[9].label).toBe("90–100");
    expect(bins.reduce((s, b) => s + b.count, 0)).toBe(ROLLING.summary.n_windows);
    expect(bins.reduce((s, b) => s + b.share, 0)).toBeCloseTo(1, 10);
    expect(ideal).toBeCloseTo(ROLLING.summary.n_windows / 10, 10);
  });

  it("formats percentile ordinals", () => {
    expect([1, 2, 3, 4, 11, 12, 13, 21, 22, 58, 100].map(ordinalPercentile)).toEqual([
      "1st", "2nd", "3rd", "4th", "11th", "12th", "13th", "21st", "22nd", "58th", "100th",
    ]);
    expect(ordinalPercentile(85.73)).toBe("86th");
  });
});

describe("demo mocks match the API contract", () => {
  it("tells rolling and single results apart", () => {
    expect(isRollingBacktest(ROLLING)).toBe(true);
    expect(isRollingBacktest(SINGLE)).toBe(false);
  });

  it("single: actual path aligned with the fan chart days", () => {
    const { analysis, backtest } = SINGLE;
    expect(backtest.actual_path).toHaveLength(analysis.days.length);
    expect(backtest.actual_path[0]).toBeCloseTo(SINGLE.parameters.S0, 2);
    expect(backtest.actual_path.at(-1)).toBe(backtest.actual_final);
    expect(SINGLE.settings.mode).toBe("single");
  });

  it("rolling: at most 40 windows and a 10-bin histogram", () => {
    expect(ROLLING.windows.length).toBeLessThanOrEqual(40);
    expect(ROLLING.windows).toHaveLength(ROLLING.summary.n_windows);
    expect(ROLLING.summary.pit_histogram.counts).toHaveLength(10);
    for (const w of ROLLING.windows) {
      expect(w.p5).toBeLessThanOrEqual(w.p95);
      expect(w.inside_90).toBe(w.actual_final >= w.p5 && w.actual_final <= w.p95);
    }
  });

  it("adds the actual path to fan rows and keeps it inside the y axis", () => {
    const rows = buildFanData(SINGLE.analysis, SINGLE.backtest.actual_path);
    expect(rows[0].actual).toBe(SINGLE.backtest.actual_path[0]);
    expect(rows.at(-1)?.actual).toBe(SINGLE.backtest.actual_final);
    expect(buildFanData(SINGLE.analysis)[0].actual).toBeUndefined();

    const spike = SINGLE.backtest.actual_path.map((v, i) => (i === 5 ? v * 3 : v));
    const axis = fanAxis(SINGLE.analysis, SINGLE.parameters.S0, spike);
    expect(axis.domain[1]).toBeGreaterThanOrEqual(Math.max(...spike));
  });
});
