"use client";

import { DEMO_MODE } from "@/lib/api";
import { assessCoverage, COVERAGE_NOISE_NOTE, ordinalPercentile, summarizeCalibration, type Calibration } from "@/lib/backtest";
import { describeRateSource } from "@/lib/drift";
import {
  formatAnnualRate,
  formatDate,
  formatHorizon,
  formatInteger,
  formatMoney,
  formatMoneyRange,
  formatPercent,
  formatProbability,
} from "@/lib/format";
import type { BacktestSettings, RollingBacktestResponse, SingleBacktestResponse } from "@/lib/types";
import { CalibrationChart } from "./CalibrationChart";
import { FanChart } from "./FanChart";
import { Card, SectionTitle, cx } from "./ui";

function DemoNote() {
  if (!DEMO_MODE) return null;
  return (
    <p className="rounded-xl border border-dashed border-sand/25 px-4 py-2.5 text-center text-xs text-sand/70">
      Demo mode: showing a bundled sample backtest generated from synthetic prices, whatever ticker or date you pick.
    </p>
  );
}

/** Green "inside" / terracotta "outside" pill for a band check. */
export function BandBadge({ inside, band }: { inside: boolean; band: "50%" | "90%" }) {
  return (
    <span
      className={cx(
        "inline-flex items-center gap-1.5 rounded-full border px-3 py-1 text-[0.8125rem] font-semibold",
        inside ? "border-hit/40 bg-hit/10 text-hit" : "border-loss/45 bg-loss/10 text-loss",
      )}
    >
      <span aria-hidden className={cx("size-1.5 rounded-full", inside ? "bg-hit" : "bg-loss")} />
      {inside ? "Inside" : "Outside"} the {band} band
    </span>
  );
}

function VerdictBadge({ status, label, title }: { status: Calibration; label: string; title?: string }) {
  return (
    <span
      title={title}
      className={cx(
        "inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-semibold",
        status === "good" && "border-hit/40 bg-hit/10 text-hit",
        status === "over" && "border-loss/45 bg-loss/10 text-loss",
        status === "under" && "border-sand/30 bg-sand/8 text-sand/85",
      )}
    >
      {label}
    </span>
  );
}

function Header({
  ticker,
  name,
  currency,
  subtitle,
  right,
}: {
  ticker: string;
  name: string | null;
  currency: string | null;
  subtitle: React.ReactNode;
  right?: React.ReactNode;
}) {
  return (
    <Card as="section" aria-labelledby="bt-title" className="p-5 sm:p-7">
      <div className="flex flex-col gap-5 sm:flex-row sm:items-end sm:justify-between">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <span className="rounded-md border border-sand/20 bg-sand/8 px-2 py-0.5 text-xs font-semibold tracking-wider">
              {ticker}
            </span>
            {currency ? <span className="text-xs font-medium text-sand/55">{currency}</span> : null}
            <span className="rounded-md border border-accent/35 bg-accent/10 px-2 py-0.5 text-xs font-semibold text-accent-text">
              Backtest
            </span>
          </div>
          <h2 id="bt-title" className="mt-2.5 break-words text-2xl font-semibold tracking-tight sm:text-3xl">
            {name || ticker}
          </h2>
          <p className="mt-1.5 text-sm text-sand/65">{subtitle}</p>
        </div>
        {right ? <div className="sm:text-right">{right}</div> : null}
      </div>
    </Card>
  );
}

function RateNote({ settings }: { settings: BacktestSettings }) {
  if (settings.drift !== "risk_free" || !settings.rate_note) return null;
  return (
    <p className="rounded-xl border border-accent/30 bg-accent/[0.07] px-4 py-3 text-sm leading-relaxed text-sand/80">
      <span className="font-semibold text-sand">Risk-free drift in the past.</span> {settings.rate_note}
    </p>
  );
}

/** Plain-English notes on what a backtest can and can't tell you. */
export function BacktestExplainer() {
  return (
    <Card as="section" aria-labelledby="bt-explain-title" className="p-5 sm:p-7">
      <SectionTitle id="bt-explain-title" title="How to read a backtest" />
      <div className="mt-4 grid gap-5 text-sm leading-relaxed text-sand/70 md:grid-cols-3">
        <div>
          <h4 className="font-semibold text-sand">No peeking</h4>
          <p className="mt-1.5">
            Each forecast only uses prices from the lookback window that ends on its start date, exactly as if you had run
            the simulator that day. Then it is compared with what really happened next.
          </p>
        </div>
        <div>
          <h4 className="font-semibold text-sand">What calibration means</h4>
          <p className="mt-1.5">
            A calibrated model&apos;s 90% band should contain the real outcome about 9 times in 10, and its 50% band about
            half the time. Coverage well below 90% means the model was <span className="font-semibold text-sand">overconfident</span>:
            its bands were too narrow, typically because real returns have fat tails and volatility that comes in bursts,
            which GBM&apos;s normal returns and constant σ leave out.
          </p>
        </div>
        <div>
          <h4 className="font-semibold text-sand">What it can&apos;t tell you</h4>
          <p className="mt-1.5">
            A handful of start dates is a small sample, and overlapping windows share the same market moves. Good past
            calibration doesn&apos;t guarantee future accuracy: the next crash may look nothing like the last decade.
          </p>
        </div>
      </div>
    </Card>
  );
}

