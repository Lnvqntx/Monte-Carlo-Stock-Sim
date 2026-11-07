/** Backtest mode: start-date limits, URL params and calibration helpers. Unit-tested in lib/backtest.test.ts. */
import { HORIZONS } from "./options";
import type { AppMode, BacktestMode, RollingSummary } from "./types";

export const APP_MODES: readonly { value: AppMode; label: string; title: string }[] = [
  { value: "simulate", label: "Simulate", title: "Forecast the range of future prices" },
  { value: "backtest", label: "Backtest", title: "Check past forecasts against what actually happened" },
];

export const BACKTEST_MODES: readonly { value: BacktestMode; label: string; title: string }[] = [
  { value: "single", label: "Single test", title: "One forecast from a past start date" },
  { value: "rolling", label: "Rolling", title: "Up to 40 past start dates: how often the bands held" },
];

export const DEFAULT_APP_MODE: AppMode = "simulate";
export const DEFAULT_BACKTEST_MODE: BacktestMode = "single";

/** Rolling backtests use fewer paths per start date (the API default). */
export const ROLLING_SIMS = 2_000;

const UNIT_TRADING_DAYS = { d: 1, w: 5, m: 21, y: 252 } as const;
/** Calendar days added on top of the horizon: the latest close can lag today by a few days. */
const DATA_LAG_DAYS = 5;
/** The default start sits this far before the latest allowed one ("one horizon + a bit"). */
const DEFAULT_MARGIN_DAYS = 14;
export const MIN_START_DATE = "1970-01-01";

const ISO_DATE = /^(\d{4})-(\d{2})-(\d{2})$/;

export function isAppMode(v: string | null | undefined): v is AppMode {
  return APP_MODES.some((m) => m.value === v);
}

export function isBacktestMode(v: string | null | undefined): v is BacktestMode {
  return BACKTEST_MODES.some((m) => m.value === v);
}

/** "6m" -> 126 trading days (same units as backend/core/horizon.py). */
export function horizonTradingDays(horizon: string): number {
  const m = /^(\d+)([dwmy])$/i.exec(horizon.trim());
  if (!m) return 0;
  return Number(m[1]) * UNIT_TRADING_DAYS[m[2].toLowerCase() as keyof typeof UNIT_TRADING_DAYS];
}

/** Parse YYYY-MM-DD as a UTC calendar date; null if malformed or not a real date. */
export function parseIsoDate(iso: string | null | undefined): Date | null {
  const m = ISO_DATE.exec((iso ?? "").trim());
  if (!m) return null;
  const d = new Date(Date.UTC(Number(m[1]), Number(m[2]) - 1, Number(m[3])));
  return d.getUTCMonth() === Number(m[2]) - 1 && d.getUTCDate() === Number(m[3]) ? d : null;
}

export function toIsoDate(d: Date): string {
  return d.toISOString().slice(0, 10);
}

/** The viewer's local calendar date as YYYY-MM-DD. */
export function localToday(now: Date = new Date()): string {
  const y = now.getFullYear();
  const m = String(now.getMonth() + 1).padStart(2, "0");
  const d = String(now.getDate()).padStart(2, "0");
  return `${y}-${m}-${d}`;
}

function addDays(iso: string, days: number): string {
  const d = parseIsoDate(iso);
  if (!d) return iso;
  d.setUTCDate(d.getUTCDate() + days);
  return toIsoDate(d);
}

/**
 * Latest start date that should still have a full horizon of closes after it: today minus the horizon
 * in calendar days (252 trading days ~ 365.25 calendar days, holidays included) minus a few days of
 * data lag. The API reports the exact latest date if a pick is still too recent.
 */
export function maxStartDate(horizon: string, today: string): string {
  const calendar = Math.ceil((horizonTradingDays(horizon) * 365.25) / 252);
  return addDays(today, -(calendar + DATA_LAG_DAYS));
}

/** About one horizon plus two weeks before today. */
export function defaultStartDate(horizon: string, today: string): string {
  return addDays(maxStartDate(horizon, today), -DEFAULT_MARGIN_DAYS);
}

/** Keep a start date valid when the horizon changes: later than the new maximum -> the maximum. */
export function clampStartDate(start: string, horizon: string, today: string): string {
  const max = maxStartDate(horizon, today);
  return start && start > max ? max : start;
}

/** Field error for the start-date picker, or undefined when it is usable. */
export function validateStartDate(start: string, horizon: string, today: string): string | undefined {
  if (!parseIsoDate(start)) return "Pick a start date.";
  if (start < MIN_START_DATE) return "Pick a date after 1970.";
  if (start > today) return "The start date must be in the past.";
  const max = maxStartDate(horizon, today);
  if (start > max) {
    const label = HORIZONS.find((h) => h.value === horizon)?.long ?? horizon;
    return `Pick ${max} or earlier, so the full ${label} after it has already happened.`;
  }
  return undefined;
}

