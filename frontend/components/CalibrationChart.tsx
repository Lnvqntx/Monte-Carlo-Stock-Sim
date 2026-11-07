"use client";

import { useMemo } from "react";
import { Bar, BarChart, CartesianGrid, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { buildCalibrationData, type CalibrationBin } from "@/lib/backtest";
import { niceTicks } from "@/lib/chart";
import { formatInteger, formatProbability } from "@/lib/format";
import type { RollingSummary } from "@/lib/types";
import { AXIS_TICK, CHART } from "./chart-theme";

function BinTooltip({ bin, total }: { bin?: CalibrationBin; total: number }) {
  if (!bin) return null;
  return (
    <div className="rounded-xl border border-sand/20 bg-forest-950/95 px-3.5 py-3 text-sm shadow-xl backdrop-blur">
      <p className="text-xs font-medium uppercase tracking-wider text-sand/60">Percentile {bin.label}</p>
      <p className="mt-1 text-sand/80">
        <span className="font-semibold text-accent-text">{formatInteger(bin.count)}</span> of {formatInteger(total)} start
        dates ({formatProbability(bin.share, 0)})
      </p>
    </div>
  );
}

/** PIT histogram: where each actual final price landed within its forecast, with the flat "ideal" line. */
export function CalibrationChart({ summary }: { summary: RollingSummary }) {
  const { bins, ideal } = useMemo(() => buildCalibrationData(summary), [summary]);
  const yAxis = useMemo(() => {
    const top = Math.max(ideal, ...bins.map((b) => b.count));
    const axis = niceTicks(0, top * 1.15, 3, 6);
    // Counts are whole numbers: drop fractional ticks.
    const ticks = axis.ticks.filter((t) => Number.isInteger(t));
    return { domain: axis.domain, ticks };
  }, [bins, ideal]);

  return (
    <div>
      <div
        className="h-[240px] w-full sm:h-[280px]"
        role="img"
        aria-label={`Calibration histogram of ${summary.n_windows} start dates: ${bins
          .map((b) => `${b.label}: ${b.count}`)
          .join(", ")}. A well-calibrated model gives about ${ideal.toFixed(1)} per bin.`}
      >
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={bins} margin={{ top: 12, right: 12, bottom: 28, left: 0 }} barCategoryGap={3}>
            <CartesianGrid stroke={CHART.grid} vertical={false} />
            <XAxis
              dataKey="label"
              tick={AXIS_TICK}
              tickLine={false}
              axisLine={{ stroke: CHART.grid }}
              tickMargin={8}
              interval={0}
              tickFormatter={(label: string) => label.split("–")[0]}
              label={{
                value: "Percentile of the actual price in its forecast",
                position: "insideBottom",
                offset: -18,
                fill: CHART.axis,
                fontSize: 12,
              }}
            />
            <YAxis
              domain={yAxis.domain}
              ticks={yAxis.ticks}
              allowDecimals={false}
              tick={AXIS_TICK}
              tickLine={false}
              axisLine={false}
              width={36}
            />
            <Bar dataKey="count" fill={CHART.accent} fillOpacity={0.85} radius={[3, 3, 0, 0]} isAnimationActive={false} />
            <ReferenceLine y={ideal} stroke={CHART.sand} strokeWidth={1.5} strokeDasharray="6 4" ifOverflow="extendDomain" />
            <Tooltip
              cursor={{ fill: "rgba(232, 220, 196, 0.06)" }}
              isAnimationActive={false}
              content={({ active, payload }) =>
                active ? (
                  <BinTooltip bin={payload?.[0]?.payload as CalibrationBin | undefined} total={summary.n_windows} />
                ) : null
              }
            />
          </BarChart>
        </ResponsiveContainer>
      </div>
      <ul className="mt-4 flex flex-wrap gap-x-5 gap-y-2 text-xs text-sand/70" aria-label="Chart legend">
        <li className="flex items-center gap-2">
          <span aria-hidden className="h-3 w-5 rounded-sm bg-accent/85" />
          Start dates per percentile bin
        </li>
        <li className="flex items-center gap-2">
          <span aria-hidden className="w-5 border-t-[1.5px] border-dashed border-sand/80" />
          Ideal: flat at {ideal.toFixed(1)} per bin
        </li>
      </ul>
    </div>
  );
}