// --- single ------------------------------------------------------------------------------

export function SingleBacktestResults({ data }: { data: SingleBacktestResponse }) {
  const { metadata, parameters, settings, analysis, backtest: bt } = data;
  const currency = metadata.currency;
  const money = (v: number) => formatMoney(v, currency);
  const horizon = formatHorizon(settings.horizon);
  const fp = analysis.final_price;
  const riskFree = settings.drift === "risk_free";
  const snapped = settings.requested_start_date && settings.requested_start_date !== bt.start_date;

  const details: [string, string, string?][] = [
    ["Lookback window", `${formatDate(bt.lookback_start_date)} – ${formatDate(bt.start_date)}`, `${settings.lookback}, ${formatInteger(parameters.n_returns)} daily returns`],
    riskFree
      ? ["Drift μ used (annual)", formatAnnualRate(parameters.mu, { signed: true }), describeRateSource(settings.rate_source)]
      : ["Drift μ (annual)", formatAnnualRate(parameters.mu, { signed: true }), "From the lookback only"],
    ["Volatility σ (annual)", formatAnnualRate(parameters.sigma), "From the lookback only"],
    ["Simulations", formatInteger(settings.n_sims), `Seed ${settings.seed}`],
  ];

  return (
    <div className="grid gap-5 sm:gap-6">
      <DemoNote />
      <Header
        ticker={metadata.ticker}
        name={metadata.long_name}
        currency={currency}
        subtitle={
          <>
            Forecast from <time dateTime={bt.start_date}>{formatDate(bt.start_date)}</time> over {horizon}, compared with
            what happened by <time dateTime={bt.end_date}>{formatDate(bt.end_date)}</time>
            {riskFree ? " · risk-free drift" : ""}
          </>
        }
        right={
          <>
            <p className="text-xs font-medium uppercase tracking-[0.14em] text-sand/55">Start price</p>
            <p className="mt-1 text-3xl font-semibold tracking-tight sm:text-4xl">{money(parameters.S0)}</p>
            <p className="mt-1 text-sm text-sand/60">
              {snapped ? <>Last close on or before {formatDate(settings.requested_start_date!)}</> : "Close on the start date"}
            </p>
          </>
        }
      />

      {/* Result */}
      <Card as="section" aria-labelledby="bt-result-title" className="p-5 sm:p-7">
        <SectionTitle id="bt-result-title" title="Did the forecast contain what happened?" />
        <div className="mt-5 grid gap-6 sm:grid-cols-2 lg:grid-cols-[1fr_1fr_1.2fr]">
          <div>
            <p className="text-sm font-medium text-sand/70">Actual price on {formatDate(bt.end_date)}</p>
            <p className="mt-2 text-3xl font-semibold tracking-tight sm:text-[2rem]">{money(bt.actual_final)}</p>
            <p className={cx("mt-1.5 text-sm", bt.actual_return_pct < 0 ? "text-loss" : "text-sand/70")}>
              {formatPercent(bt.actual_return_pct, { signed: true })} from the start
            </p>
          </div>
          <div>
            <p className="text-sm font-medium text-sand/70">Percentile in the forecast</p>
            <p className="mt-2 text-3xl font-semibold tracking-tight text-accent-text sm:text-[2rem]">
              {ordinalPercentile(bt.percentile_rank)}
            </p>
            <p className="mt-1.5 text-sm text-sand/60">
              {formatProbability(bt.percentile_rank / 100, 0)} of simulated paths ended below the actual price.
            </p>
          </div>
          <div className="sm:col-span-2 lg:col-span-1">
            <p className="text-sm font-medium text-sand/70">Band checks at the end</p>
            <div className="mt-2.5 flex flex-wrap gap-2">
              <BandBadge inside={bt.inside_50} band="50%" />
              <BandBadge inside={bt.inside_90} band="90%" />
            </div>
            <dl className="mt-3 grid grid-cols-[auto_1fr] gap-x-4 gap-y-1 text-sm">
              <dt className="text-sand/60">50% band</dt>
              <dd className="text-right font-medium">
                {money(fp.p25)} – {money(fp.p75)}
              </dd>
              <dt className="text-sand/60">90% band</dt>
              <dd className="text-right font-medium">
                {money(fp.p5)} – {money(fp.p95)}
              </dd>
              <dt className="text-sand/60">Forecast median</dt>
              <dd className="text-right font-medium">{money(fp.median)}</dd>
            </dl>
          </div>
        </div>
      </Card>

      {/* Fan chart with the actual path */}
      <Card as="section" aria-labelledby="bt-fan-title" className="p-5 sm:p-7">
        <SectionTitle
          id="bt-fan-title"
          title="Forecast vs what actually happened"
          description={`The fan is what the model expected on ${formatDate(bt.start_date)}, using only prices up to that day. The sand line is the real price over the next ${horizon}.`}
        />
        <div className="mt-5 -mx-1 sm:mx-0">
          <FanChart data={data} actual={bt.actual_path} />
        </div>
      </Card>

      {/* Model details */}
      <Card as="section" aria-labelledby="bt-model-title" className="p-5 sm:p-7">
        <SectionTitle id="bt-model-title" title="Model as of the start date" />
        <dl className="mt-5 grid grid-cols-2 gap-px overflow-hidden rounded-xl border border-sand/10 bg-sand/10 lg:grid-cols-4">
          {details.map(([term, value, hint]) => (
            <div key={term} className="min-w-0 bg-forest-900 p-4">
              <dt className="text-xs font-medium text-sand/60">{term}</dt>
              <dd className="mt-1.5 text-base font-semibold tracking-tight sm:text-lg">{value}</dd>
              {hint ? <dd className="mt-1 text-xs text-sand/50">{hint}</dd> : null}
            </div>
          ))}
        </dl>
        {riskFree ? (
          <div className="mt-4">
            <RateNote settings={settings} />
          </div>
        ) : null}
      </Card>

      <BacktestExplainer />
    </div>
  );
}

