"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { SimulationError, simulate } from "@/lib/api";
import { friendlyError, type FriendlyError } from "@/lib/errors";
import { DEFAULT_DRIFT, parseRatePercent, readDriftParams, writeDriftParams } from "@/lib/drift";
import { DEFAULTS, TICKER_RE, isHorizon, normalizeTicker } from "@/lib/options";
import type { SimulateResponse } from "@/lib/types";
import { InputCard, type FieldErrors, type FormState } from "./InputCard";
import { Results } from "./Results";
import { EmptyState, ErrorAlert, ResultsSkeleton } from "./States";

const INITIAL_FORM: FormState = {
  ticker: "",
  horizon: DEFAULTS.horizon,
  lookback: DEFAULTS.lookback,
  nSims: DEFAULTS.nSims,
  seed: String(DEFAULTS.seed),
  drift: DEFAULT_DRIFT,
  rate: "",
};

function validate(form: FormState): FieldErrors {
  const errors: FieldErrors = {};
  const ticker = normalizeTicker(form.ticker);
  if (!ticker) errors.ticker = "Enter a ticker symbol, e.g. AAPL or RELIANCE.NS.";
  else if (!TICKER_RE.test(ticker)) errors.ticker = "Tickers can only contain letters, digits and . - ^ =";
  if (!/^\d+$/.test(form.seed.trim())) errors.seed = "Seed must be a whole number of 0 or more.";
  // The rate only matters with risk-free drift, so don't block historical runs on it.
  if (form.drift === "risk_free") {
    const rate = parseRatePercent(form.rate);
    if (!rate.ok) errors.rate = rate.error;
  }
  return errors;
}

/** Keep ticker, horizon and (when not the default) drift + rate in the URL so results are shareable. */
function writeUrl(ticker: string, form: FormState) {
  const params = new URLSearchParams(window.location.search);
  params.set("ticker", ticker);
  params.set("horizon", form.horizon);
  writeDriftParams(params, { drift: form.drift, rate: form.rate });
  window.history.replaceState(null, "", `${window.location.pathname}?${params.toString()}`);
}

export function Simulator() {
  const [form, setForm] = useState<FormState>(INITIAL_FORM);
  const [fieldErrors, setFieldErrors] = useState<FieldErrors>({});
  const [result, setResult] = useState<SimulateResponse | null>(null);
  const [error, setError] = useState<FriendlyError | null>(null);
  const [loading, setLoading] = useState(false);
  const abortRef = useRef<AbortController | null>(null);
  const resultsRef = useRef<HTMLDivElement>(null);
  const lastFormRef = useRef<FormState>(INITIAL_FORM);

  const run = useCallback(async (next: FormState, { scroll = true } = {}) => {
    const errors = validate(next);
    setFieldErrors(errors);
    if (Object.keys(errors).length > 0) return;

    const ticker = normalizeTicker(next.ticker);
    lastFormRef.current = next;
    writeUrl(ticker, next);

    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;

    setLoading(true);
    setError(null);
    if (scroll) {
      requestAnimationFrame(() => {
        const el = resultsRef.current;
        if (el && el.getBoundingClientRect().top > window.innerHeight * 0.6) {
          el.scrollIntoView({ behavior: "smooth", block: "start" });
        }
      });
    }

    const rate = next.drift === "risk_free" ? parseRatePercent(next.rate) : null;
    try {
      const data = await simulate(
        {
          ticker,
          horizon: next.horizon,
          lookback: next.lookback,
          n_sims: next.nSims,
          seed: Number(next.seed),
          drift: next.drift,
          ...(rate?.ok && rate.rate !== undefined ? { risk_free_rate: rate.rate } : {}),
        },
        controller.signal,
      );
      setResult(data);
    } catch (err) {
      if ((err as Error)?.name === "AbortError") return;
      const e = err instanceof SimulationError ? err : new SimulationError("internal_error", String(err));
      setResult(null);
      setError(friendlyError(e.code, { ticker, detail: e.message }));
    } finally {
      if (abortRef.current === controller) {
        abortRef.current = null;
        setLoading(false);
      }
    }
  }, []);

  // Auto-run when the page opens with ?ticker=...&horizon=...[&drift=risk_free&rate=4.5]
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const ticker = normalizeTicker(params.get("ticker") ?? "");
    if (!ticker) return;
    const horizonParam = params.get("horizon")?.toLowerCase();
    const initial: FormState = {
      ...INITIAL_FORM,
      ticker,
      horizon: isHorizon(horizonParam) ? horizonParam : DEFAULTS.horizon,
      ...readDriftParams(params),
    };
    queueMicrotask(() => {
      setForm(initial);
      void run(initial, { scroll: false });
    });
    return () => abortRef.current?.abort();
  }, [run]);

  const update = (patch: Partial<FormState>) => {
    setForm((f) => ({ ...f, ...patch }));
    if (patch.ticker !== undefined && fieldErrors.ticker) setFieldErrors((e) => ({ ...e, ticker: undefined }));
    if (patch.seed !== undefined && fieldErrors.seed) setFieldErrors((e) => ({ ...e, seed: undefined }));
    if ((patch.rate !== undefined || patch.drift !== undefined) && fieldErrors.rate) {
      setFieldErrors((e) => ({ ...e, rate: undefined }));
    }
  };

  const pickExample = (ticker: string) => {
    const next = { ...form, ticker };
    setForm(next);
    void run(next);
  };

  return (
    <section id="simulator" aria-label="Simulator" className="mx-auto max-w-6xl scroll-mt-6 px-4 sm:px-6">
      <InputCard
        form={form}
        onChange={update}
        onSubmit={() => void run(form)}
        onPickExample={pickExample}
        loading={loading}
        fieldErrors={fieldErrors}
      />

      <div ref={resultsRef} className="mt-6 scroll-mt-6 sm:mt-8" aria-live="polite" aria-busy={loading}>
        {loading ? (
          <>
            <p className="sr-only">Running simulation…</p>
            <ResultsSkeleton />
          </>
        ) : error ? (
          <ErrorAlert error={error} onRetry={() => void run(lastFormRef.current)} />
        ) : result ? (
          <Results data={result} />
        ) : (
          <EmptyState />
        )}
      </div>
    </section>
  );
}