export interface BacktestParams {
  mode: AppMode;
  backtest: BacktestMode;
  /** "" = use the default for the horizon. */
  startDate: string;
}

/**
 * Read ?mode=backtest&test=rolling&start=2025-05-01. Anything unknown falls back to Simulate,
 * so existing ?ticker=...&horizon=... links behave exactly as before.
 */
export function readBacktestParams(params: URLSearchParams): BacktestParams {
  const mode = params.get("mode")?.toLowerCase();
  const test = params.get("test")?.toLowerCase();
  const start = params.get("start")?.trim() ?? "";
  return {
    mode: isAppMode(mode) ? mode : DEFAULT_APP_MODE,
    backtest: isBacktestMode(test) ? test : DEFAULT_BACKTEST_MODE,
    startDate: parseIsoDate(start) ? start : "",
  };
}

/** Write backtest params in place; Simulate (the default) removes them all. */
export function writeBacktestParams(params: URLSearchParams, p: BacktestParams): void {
  params.delete("mode");
  params.delete("test");
  params.delete("start");
  if (p.mode !== "backtest") return;
  params.set("mode", "backtest");
  if (p.backtest === "rolling") params.set("test", "rolling");
  else if (p.startDate) params.set("start", p.startDate);
}

export type Calibration = "over" | "good" | "under";

export interface CoverageVerdict {
  status: Calibration;
  label: string;
  /** Binomial standard error of the coverage under the nominal level: sqrt(p(1-p)/n). */
  standardError: number;
}

/** Caption for coverage verdicts: the binomial error bar is a lower bound on the real noise. */
export const COVERAGE_NOISE_NOTE =
  "Overlapping windows are correlated, so the true uncertainty is even larger than this error bar.";

/**
 * Compare a band's coverage with its nominal level p, allowing for sampling noise: with n windows the
 * standard error is sqrt(p(1-p)/n). Within 2 standard errors is "Within sampling noise"; below means
 * the bands were too narrow (overconfident), above means too wide.
 */
export function assessCoverage(coverage: number, nominal: 0.5 | 0.9, nWindows: number): CoverageVerdict {
  const n = Math.max(1, nWindows);
  const standardError = Math.sqrt((nominal * (1 - nominal)) / n);
  // Tiny tolerance so a coverage exactly 2 SE away (k/n) isn't flipped by float noise.
  const limit = 2 * standardError + 1e-9;
  const diff = coverage - nominal;
  if (diff < -limit) return { status: "over", label: "Bands too narrow", standardError };
  if (diff > limit) return { status: "under", label: "Bands too wide", standardError };
  return { status: "good", label: "Within sampling noise", standardError };
}

/** One-sentence takeaway for a rolling run, driven by the 90% band. */
export function summarizeCalibration(s: RollingSummary): string {
  const misses = Math.round((1 - s.coverage_90) * s.n_windows);
  const verdict = assessCoverage(s.coverage_90, 0.9, s.n_windows).status;
  const outOf = `${misses} of ${s.n_windows} start dates ended outside the 90% band`;
  if (verdict === "over") {
    return `${outOf}, far more than the 1 in 10 you would expect. The model was overconfident: its bands were too narrow for this stock.`;
  }
  if (verdict === "under") {
    return `${outOf}. The bands were wider than they needed to be, so the model was more cautious than necessary here.`;
  }
  return `${outOf}, within the sampling noise around the 1 in 10 a well-calibrated model would miss.`;
}

export interface CalibrationBin {
  /** "0–10" */
  label: string;
  lo: number;
  hi: number;
  count: number;
  /** Share of windows (0-1). */
  share: number;
}

export function buildCalibrationData(s: RollingSummary): { bins: CalibrationBin[]; ideal: number } {
  const { bin_edges: edges, counts } = s.pit_histogram;
  const total = counts.reduce((a, b) => a + b, 0) || 1;
  const bins = counts.map((count, i) => ({
    label: `${edges[i]}–${edges[i + 1]}`,
    lo: edges[i],
    hi: edges[i + 1],
    count,
    share: count / total,
  }));
  return { bins, ideal: total / (counts.length || 1) };
}

/** "58th", "1st", "22nd", "13th" for a 0-100 percentile rank. */
export function ordinalPercentile(rank: number): string {
  const n = Math.min(100, Math.max(0, Math.round(rank)));
  const mod100 = n % 100;
  const suffix = mod100 >= 11 && mod100 <= 13 ? "th" : ({ 1: "st", 2: "nd", 3: "rd" } as Record<number, string>)[n % 10] ?? "th";
  return `${n}${suffix}`;
}