// --- rolling -----------------------------------------------------------------------------

function CoverageCard({
  label,
  coverage,
  nominal,
  nWindows,
}: {
  label: string;
  coverage: number;
  nominal: 0.5 | 0.9;
  nWindows: number;
}) {
  const verdict = assessCoverage(coverage, nominal, nWindows);
  return (
    <Card className="flex flex-col p-5">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="text-sm font-medium text-sand/70">{label}</p>
        <VerdictBadge {...verdict} title={COVERAGE_NOISE_NOTE} />
      </div>
      <p
        className={cx(
          "mt-3 text-3xl font-semibold tracking-tight sm:text-[2rem]",
          verdict.status === "over" ? "text-loss" : verdict.status === "good" ? "text-hit" : "text-sand",
        )}
      >
        {formatProbability(coverage, 0)}
      </p>
      <p className="mt-2 text-[0.8125rem] leading-relaxed text-sand/60">
        of actual prices ended inside it. Ideal: {formatProbability(nominal, 0)} ±{" "}
        {formatProbability(2 * verdict.standardError, 0)} (2 standard errors for {nWindows} windows).
      </p>
      <p className="mt-1 text-xs leading-relaxed text-sand/50">{COVERAGE_NOISE_NOTE}</p>
    </Card>
  );
}

