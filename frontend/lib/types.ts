/**
 * TypeScript mirror of the FastAPI contract (backend/api/schemas.py + backend/api/serialize.py).
 * Keep in sync with the backend; these are the exact JSON shapes of POST /api/simulate.
 */

export type Lookback = "6mo" | "1y" | "2y" | "5y";

/** historical: mu estimated from past log returns. risk_free: mu = annual risk-free rate (risk-neutral GBM). */
export type DriftModel = "historical" | "risk_free";

/** Body of POST /api/simulate. */
export interface SimulateRequest {
  ticker: string;
  /** e.g. "1m", "6m", "1y" (max 5y). */
  horizon: string;
  lookback?: Lookback;
  /** 1,000 - 20,000. */
  n_sims?: number;
  /** Non-negative integer. */
  seed?: number;
  /** Default "historical". */
  drift?: DriftModel;
  /** Annual decimal (0.045 = 4.5%), -0.05 to 0.25. Only allowed with drift "risk_free". */
  risk_free_rate?: number;
}

/** core.data.PriceData.metadata() */
export interface SimulationMetadata {
  ticker: string;
  /** ISO 4217 code reported by the data provider, e.g. "USD" or "INR". */
  currency: string | null;
  long_name: string | null;
  /** ISO date (YYYY-MM-DD) of the last close. */
  last_date: string;
  n_prices: number;
}

/** core.estimate.Parameters.to_dict() - annualized GBM parameters. */
export interface SimulationParameters {
  /** Last close, the starting price of every path. */
  S0: number;
  /** Annualized drift actually simulated (0.12 = 12% / year): the historical estimate or the risk-free rate. */
  mu: number;
  /** Annualized drift estimated from history (always computed; equals `mu` for historical drift). */
  mu_historical: number;
  /** Annualized volatility (0.25 = 25% / year). */
  sigma: number;
  /** Number of daily log returns used for the estimate. */
  n_returns: number;
}

/** Settings echoed by core.run_simulation. */
export interface SimulationSettings {
  horizon: string;
  n_steps: number;
  T_years: number;
  lookback: Lookback;
  n_sims: number;
  seed: number;
  trading_days_per_year: number;
  drift: DriftModel;
  /** Rate used as the drift when drift is "risk_free"; null for historical drift. */
  risk_free_rate: number | null;
  /** Where the rate came from, e.g. "live ^IRX", "default for INR", "user override"; null for historical. */
  rate_source: string | null;
}

export interface FinalPriceStats {
  mean: number;
  median: number;
  p5: number;
  p25: number;
  p75: number;
  p95: number;
  min: number;
  max: number;
}

export interface Histogram {
  /** counts.length + 1 edges. */
  bin_edges: number[];
  counts: number[];
}

export type BandKey = "p5" | "p25" | "p50" | "p75" | "p95";

export interface Analysis {
  final_price: FinalPriceStats;
  /** Percent units: 12.5 means +12.5%. */
  expected_return_pct: number;
  /** Probability (0-1) that the final price is below S0. */
  prob_below_start: number;
  /** Loss at the 5th percentile as % of S0; negative = no loss at 95% confidence. */
  var_95_pct: number;
  histogram: Histogram;
  /** Trading-day index (0 = last close) of each point in the series below (<= 200 points). */
  days: number[];
  mean_path: number[];
  bands: Record<BandKey, number[]>;
  /** Up to 50 sample paths, each aligned with `days`. */
  sample_paths: number[][];
  sample_path_indices: number[];
}

export interface SimulateResponse {
  metadata: SimulationMetadata;
  parameters: SimulationParameters;
  settings: SimulationSettings;
  analysis: Analysis;
}

/** Error codes the API returns in {"error": {"code", "message"}}. */
export type ApiErrorCode =
  | "invalid_ticker"
  | "insufficient_data"
  | "invalid_input"
  | "data_unavailable"
  | "internal_error";

/** Client-side failure: the API could not be reached or answered with something that isn't JSON. */
export type ClientErrorCode = "network_error";

export type ErrorCode = ApiErrorCode | ClientErrorCode;

export interface ApiErrorBody {
  error: {
    code: string;
    message: string;
  };
}
