import { describe, expect, it } from "vitest";
import sample from "@/mocks/sample-response.json";
import type { SimulateResponse } from "./types";
import { buildFanData, buildHistogramData, dayTicks, fanAxis, niceStep } from "./chart";

const data = sample as unknown as SimulateResponse;

describe("chart data builders", () => {
  it("builds one fan row per day with bands and sample paths", () => {
    const rows = buildFanData(data.analysis);
    expect(rows).toHaveLength(data.analysis.days.length);
    expect(rows[0].day).toBe(0);
    expect(rows[0].mean).toBeCloseTo(data.parameters.S0, 2);
    expect(rows[5].outer).toEqual([data.analysis.bands.p5[5], data.analysis.bands.p95[5]]);
    expect(rows[5].s0).toBe(data.analysis.sample_paths[0][5]);
    expect(rows.at(-1)?.day).toBe(data.settings.n_steps);
  });

  it("pads the y axis around the 5-95% band with round ticks", () => {
    const { domain, ticks } = fanAxis(data.analysis, data.parameters.S0);
    expect(domain[0]).toBeLessThan(Math.min(...data.analysis.bands.p5));
    expect(domain[1]).toBeGreaterThan(Math.max(...data.analysis.bands.p95));
    expect(ticks[0]).toBe(domain[0]);
    expect(ticks.at(-1)).toBe(domain[1]);
    const step = ticks[1] - ticks[0];
    expect(Number.isInteger(step / niceStep(step))).toBe(true);
  });

  it("picks nice steps", () => {
    expect(niceStep(43)).toBe(50);
    expect(niceStep(0.18)).toBe(0.2);
    expect(niceStep(220)).toBe(250);
    expect(niceStep(1000)).toBe(1000);
  });

  it("turns histogram edges into bins whose shares sum to 1", () => {
    const bins = buildHistogramData(data.analysis.histogram);
    expect(bins).toHaveLength(data.analysis.histogram.counts.length);
    expect(bins.reduce((s, b) => s + b.share, 0)).toBeCloseTo(1, 6);
    expect(bins[0].mid).toBeCloseTo((bins[0].x0 + bins[0].x1) / 2);
  });

  it("puts day ticks on month boundaries and always ends at the horizon", () => {
    expect(dayTicks(126)).toEqual([0, 21, 42, 63, 84, 105, 126]);
    expect(dayTicks(252)).toEqual([0, 63, 126, 189, 252]);
    expect(dayTicks(21)).toEqual([0, 5, 10, 15, 21]);
    expect(dayTicks(504)).toEqual([0, 126, 252, 378, 504]);
  });
});