export function RollingBacktestResults({ data }: { data: RollingBacktestResponse }) {
  const { metadata, settings, summary, windows } = data;
  const currency = metadata.currency;
  const money = (v: number) => formatMoney(v, currency);
  const horizon = formatHorizon(settings.horizon);
  const rankOff = Math.abs(summary.mean_percentile_rank - 50);

  return (
    <div className="grid gap-5 sm:gap-6">
      <DemoNote />
      <Header
        ticker={metadata.ticker}
        name={metadata.long_name}
        currency={currency}
        subtitle={
          <>
            {formatInteger(summary.n_windows)} forecasts from {formatDate(summary.first_start_date)} to{" "}
            {formatDate(summary.last_start_date)} · {horizon} horizon · {settings.lookback} lookback ·{" "}
            {formatInteger(settings.n_sims)} paths each{settings.drift === "risk_free" ? " · risk-free drift" : ""}
          </>
        }
      />

      <section aria-label="Calibration summary" className="grid grid-cols-1 gap-4 min-[480px]:grid-cols-2 lg:grid-cols-4">
        <CoverageCard label="90% band coverage" coverage={summary.coverage_90} nominal={0.9} nWindows={summary.n_windows} />
        <CoverageCard label="50% band coverage" coverage={summary.coverage_50} nominal={0.5} nWindows={summary.n_windows} />
        <Card className="flex flex-col p-5">
          <p className="text-sm font-medium text-sand/70">Mean percentile</p>
          <p className="mt-3 text-3xl font-semibold tracking-tight text-accent-text sm:text-[2rem]">
            {summary.mean_percentile_rank.toFixed(0)}
          </p>
          <p className="mt-2 text-[0.8125rem] leading-relaxed text-sand/60">
            Ideal: 50.{" "}
            {rankOff < 8
              ? "No strong lean up or down."
              : summary.mean_percentile_rank > 50
                ? "Prices tended to beat the forecast."
                : "Prices tended to fall short of the forecast."}
          </p>
        </Card>
        <Card className="flex flex-col p-5">
          <p className="text-sm font-medium text-sand/70">Misses beyond the 90% band</p>
          <p className="mt-3 text-lg font-semibold leading-snug tracking-tight sm:text-xl">
            <span className="text-loss">{formatProbability(summary.below_p5, 0)}</span> below,{" "}
            <span className="text-sand">{formatProbability(summary.above_p95, 0)}</span> above
          </p>
          <p className="mt-2 text-[0.8125rem] leading-relaxed text-sand/60">
            Under the 5th / over the 95th percentile. Ideal: 5% each.
          </p>
        </Card>
      </section>

      <p className="rounded-xl border border-sand/12 bg-forest-900/60 px-4 py-3 text-sm leading-relaxed text-sand/80">
        {summarizeCalibration(summary)}
      </p>

      <div className="grid gap-5 sm:gap-6 lg:grid-cols-[minmax(0,1.15fr)_minmax(0,1fr)]">
        <Card as="section" aria-labelledby="calib-title" className="p-5 sm:p-7">
          <SectionTitle
            id="calib-title"
            title="Calibration histogram"
            description="Where each actual final price fell within its own forecast, in percentile bins. A well-calibrated model gives a flat histogram; tall outer bars mean the real outcomes kept escaping the bands."
          />
          <div className="mt-5 -mx-1 sm:mx-0">
            <CalibrationChart summary={summary} />
          </div>
        </Card>

        <Card as="section" aria-labelledby="windows-title" className="flex min-w-0 flex-col p-5 sm:p-7">
          <SectionTitle
            id="windows-title"
            title="Every forecast"
            description="Predicted 90% range at the end of each window vs the actual price."
          />
          <div className="mt-4 max-h-[26rem] overflow-auto rounded-xl border border-sand/10" tabIndex={0} aria-label="Backtest windows, scrollable">
            <table className="w-full text-[0.8125rem] sm:text-sm">
              <caption className="sr-only">Start date, predicted 90% range, actual final price and whether it was inside the band</caption>
              <thead className="sticky top-0 bg-forest-950/95 backdrop-blur">
                <tr className="text-left text-xs uppercase tracking-wider text-sand/50">
                  <th scope="col" className="px-1.5 py-2 sm:px-3 font-medium">Start</th>
                  <th scope="col" className="px-1.5 py-2 sm:px-3 text-right font-medium">Predicted 90%</th>
                  <th scope="col" className="px-1.5 py-2 sm:px-3 text-right font-medium">Actual</th>
                  <th scope="col" className="px-1.5 py-2 sm:px-3 text-center font-medium">In 90%</th>
                </tr>
              </thead>
              <tbody>
                {windows.map((w) => (
                  <tr key={w.start_date} className="border-t border-sand/10">
                    <th scope="row" className="whitespace-nowrap px-1.5 py-2 sm:px-3 text-left font-medium text-sand/80">
                      <time dateTime={w.start_date}>{formatDate(w.start_date)}</time>
                    </th>
                    <td className="whitespace-nowrap px-1.5 py-2 sm:px-3 text-right text-sand/75">
                      {formatMoneyRange(w.p5, w.p95, currency)}
                    </td>
                    <td className={cx("whitespace-nowrap px-1.5 py-2 sm:px-3 text-right font-semibold", !w.inside_90 && "text-loss")}>
                      {money(w.actual_final)}
                    </td>
                    <td className="px-1.5 py-2 sm:px-3 text-center">
                      <span
                        className={cx(
                          "inline-block rounded-full px-2 py-0.5 text-xs font-semibold",
                          w.inside_90 ? "bg-hit/12 text-hit" : "bg-loss/12 text-loss",
                        )}
                      >
                        {w.inside_90 ? "Yes" : "No"}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      </div>

      <RateNote settings={settings} />
      <BacktestExplainer />
    </div>
  );
}
