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
 * Round, evenly spaced ticks covering [min, max]. Tries 1/2/2.5/5 x 10^n steps; among those giving
 * `minIntervals`-`maxIntervals` intervals it keeps the tightest range (ties: fewer ticks). The domain
 * ends on ticks, so there is never a crowded partial tick at either edge.
 */
export function niceTicks(min: number, max: number, minIntervals = 4, maxIntervals = 8): NiceAxis {
  if (!Number.isFinite(min) || !Number.isFinite(max)) return { domain: [0, 1], ticks: [0, 1] };
  if (max <= min) max = min + Math.abs(min || 1) * 0.1;
  const magnitude = 10 ** Math.floor(Math.log10((max - min) / minIntervals));
  type Candidate = { step: number; start: number; intervals: number; span: number };
  const candidates: Candidate[] = [];
  for (const scale of [0.1, 1, 10]) {
    for (const f of [1, 2, 2.5, 5]) {
      const step = f * magnitude * scale;
      const start = min >= 0 ? Math.max(0, Math.floor(min / step) * step) : Math.floor(min / step) * step;
      const end = Math.ceil(max / step) * step;
      candidates.push({ step, start, intervals: Math.round((end - start) / step), span: end - start });
    }
  }
  const inRange = candidates.filter((c) => c.intervals >= minIntervals && c.intervals <= maxIntervals);
  const pool = inRange.length
    ? inRange.sort((x, y) => x.span - y.span || x.intervals - y.intervals)
    : candidates.sort((x, y) => Math.abs(x.intervals - minIntervals) - Math.abs(y.intervals - minIntervals));
  const { step, start, intervals } = pool[0];
  const ticks = Array.from({ length: intervals + 1 }, (_, i) => Number((start + i * step).toPrecision(12)));
  return { domain: [ticks[0], ticks[ticks.length - 1]], ticks };
}

/** Y axis from the 5-95% band (with padding), so outlier sample paths don't flatten the fan. */
export function fanAxis(a: Analysis, S0: number): NiceAxis {
  const lo = Math.min(S0, ...a.bands.p5);
  const hi = Math.max(S0, ...a.bands.p95);
  const pad = (hi - lo) * 0.08;
  return niceTicks(Math.max(0, lo - pad), hi + pad, 4, 6);
}

/** X axis for the final-price histogram: round ticks spanning every bin. */
export function histogramAxis(h: Histogram): NiceAxis {
  return niceTicks(h.bin_edges[0], h.bin_edges[h.bin_edges.length - 1], 4, 8);
}

export interface Marker {
  key: string;
  x: number;
}

export interface MarkerLayout extends Marker {
  /** Label row above the plot (0 = closest to the plot). */
  row: number;
  /** Which side of the line the label sits on. */
  anchor: "start" | "middle" | "end";
}

/**
 * Place reference-line labels so they never overlap: markers closer than `minGap` (a fraction of
 * the axis width) go on different rows, and each close pair splits to opposite sides of its lines.
 */
export function layoutMarkers(markers: Marker[], domain: [number, number], minGap = 0.16): MarkerLayout[] {
  const width = domain[1] - domain[0] || 1;
  const sorted = [...markers].sort((a, b) => a.x - b.x);
  const close = (a: Marker, b: Marker) => Math.abs(a.x - b.x) / width < minGap;
  const placed: MarkerLayout[] = [];
  sorted.forEach((m, i) => {
    let row = 0;
    while (placed.some((p) => p.row === row && close(p, m))) row++;
    const prev = sorted[i - 1];
    const next = sorted[i + 1];
    const nearEdge = (m.x - domain[0]) / width < 0.06 || (domain[1] - m.x) / width < 0.06;
    let anchor: MarkerLayout["anchor"] = "middle";
    if (!nearEdge) {
      if (next && close(m, next)) anchor = "end";
      else if (prev && close(prev, m)) anchor = "start";
    }
    placed.push({ ...m, row, anchor });
  });
  return placed;
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
