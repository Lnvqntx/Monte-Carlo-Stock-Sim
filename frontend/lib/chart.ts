import type { Analysis, Histogram } from "./types";

export interface FanRow {
  day: number;
  mean: number;
  p5: number;
  p25: number;
  p50: number;
  p75: number;
  p95: number;
  /** [p5, p95] for the outer band area. */
  outer: [number, number];
  /** [p25, p75] for the inner band area. */
  inner: [number, number];
  /** Sample path values keyed s0..s49. */
  [sample: `s${number}`]: number;
}

export function sampleKey(i: number): `s${number}` {
  return `s${i}`;
}

/** One row per kept trading day, combining bands, mean and sample paths for Recharts. */
export function buildFanData(a: Analysis): FanRow[] {
  return a.days.map((day, i) => {
    const row = {
      day,
      mean: a.mean_path[i],
      p5: a.bands.p5[i],
      p25: a.bands.p25[i],
      p50: a.bands.p50[i],
      p75: a.bands.p75[i],
      p95: a.bands.p95[i],
      outer: [a.bands.p5[i], a.bands.p95[i]],
      inner: [a.bands.p25[i], a.bands.p75[i]],
    } as FanRow;
    a.sample_paths.forEach((path, k) => {
      row[sampleKey(k)] = path[i];
    });
    return row;
  });
}

/** A "nice" step (1, 2, 2.5 or 5 x 10^n) close to `raw`. */
export function niceStep(raw: number): number {
  if (!(raw > 0) || !Number.isFinite(raw)) return 1;
  const pow = 10 ** Math.floor(Math.log10(raw));
  const f = raw / pow;
  const nice = f <= 1 ? 1 : f <= 2 ? 2 : f <= 2.5 ? 2.5 : f <= 5 ? 5 : 10;
  return nice * pow;
}

export interface NiceAxis {
  domain: [number, number];
  ticks: number[];
}

/**
 * Y axis from the 5-95% band (with padding), so outlier sample paths don't flatten the fan.
 * Domain ends and ticks land on round numbers.
 */
export function fanAxis(a: Analysis, S0: number, targetTicks = 5): NiceAxis {
  const lo = Math.min(S0, ...a.bands.p5);
  const hi = Math.max(S0, ...a.bands.p95);
  const pad = (hi - lo) * 0.08;
  const step = niceStep((hi - lo + 2 * pad) / targetTicks);
  const start = Math.max(0, Math.floor((lo - pad) / step) * step);
  const end = Math.ceil((hi + pad) / step) * step;
  const ticks: number[] = [];
  for (let v = start; v <= end + step / 2; v += step) ticks.push(Number(v.toPrecision(12)));
  return { domain: [start, end], ticks };
}

export interface HistogramBin {
  x0: number;
  x1: number;
  mid: number;
  count: number;
  share: number;
}

export function buildHistogramData(h: Histogram): HistogramBin[] {
  const total = h.counts.reduce((s, c) => s + c, 0) || 1;
  return h.counts.map((count, i) => {
    const x0 = h.bin_edges[i];
    const x1 = h.bin_edges[i + 1];
    return { x0, x1, mid: (x0 + x1) / 2, count, share: count / total };
  });
}

/** X ticks on month boundaries (21 trading days), widening the step for long horizons. */
export function dayTicks(nSteps: number): number[] {
  const step = nSteps <= 63 ? 5 : nSteps <= 147 ? 21 : nSteps <= 273 ? 63 : 126;
  const ticks: number[] = [];
  for (let d = 0; d <= nSteps; d += step) ticks.push(d);
  if (ticks.at(-1) !== nSteps && nSteps - (ticks.at(-1) ?? 0) < step / 2) ticks.pop();
  if (ticks.at(-1) !== nSteps) ticks.push(nSteps);
  return ticks;
}
