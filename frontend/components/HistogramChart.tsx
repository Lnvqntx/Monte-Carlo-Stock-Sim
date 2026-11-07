"use client";

import { useMemo } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { buildHistogramData, histogramAxis, layoutMarkers, type HistogramBin, type MarkerLayout } from "@/lib/chart";
import { formatInteger, formatMoney, formatMoneyCompact, formatProbability } from "@/lib/format";
import type { SimulateResponse } from "@/lib/types";
import { AXIS_TICK, CHART } from "./chart-theme";

interface MarkerLabelProps {
  viewBox?: { x?: number; y?: number };
  text: string;
  color: string;
  row: number;
  anchor: MarkerLayout["anchor"];
}

/** Reference-line label above the plot; row and side come from layoutMarkers so labels never collide. */
function MarkerLabel({ viewBox, text, color, row, anchor }: MarkerLabelProps) {
  const dx = anchor === "end" ? -5 : anchor === "start" ? 5 : 0;
  const x = (viewBox?.x ?? 0) + dx;
  const y = (viewBox?.y ?? 0) - 8 - row * 16;
  return (
    <text x={x} y={y} textAnchor={anchor} fill={color} fontSize={11} fontWeight={600}>
      {text}
    </text>
  );
}

function HistTooltip({ bin, currency, nSims }: { bin?: HistogramBin; currency: string | null; nSims: number }) {
  if (!bin) return null;
  return (
    <div className="rounded-xl border border-sand/20 bg-forest-950/95 px-3.5 py-3 text-sm shadow-xl backdrop-blur">
      <p className="text-xs font-medium uppercase tracking-wider text-sand/60">Final price</p>
      <p className="mt-1 font-semibold">
        {formatMoney(bin.x0, currency)} – {formatMoney(bin.x1, currency)}
      </p>
      <p className="mt-1 text-sand/70">
        <span className="font-semibold text-accent-text">{formatProbability(bin.share)}</span> of paths (
        {formatInteger(Math.round(bin.share * nSims))})
      </p>
    </div>
  );
}

export function HistogramChart({ data }: { data: SimulateResponse }) {
  const { analysis, metadata, parameters, settings } = data;
  const currency = metadata.currency;
  const bins = useMemo(() => buildHistogramData(analysis.histogram), [analysis.histogram]);
  const xAxis = useMemo(() => histogramAxis(analysis.histogram), [analysis.histogram]);

  const markers = [
    { x: analysis.final_price.p5, text: "5th pct", color: CHART.loss, dash: "4 3" },
    { x: parameters.S0, text: "Today", color: CHART.sand, dash: "5 5" },
    { x: analysis.final_price.median, text: "Median", color: CHART.sand, dash: undefined },
  ];
  const layout = layoutMarkers(
    markers.map((m) => ({ key: m.text, x: m.x })),
    xAxis.domain,
  );
  const placed = markers.map((m) => ({ ...m, ...layout.find((l) => l.key === m.text)! }));

  return (
    <div>
      <div
        className="h-[260px] w-full sm:h-[300px]"
        role="img"
        aria-label={`Histogram of ${formatInteger(settings.n_sims)} simulated final prices. Median ${formatMoney(analysis.final_price.median, currency)}, today ${formatMoney(parameters.S0, currency)}, 5th percentile ${formatMoney(analysis.final_price.p5, currency)}.`}
      >
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={bins} margin={{ top: 56, right: 20, bottom: 4, left: 0 }} barCategoryGap={1}>
            <CartesianGrid stroke={CHART.grid} vertical={false} />
            <XAxis
              dataKey="mid"
              type="number"
              domain={xAxis.domain}
              ticks={xAxis.ticks}
              interval={0}
              tick={AXIS_TICK}
              tickLine={false}
              axisLine={{ stroke: CHART.grid }}
              tickMargin={8}
              tickFormatter={(v: number) => formatMoneyCompact(v, currency)}
            />
            <YAxis
              dataKey="share"
              tick={AXIS_TICK}
              tickLine={false}
              axisLine={false}
              width={48}
              tickFormatter={(v: number) => formatProbability(v, 0)}
            />
            <Bar dataKey="share" fill={CHART.accent} fillOpacity={0.85} radius={[2, 2, 0, 0]} isAnimationActive={false} />
            {placed.map((m) => (
              <ReferenceLine
                key={m.text}
                x={m.x}
                stroke={m.color}
                strokeWidth={1.5}
                strokeDasharray={m.dash}
                label={(props: { viewBox?: { x?: number; y?: number } }) => (
                  <MarkerLabel viewBox={props.viewBox} text={m.text} color={m.color} row={m.row} anchor={m.anchor} />
                )}
              />
            ))}
            <Tooltip
              cursor={{ fill: "rgba(232, 220, 196, 0.06)" }}
              isAnimationActive={false}
              content={({ active, payload }) =>
                active ? (
                  <HistTooltip
                    bin={payload?.[0]?.payload as HistogramBin | undefined}
                    currency={currency}
                    nSims={settings.n_sims}
                  />
                ) : null
              }
            />
          </BarChart>
        </ResponsiveContainer>
      </div>
      <ul className="mt-4 flex flex-wrap gap-x-5 gap-y-2 text-xs text-sand/70" aria-label="Chart legend">
        <li className="flex items-center gap-2">
          <span aria-hidden className="w-5 border-t border-dashed border-sand/80" />
          Today {formatMoney(parameters.S0, currency)}
        </li>
        <li className="flex items-center gap-2">
          <span aria-hidden className="w-5 border-t-[1.5px] border-sand/80" />
          Median {formatMoney(analysis.final_price.median, currency)}
        </li>
        <li className="flex items-center gap-2">
          <span aria-hidden className="w-5 border-t-[1.5px] border-dashed border-loss" />
          5th percentile <span className="text-loss">{formatMoney(analysis.final_price.p5, currency)}</span>
        </li>
      </ul>
    </div>
  );
}
