"use client";

import type { FormEvent } from "react";
import { DRIFTS } from "@/lib/drift";
import { EXAMPLE_TICKERS, HORIZONS, LOOKBACKS, SIM_COUNTS, type HorizonValue } from "@/lib/options";
import { formatInteger } from "@/lib/format";
import type { DriftModel, Lookback } from "@/lib/types";
import { ChevronIcon, SpinnerIcon } from "./icons";
import { Card, Segmented, cx } from "./ui";

export interface FormState {
  ticker: string;
  horizon: HorizonValue;
  lookback: Lookback;
  nSims: number;
  seed: string;
  drift: DriftModel;
  /** Risk-free rate override in percent as typed; "" = server default. */
  rate: string;
}

export interface FieldErrors {
  ticker?: string;
  seed?: string;
  rate?: string;
}

export function InputCard({
  form,
  onChange,
  onSubmit,
  onPickExample,
  loading,
  fieldErrors,
}: {
  form: FormState;
  onChange: (patch: Partial<FormState>) => void;
  onSubmit: () => void;
  onPickExample: (ticker: string) => void;
  loading: boolean;
  fieldErrors: FieldErrors;
}) {
  const handleSubmit = (e: FormEvent) => {
    e.preventDefault();
    onSubmit();
  };

  return (
    <Card as="section" aria-labelledby="sim-form-title" className="p-5 sm:p-7">
      <h2 id="sim-form-title" className="sr-only">
        Simulation settings
      </h2>
      <form onSubmit={handleSubmit} noValidate className="grid gap-7 lg:grid-cols-[minmax(0,1.25fr)_minmax(0,1fr)] lg:gap-10">
        {/* Ticker */}
        <div className="min-w-0">
          <label htmlFor="ticker" className="text-sm font-medium text-sand/90">
            Stock ticker
          </label>
          <input
            id="ticker"
            name="ticker"
            type="text"
            inputMode="text"
            autoComplete="off"
            autoCapitalize="characters"
            autoCorrect="off"
            spellCheck={false}
            maxLength={20}
            placeholder="e.g. AAPL or RELIANCE.NS"
            value={form.ticker}
            onChange={(e) => onChange({ ticker: e.target.value.toUpperCase() })}
            aria-invalid={fieldErrors.ticker ? true : undefined}
            aria-describedby={cx("ticker-hint", fieldErrors.ticker && "ticker-error") || undefined}
            className={cx(
              "mt-2 block h-14 w-full rounded-xl border bg-forest-950/60 px-4 text-xl font-semibold tracking-wide text-sand placeholder:text-base placeholder:font-normal placeholder:tracking-normal placeholder:text-sand/45",
              "transition-colors focus:border-accent-text focus:outline-none focus-visible:outline-none focus:ring-4 focus:ring-accent/25",
              fieldErrors.ticker ? "border-sand/60" : "border-sand/15 hover:border-sand/30",
            )}
          />
          {fieldErrors.ticker ? (
            <p id="ticker-error" className="mt-2 text-sm font-medium text-sand">
              {fieldErrors.ticker}
            </p>
          ) : null}
          <p id="ticker-hint" className="mt-2 text-sm text-sand/60">
            Indian stocks need <span className="font-semibold text-sand/85">.NS</span> (NSE) or{" "}
            <span className="font-semibold text-sand/85">.BO</span> (BSE), e.g. TCS.NS.
          </p>

          <div className="mt-5">
            <p id="examples-label" className="text-xs font-medium uppercase tracking-[0.14em] text-sand/50">
              Try an example
            </p>
            <ul aria-labelledby="examples-label" className="mt-2.5 flex flex-wrap gap-2">
              {EXAMPLE_TICKERS.map((t) => (
                <li key={t}>
                  <button
                    type="button"
                    disabled={loading}
                    onClick={() => onPickExample(t)}
                    aria-pressed={form.ticker === t}
                    className={cx(
                      "rounded-full border px-3 py-1.5 text-[0.8125rem] font-medium transition-colors disabled:cursor-not-allowed disabled:opacity-60",
                      form.ticker === t
                        ? "border-sand/60 bg-sand/12 text-sand"
                        : "border-sand/15 text-sand/75 hover:border-sand/35 hover:bg-sand/5 hover:text-sand",
                    )}
                  >
                    {t}
                  </button>
                </li>
              ))}
            </ul>
          </div>
        </div>

        {/* Horizon, advanced, submit */}
        <div className="flex min-w-0 flex-col gap-5">
          <Segmented
            name="horizon"
            legend="Forecast horizon"
            options={HORIZONS.map((h) => ({ value: h.value, label: h.label, title: h.long }))}
            value={form.horizon}
            onChange={(horizon) => onChange({ horizon })}
          />

          <div>
            <Segmented
              name="drift"
              legend="Drift"
              size="sm"
              options={DRIFTS}
              value={form.drift}
              onChange={(drift) => onChange({ drift })}
              describedBy="drift-hint"
            />
            <p id="drift-hint" className="mt-2 text-xs leading-relaxed text-sand/55">
              Historical uses the stock&apos;s past trend; risk-free grows at the T-bill rate, a neutral baseline.
            </p>
          </div>

          <details className="group rounded-xl border border-sand/12 bg-forest-950/30" open={Boolean(fieldErrors.seed || fieldErrors.rate) || undefined}>
            <summary className="flex cursor-pointer items-center justify-between gap-3 rounded-xl px-4 py-3 text-sm font-medium text-sand/90 hover:text-sand">
              <span>Advanced</span>
              <span className="flex min-w-0 items-center gap-2 text-xs font-normal text-sand/55">
                <span className="truncate">
                  {form.lookback} lookback · {formatInteger(form.nSims)} sims · seed {form.seed || "–"}
                  {form.drift === "risk_free" && form.rate.trim() ? ` · rate ${form.rate.trim().replace(/%$/, "")}%` : ""}
                </span>
                <ChevronIcon className="size-4 shrink-0 transition-transform group-open:rotate-180" />
              </span>
            </summary>
            <div className="grid gap-5 border-t border-sand/10 px-4 pb-4 pt-4">
              <Segmented
                name="lookback"
                legend="History lookback"
                size="sm"
                options={LOOKBACKS}
                value={form.lookback}
                onChange={(lookback) => onChange({ lookback })}
              />
              <Segmented
                name="n_sims"
                legend="Simulations"
                size="sm"
                options={SIM_COUNTS.map((n) => ({ value: n, label: formatInteger(n) }))}
                value={form.nSims}
                onChange={(nSims) => onChange({ nSims })}
              />
              <div>
                <label htmlFor="seed" className="text-sm font-medium text-sand/90">
                  Random seed
                </label>
                <input
                  id="seed"
                  name="seed"
                  type="number"
                  inputMode="numeric"
                  min={0}
                  step={1}
                  value={form.seed}
                  onChange={(e) => onChange({ seed: e.target.value })}
                  aria-invalid={fieldErrors.seed ? true : undefined}
                  aria-describedby={fieldErrors.seed ? "seed-error seed-hint" : "seed-hint"}
                  className={cx(
                    "mt-2 block h-11 w-full rounded-xl border bg-forest-950/60 px-3.5 text-sand transition-colors focus:border-accent-text focus:outline-none focus:ring-4 focus:ring-accent/25 focus-visible:outline-none",
                    fieldErrors.seed ? "border-sand/60" : "border-sand/15 hover:border-sand/30",
                  )}
                />
                {fieldErrors.seed ? (
                  <p id="seed-error" className="mt-2 text-sm font-medium text-sand">
                    {fieldErrors.seed}
                  </p>
                ) : null}
                <p id="seed-hint" className="mt-2 text-xs text-sand/55">
                  Same seed and settings give the same result.
                </p>
              </div>
              <div>
                <label htmlFor="rate" className="text-sm font-medium text-sand/90">
                  Risk-free rate %{" "}
                  <span className="font-normal text-sand/50">(optional)</span>
                </label>
                <div className="relative mt-2">
                  <input
                    id="rate"
                    name="rate"
                    type="text"
                    inputMode="decimal"
                    autoComplete="off"
                    placeholder="Default"
                    value={form.rate}
                    onChange={(e) => onChange({ rate: e.target.value })}
                    aria-invalid={fieldErrors.rate ? true : undefined}
                    aria-describedby={fieldErrors.rate ? "rate-error rate-hint" : "rate-hint"}
                    className={cx(
                      "block h-11 w-full rounded-xl border bg-forest-950/60 pl-3.5 pr-9 text-sand placeholder:text-sand/40 transition-colors focus:border-accent-text focus:outline-none focus:ring-4 focus:ring-accent/25 focus-visible:outline-none",
                      fieldErrors.rate ? "border-sand/60" : "border-sand/15 hover:border-sand/30",
                    )}
                  />
                  <span aria-hidden className="pointer-events-none absolute inset-y-0 right-3.5 flex items-center text-sm text-sand/50">
                    %
                  </span>
                </div>
                {fieldErrors.rate ? (
                  <p id="rate-error" className="mt-2 text-sm font-medium text-sand">
                    {fieldErrors.rate}
                  </p>
                ) : null}
                <p id="rate-hint" className="mt-2 text-xs text-sand/55">
                  Used only with risk-free drift. Blank uses the current T-bill rate for the stock&apos;s currency.
                </p>
              </div>
            </div>
          </details>

          <button
            type="submit"
            disabled={loading}
            className="mt-auto inline-flex h-14 w-full items-center justify-center gap-2.5 rounded-xl bg-accent px-6 text-[1.1875rem] font-bold text-white shadow-[0_10px_30px_-10px_rgb(139_92_246/0.8)] transition-[background-color,transform] hover:bg-accent-strong active:scale-[0.99] disabled:cursor-not-allowed disabled:opacity-75"
          >
            {loading ? (
              <>
                <SpinnerIcon className="size-5 animate-spin" />
                Simulating…
              </>
            ) : (
              "Run simulation"
            )}
          </button>
        </div>
      </form>
    </Card>
  );
}
