"use client";

import { DEMO_MODE } from "@/lib/api";
import { describeRateSource } from "@/lib/drift";
import {
  describeVar,
  formatAnnualRate,
  formatDate,
  formatHorizon,
  formatInteger,
  formatMoney,
  formatPercent,
  formatProbability,
} from "@/lib/format";
import type { SimulateResponse } from "@/lib/types";
import { FanChart } from "./FanChart";
import { HistogramChart } from "./HistogramChart";
import { Card, SectionTitle, cx } from "./ui";

function StatCard({
  label,
  value,
  tone,
  note,
  small,
}: {
  label: string;
  value: string;
  tone: "accent" | "loss" | "neutral";
  note: React.ReactNode;
  small?: boolean;
}) {
  return (
    <Card className="flex flex-col p-5">
      <p className="text-sm font-medium text-sand/70">{label}</p>
      <p
        className={cx(
          "mt-3 font-semibold tracking-tight",
          small ? "text-lg leading-snug sm:text-xl" : "text-3xl sm:text-[2rem]",
          tone === "accent" && "text-accent-text",
          tone === "loss" && "text-loss",
          tone === "neutral" && "text-sand",
        )}
      >
        {value}
      </p>
      <p className="mt-2 text-[0.8125rem] leading-relaxed text-sand/60">{note}</p>
    </Card>
  );
}

