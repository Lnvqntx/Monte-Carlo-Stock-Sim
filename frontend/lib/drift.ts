/** Drift model options, the risk-free rate field and their URL params. Unit-tested in lib/drift.test.ts. */
import type { DriftModel } from "./types";

export const DRIFTS: readonly { value: DriftModel; label: string; title: string }[] = [
  { value: "historical", label: "Historical", title: "Drift estimated from the stock's past returns" },
  { value: "risk_free", label: "Risk-free", title: "Drift set to the risk-free rate (risk-neutral)" },
];

export const DEFAULT_DRIFT: DriftModel = "historical";

/** Same bounds as the API (backend/core/rates.py), in percent. */
export const MIN_RATE_PCT = -5;
export const MAX_RATE_PCT = 25;

export function isDrift(value: string | null | undefined): value is DriftModel {
  return DRIFTS.some((d) => d.value === value);
}

export type RateParse = { ok: true; rate: number | undefined } | { ok: false; error: string };

/**
 * Parse the "Risk-free rate %" field. Blank -> undefined (use the server default);
 * "4.5" -> 0.045. Accepts a trailing % and a comma decimal separator.
 */
export function parseRatePercent(raw: string): RateParse {
  const text = raw.trim().replace(/%$/, "").trim().replace(",", ".");
  if (!text) return { ok: true, rate: undefined };
  if (!/^[-+]?(\d+\.?\d*|\.\d+)$/.test(text)) {
    return { ok: false, error: "Enter the rate as a percentage, e.g. 4.5." };
  }
  const pct = Number(text);
  if (!Number.isFinite(pct) || pct < MIN_RATE_PCT || pct > MAX_RATE_PCT) {
    return { ok: false, error: `Rate must be between ${MIN_RATE_PCT}% and ${MAX_RATE_PCT}%.` };
  }
  // Round away binary noise: 4.5 / 100 = 0.045000000000000005.
  return { ok: true, rate: Number((pct / 100).toPrecision(10)) };
}

/** "live ^IRX" -> "Live 13-week T-bill (^IRX)", "default for INR" -> "Default for INR". */
export function describeRateSource(source: string | null | undefined): string {
  if (!source) return "Unknown source";
  if (source === "live ^IRX") return "Live 13-week T-bill (^IRX)";
  if (source === "user override") return "Your override";
  return source.charAt(0).toUpperCase() + source.slice(1);
}

export interface DriftParams {
  drift: DriftModel;
  /** The rate field text as typed (percent), "" when not overridden. */
  rate: string;
}

/** Read ?drift=risk_free&rate=4.5. Unknown drift -> historical; rate only kept with risk-free and when valid. */
export function readDriftParams(params: URLSearchParams): DriftParams {
  const raw = params.get("drift")?.toLowerCase();
  const drift = isDrift(raw) ? raw : DEFAULT_DRIFT;
  const rateText = (params.get("rate") ?? "").trim();
  const parsed = parseRatePercent(rateText);
  const rate = drift === "risk_free" && parsed.ok && parsed.rate !== undefined ? rateText : "";
  return { drift, rate };
}

/**
 * Write drift params in place. Historical (the default) removes both, so default URLs stay
 * ?ticker=...&horizon=... exactly as before; rate is only written when overridden.
 */
export function writeDriftParams(params: URLSearchParams, { drift, rate }: DriftParams): void {
  params.delete("drift");
  params.delete("rate");
  if (drift === DEFAULT_DRIFT) return;
  params.set("drift", drift);
  const parsed = parseRatePercent(rate);
  if (parsed.ok && parsed.rate !== undefined) params.set("rate", rate.trim().replace(/%$/, "").trim());
}
