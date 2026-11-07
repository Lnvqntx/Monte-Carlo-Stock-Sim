"use client";

import { useMemo } from "react";
import {
  Area,
  CartesianGrid,
  ComposedChart,
  Line,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { buildFanData, dayTicks, fanAxis, sampleKey, type FanRow } from "@/lib/chart";
import { formatInteger, formatMoney, formatMoneyCompact } from "@/lib/format";
import type { SimulateResponse } from "@/lib/types";
import { AXIS_TICK, CHART } from "./chart-theme";

function FanTooltip({
  active,
  row,
  currency,
}: {
  active?: boolean;
  row?: FanRow;
  currency: string | null;
}) {
  if (!active || !row) return null;
  const items: [string, number, string][] = [
    ...(row.actual !== undefined ? ([["Actual", row.actual, CHART.sand]] as [string, number, string][]) : []),
    ["Mean", row.mean, CHART.accentText],
    ["Median", row.p50, CHART.sand],
    ["95th percentile", row.p95, CHART.sand],
    ["5th percentile", row.p5, CHART.sand],
  ];
  return (
    <div className="min-w-48 rounded-xl border border-sand/20 bg-forest-950/95 px-3.5 py-3 text-sm shadow-xl backdrop-blur">
      <p className="mb-2 text-xs font-medium uppercase tracking-wider text-sand/60">
        Day {formatInteger(row.day)}
      </p>
      <dl className="grid grid-cols-[1fr_auto] gap-x-4 gap-y-1">
        {items.map(([label, value, color]) => (
          <div key={label} className="contents">
            <dt className="text-sand/70">{label}</dt>
            <dd className="text-right font-semibold" style={{ color }}>
              {formatMoney(value, currency)}
            </dd>
          </div>
        ))}
      </dl>
    </div>
  );
}

/**
 * Fan chart of simulated paths. For a backtest pass `actual` (the realised path aligned with
 * analysis.days): it is drawn on top as a solid sand line and the reference line reads "Start".
 */
export function FanChart({ data, actual }: { data: SimulateResponse; actual?: number[] }) {
  const { analysis, metadata, parameters, settings } = data;
  const currency = metadata.currency;
  const rows = useMemo(() => buildFanData(analysis, actual), [analysis, actual]);
  const yAxis = useMemo(() => fanAxis(analysis, parameters.S0, actual), [analysis, parameters.S0, actual]);
  const isBacktest = Boolean(actual?.length);
  const startWord = isBacktest ? "Start" : "Today";

  return (
    <div>
      <div
        className="h-[300px] w-full sm:h-[400px]"
        role="img"
        aria-label={`Fan chart of ${formatInteger(settings.n_sims)} simulated price paths over ${settings.n_steps} trading days. Mean path ends at ${formatMoney(analysis.mean_path.at(-1) ?? NaN, currency)}; 90% of paths end between ${formatMoney(analysis.final_price.p5, currency)} and ${formatMoney(analysis.final_price.p95, currency)}.${isBacktest ? ` The actual price ended at ${formatMoney(actual?.at(-1) ?? NaN, currency)}.` : ""}`}
      >
        <ResponsiveContainer width="100%" height="100%">
          <ComposedChart data={rows} margin={{ top: 12, right: 12, bottom: 28, left: 0 }}>
            <CartesianGrid stroke={CHART.grid} vertical={false} />
            <XAxis
              dataKey="day"
              type="number"
              domain={[0, settings.n_steps]}
              ticks={dayTicks(settings.n_steps)}
              tick={AXIS_TICK}
              tickLine={false}
              axisLine={{ stroke: CHART.grid }}
              tickMargin={8}
              allowDecimals={false}
              label={{ value: isBacktest ? "Trading days after the start date" : "Trading days ahead", position: "insideBottom", offset: -18, fill: CHART.axis, fontSize: 12 }}
            />
            <YAxis
              type="number"
              domain={yAxis.domain}
              ticks={yAxis.ticks}
              allowDataOverflow
              tick={AXIS_TICK}
              tickLine={false}
              axisLine={false}
              width={64}
              tickFormatter={(v: number) => formatMoneyCompact(v, currency)}
            />
            <Area
              type="monotone"
              dataKey="outer"
              stroke="none"
              fill={CHART.accent}
              fillOpacity={0.2}
              isAnimationActive={false}
              activeDot={false}
            />
            <Area
              type="monotone"
              dataKey="inner"
              stroke="none"
              fill={CHART.accent}
              fillOpacity={0.3}
              isAnimationActive={false}
              activeDot={false}
            />
            {analysis.sample_paths.map((_, i) => (
              <Line
                key={i}
                type="linear"
                dataKey={sampleKey(i)}
                stroke={CHART.sand}
                strokeOpacity={0.14}
                strokeWidth={1}
                dot={false}
                activeDot={false}
                isAnimationActive={false}
              />
            ))}
            <ReferenceLine
              y={parameters.S0}
              stroke={CHART.sand}
              strokeOpacity={0.7}
              strokeDasharray="5 5"
              label={(props: { viewBox?: { x?: number; y?: number } }) => (
                <text
                  x={(props.viewBox?.x ?? 0) + 10}
                  y={(props.viewBox?.y ?? 0) + 16}
                  fill={CHART.sand}
                  stroke={CHART.tooltipBg}
                  strokeWidth={4}
                  strokeLinejoin="round"
                  paintOrder="stroke"
                  fontSize={11}
                  fontWeight={600}
                >
                  {startWord} {formatMoney(parameters.S0, currency)}
                </text>
              )}
            />
            <Line
              type="monotone"
              dataKey="mean"
              stroke={CHART.accent}
              strokeWidth={2.75}
              dot={false}
              activeDot={{ r: 4.5, fill: CHART.accent, stroke: CHART.tooltipBg, strokeWidth: 2 }}
              isAnimationActive={false}
            />
            {isBacktest ? (
              <Line
                type="linear"
                dataKey="actual"
                stroke={CHART.sand}
                strokeWidth={2.5}
                dot={false}
                activeDot={{ r: 4.5, fill: CHART.sand, stroke: CHART.tooltipBg, strokeWidth: 2 }}
                isAnimationActive={false}
              />
            ) : null}
            <Tooltip
              cursor={{ stroke: CHART.sand, strokeOpacity: 0.3 }}
              isAnimationActive={false}
              content={({ active, payload }) => (
                <FanTooltip
                  active={active}
                  row={(payload?.[0]?.payload as FanRow | undefined) ?? undefined}
                  currency={currency}
                />
              )}
            />
          </ComposedChart>
        </ResponsiveContainer>
      </div>
      <ul className="mt-4 flex flex-wrap gap-x-5 gap-y-2 text-xs text-sand/70" aria-label="Chart legend">
        {isBacktest ? (
          <li className="flex items-center gap-2 font-medium text-sand">
            <span aria-hidden className="h-[3px] w-5 rounded-full bg-sand" />
            Actual price
          </li>
        ) : null}
        <li className="flex items-center gap-2">
          <span aria-hidden className="h-[3px] w-5 rounded-full bg-accent" />
          {isBacktest ? "Forecast mean" : "Mean path"}
        </li>
        <li className="flex items-center gap-2">
          <span aria-hidden className="h-3 w-5 rounded-sm bg-accent/45" />
          25–75% of paths
        </li>
        <li className="flex items-center gap-2">
          <span aria-hidden className="h-3 w-5 rounded-sm bg-accent/20" />
          5–95% of paths
        </li>
        <li className="flex items-center gap-2">
          <span aria-hidden className="h-px w-5 bg-sand/50" />
          {analysis.sample_paths.length} sample paths
        </li>
        <li className="flex items-center gap-2">
          <span aria-hidden className="w-5 border-t border-dashed border-sand/80" />
          {isBacktest ? "Start price" : "Today\u2019s price"}
        </li>
      </ul>
    </div>
  );
}