export function Results({ data }: { data: SimulateResponse }) {
  const { metadata, parameters, settings, analysis } = data;
  const currency = metadata.currency;
  const money = (v: number) => formatMoney(v, currency);
  const horizon = formatHorizon(settings.horizon);
  const varInfo = describeVar(analysis.var_95_pct);
  const returnTone = analysis.expected_return_pct < 0 ? "loss" : "accent";

  const percentiles: [string, number][] = [
    ["5th", analysis.final_price.p5],
    ["25th", analysis.final_price.p25],
    ["Median", analysis.final_price.median],
    ["75th", analysis.final_price.p75],
    ["95th", analysis.final_price.p95],
  ];

  const riskFree = settings.drift === "risk_free";
  const muHistorical = parameters.mu_historical ?? parameters.mu;
  const rate = settings.risk_free_rate ?? parameters.mu;
  const volatility: [string, string, string?] = [
    "Volatility σ (annual)",
    formatAnnualRate(parameters.sigma),
    "Std. dev. of daily log returns × √252",
  ];
  const common: [string, string, string?][] = [
    ["Simulations", formatInteger(settings.n_sims)],
    ["Seed", String(settings.seed)],
    ["Horizon", horizon, `${formatInteger(settings.n_steps)} trading days`],
  ];
  // Both modes show 8 cells so the grid stays full at 2 and 4 columns.
  const details: [string, string, string?][] = riskFree
    ? [
        ["Drift model", "Risk-free", "Risk-neutral GBM: μ\u00a0=\u00a0r"],
        ["Drift μ used (annual)", formatAnnualRate(rate, { signed: true }), describeRateSource(settings.rate_source)],
        ["Historical μ (annual)", formatAnnualRate(muHistorical, { signed: true }), "Estimated from history, not used"],
        volatility,
        ["Lookback", settings.lookback, `${formatInteger(parameters.n_returns)} daily returns`],
        ...common,
      ]
    : [
        ["Drift model", "Historical", "μ estimated from past returns"],
        ["Drift μ (annual)", formatAnnualRate(parameters.mu, { signed: true }), "Mean log return × 252 + σ²/2"],
        volatility,
        ["Daily returns used", formatInteger(parameters.n_returns)],
        ["Lookback", settings.lookback],
        ...common,
      ];

  return (
    <div className="grid gap-5 sm:gap-6">
      {DEMO_MODE ? (
        <p className="rounded-xl border border-dashed border-sand/25 px-4 py-2.5 text-center text-xs text-sand/70">
          Demo mode: showing bundled sample data generated from synthetic prices, whatever ticker you pick.
        </p>
      ) : null}

      {/* Header */}
      <Card as="section" aria-labelledby="result-title" className="p-5 sm:p-7">
        <div className="flex flex-col gap-5 sm:flex-row sm:items-end sm:justify-between">
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-2">
              <span className="rounded-md border border-sand/20 bg-sand/8 px-2 py-0.5 text-xs font-semibold tracking-wider">
                {metadata.ticker}
              </span>
              {currency ? <span className="text-xs font-medium text-sand/55">{currency}</span> : null}
            </div>
            <h2 id="result-title" className="mt-2.5 break-words text-2xl font-semibold tracking-tight sm:text-3xl">
              {metadata.long_name || metadata.ticker}
            </h2>
            <p className="mt-1.5 text-sm text-sand/65">
              {horizon} ahead · {formatInteger(settings.n_steps)} trading days · {formatInteger(settings.n_sims)} simulated paths
              {riskFree ? " · risk-free drift" : ""}
            </p>
          </div>
          <div className="sm:text-right">
            <p className="text-xs font-medium uppercase tracking-[0.14em] text-sand/55">Current price</p>
            <p className="mt-1 text-3xl font-semibold tracking-tight sm:text-4xl">{money(parameters.S0)}</p>
            <p className="mt-1 text-sm text-sand/60">
              Last close <time dateTime={metadata.last_date}>{formatDate(metadata.last_date)}</time>
            </p>
          </div>
        </div>
      </Card>

      {/* Stats */}
      <section aria-label="Key statistics" className="grid grid-cols-1 gap-4 min-[480px]:grid-cols-2 lg:grid-cols-4">
        <StatCard
          label="Expected price"
          value={money(analysis.final_price.mean)}
          tone="accent"
          note={<>Mean final price in {horizon}. Median {money(analysis.final_price.median)}.</>}
        />
        <StatCard
          label="Expected return"
          value={formatPercent(analysis.expected_return_pct, { signed: true })}
          tone={returnTone}
          note={<>From {money(parameters.S0)} today to the mean final price.</>}
        />
        <StatCard
          label="Probability of loss"
          value={formatProbability(analysis.prob_below_start)}
          tone="loss"
          note="Share of simulated paths that end below today's price."
        />
        <StatCard
          label="95% Value at Risk"
          value={varInfo.text}
          tone={varInfo.noLoss ? "neutral" : "loss"}
          small={varInfo.noLoss}
          note={
            varInfo.noLoss ? (
              <>Even the 5th-percentile outcome ({money(analysis.final_price.p5)}) ends above today&apos;s price.</>
            ) : (
              <>
                In the worst 5% of paths you lose at least {money(parameters.S0 - analysis.final_price.p5)} per share.
              </>
            )
          }
        />
      </section>

      {/* Fan chart */}
      <Card as="section" aria-labelledby="fan-title" className="p-5 sm:p-7">
        <SectionTitle
          id="fan-title"
          title="Simulated price paths"
          description={`How the price could evolve over the next ${horizon}. Shaded bands hold the middle 50% and 90% of all ${formatInteger(settings.n_sims)} paths.`}
        />
        <div className="mt-5 -mx-1 sm:mx-0">
          <FanChart data={data} />
        </div>
      </Card>

      <div className="grid gap-5 sm:gap-6 lg:grid-cols-[minmax(0,1.6fr)_minmax(0,1fr)]">
        {/* Histogram */}
        <Card as="section" aria-labelledby="hist-title" className="p-5 sm:p-7">
          <SectionTitle
            id="hist-title"
            title="Distribution of final prices"
            description={`Where the ${formatInteger(settings.n_sims)} paths end after ${formatInteger(settings.n_steps)} trading days.`}
          />
          <div className="mt-5 -mx-1 sm:mx-0">
            <HistogramChart data={data} />
          </div>
        </Card>

        {/* Percentiles */}
        <Card as="section" aria-labelledby="pct-title" className="p-5 sm:p-7">
          <SectionTitle id="pct-title" title="Final price percentiles" description="Compared with today's price." />
          <table className="mt-4 w-full text-sm">
            <caption className="sr-only">Percentiles of the simulated final price and change from today</caption>
            <thead>
              <tr className="text-left text-xs uppercase tracking-wider text-sand/50">
                <th scope="col" className="pb-2 font-medium">Percentile</th>
                <th scope="col" className="pb-2 text-right font-medium">Price</th>
                <th scope="col" className="pb-2 text-right font-medium">vs today</th>
              </tr>
            </thead>
            <tbody>
              {percentiles.map(([label, value]) => {
                const change = (value / parameters.S0 - 1) * 100;
                const isMedian = label === "Median";
                return (
                  <tr key={label} className={cx("border-t border-sand/10", isMedian && "bg-sand/[0.04]")}>
                    <th scope="row" className={cx("py-3 pl-1 text-left", isMedian ? "font-semibold" : "font-medium text-sand/80")}>
                      {label}
                    </th>
                    <td className="py-3 text-right font-semibold">{money(value)}</td>
                    <td className={cx("py-3 pr-1 text-right", change < 0 ? "text-loss" : "text-sand/75")}>
                      {formatPercent(change, { signed: true })}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </Card>
      </div>

      {/* Model details */}
      <Card as="section" aria-labelledby="model-title" className="p-5 sm:p-7">
        <SectionTitle
          id="model-title"
          title="Model details"
          description={
            riskFree
              ? `Volatility estimated from ${formatInteger(metadata.n_prices)} daily closes over the ${settings.lookback} lookback; drift set to the risk-free rate.`
              : `Parameters estimated from ${formatInteger(metadata.n_prices)} daily closes over the ${settings.lookback} lookback.`
          }
        />
        <dl className="mt-5 grid gap-px overflow-hidden rounded-xl border border-sand/10 bg-sand/10 grid-cols-2 lg:grid-cols-4">
          {details.map(([term, value, hint]) => (
            <div key={term} className="min-w-0 bg-forest-900 p-4">
              <dt className="text-xs font-medium text-sand/60">{term}</dt>
              <dd className="mt-1.5 text-base font-semibold tracking-tight sm:text-lg">{value}</dd>
              {hint ? <dd className="mt-1 text-xs text-sand/50">{hint}</dd> : null}
            </div>
          ))}
        </dl>
        {riskFree ? (
          <p className="mt-4 rounded-xl border border-accent/30 bg-accent/[0.07] px-4 py-3 text-sm leading-relaxed text-sand/80">
            <span className="font-semibold text-sand">A neutral baseline, not a forecast.</span> Every path drifts at
            the risk-free rate ({formatAnnualRate(rate)}), as in option pricing, so the spread comes from
            volatility alone. The stock&apos;s historical drift was{" "}
            <span className="font-semibold text-accent-text">{formatAnnualRate(muHistorical, { signed: true })}</span>.
          </p>
        ) : null}
      </Card>
    </div>
  );
}
