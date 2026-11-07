import type { Lookback } from "./types";

export const EXAMPLE_TICKERS = [
  "AAPL",
  "MSFT",
  "NVDA",
  "TSLA",
  "RELIANCE.NS",
  "TCS.NS",
  "INFY.NS",
  "HDFCBANK.NS",
] as const;

export const HORIZONS = [
  { value: "1m", label: "1M", long: "1 month" },
  { value: "3m", label: "3M", long: "3 months" },
  { value: "6m", label: "6M", long: "6 months" },
  { value: "1y", label: "1Y", long: "1 year" },
  { value: "2y", label: "2Y", long: "2 years" },
] as const;
export type HorizonValue = (typeof HORIZONS)[number]["value"];

export const LOOKBACKS: readonly { value: Lookback; label: string }[] = [
  { value: "6mo", label: "6 mo" },
  { value: "1y", label: "1 yr" },
  { value: "2y", label: "2 yr" },
  { value: "5y", label: "5 yr" },
];

export const SIM_COUNTS = [1_000, 5_000, 10_000, 20_000] as const;

export const DEFAULTS = {
  horizon: "6m" as HorizonValue,
  lookback: "2y" as Lookback,
  nSims: 10_000,
  seed: 42,
};

/** Same rule as the API (backend/api/schemas.py TICKER_RE). */
export const TICKER_RE = /^[A-Z0-9.\-^=]{1,20}$/;

export function normalizeTicker(raw: string): string {
  return raw.trim().toUpperCase();
}

export function isHorizon(value: string | null | undefined): value is HorizonValue {
  return HORIZONS.some((h) => h.value === value?.toLowerCase());
}
