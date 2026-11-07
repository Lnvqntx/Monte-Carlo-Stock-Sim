"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { SimulationError, backtest, simulate } from "@/lib/api";
import {
  DEFAULT_APP_MODE,
  DEFAULT_BACKTEST_MODE,
  clampStartDate,
  defaultStartDate,
  localToday,
  readBacktestParams,
  validateStartDate,
  writeBacktestParams,
} from "@/lib/backtest";
import { friendlyError, type FriendlyError } from "@/lib/errors";
import { DEFAULT_DRIFT, parseRatePercent, readDriftParams, writeDriftParams } from "@/lib/drift";
import { DEFAULTS, TICKER_RE, isHorizon, normalizeTicker } from "@/lib/options";
import { isRollingBacktest, type BacktestResponse, type SimulateResponse } from "@/lib/types";
import { RollingBacktestResults, SingleBacktestResults } from "./BacktestResults";
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
  mode: DEFAULT_APP_MODE,
  backtest: DEFAULT_BACKTEST_MODE,
  startDate: "",
};

/** The start date actually used: the typed one, or the default for the horizon. */
function effectiveStart(form: FormState, today: string): string {
  return form.startDate || defaultStartDate(form.horizon, today);
}

function validate(form: FormState, today: string): FieldErrors {
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
  if (form.mode === "backtest" && form.backtest === "single") {
    const err = validateStartDate(effectiveStart(form, today), form.horizon, today);
    if (err) errors.startDate = err;
  }
  return errors;
}

/**
 * Keep ticker, horizon and (when not the default) drift + rate and the backtest mode, type and start
 * date in the URL so results are shareable. The effective start date is written, so a shared single
 * backtest doesn't shift as days pass.
 */
function writeUrl(ticker: string, form: FormState, today: string) {
  const params = new URLSearchParams(window.location.search);
  params.set("ticker", ticker);
  params.set("horizon", form.horizon);
  writeDriftParams(params, { drift: form.drift, rate: form.rate });
  writeBacktestParams(params, { mode: form.mode, backtest: form.backtest, startDate: effectiveStart(form, today) });
  window.history.replaceState(null, "", `${window.location.pathname}?${params.toString()}`);
}

export function Simulator() {
  const [form, setForm] = useState<FormState>(INITIAL_FORM);
  const [fieldErrors, setFieldErrors] = useState<FieldErrors>({});
  // One result per mode, so switching modes shows that mode's last result (or its empty state).
  const [result, setResult] = useState<SimulateResponse | null>(null);
  const [btResult, setBtResult] = useState<BacktestResponse | null>(null);
  const [today, setToday] = useState("");
  const todayRef = useRef("");
  const [error, setError] = useState<FriendlyError | null>(null);
  const [loading, setLoading] = useState(false);
  const abortRef = useRef<AbortController | null>(null);
  const resultsRef = useRef<HTMLDivElement>(null);
  const lastFormRef = useRef<FormState>(INITIAL_FORM);

  const run = useCallback(async (next: FormState, { scroll = true } = {}) => {
    const now = todayRef.current || localToday();
    const errors = validate(next, now);
    setFieldErrors(errors);
    if (Object.keys(errors).length > 0) return;

    const ticker = normalizeTicker(next.ticker);
    lastFormRef.current = next;
    writeUrl(ticker, next, now);

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
    const common = {
      ticker,
      horizon: next.horizon,
      lookback: next.lookback,
      seed: Number(next.seed),
      drift: next.drift,
      ...(rate?.ok && rate.rate !== undefined ? { risk_free_rate: rate.rate } : {}),
    };
    const isBacktest = next.mode === "backtest";
    try {
      if (isBacktest) {
        const data = await backtest(
          next.backtest === "rolling"
            ? { ...common, mode: "rolling" }
            : { ...common, mode: "single", start_date: effectiveStart(next, now), n_sims: next.nSims },
          controller.signal,
        );
        setBtResult(data);
      } else {
        setResult(await simulate({ ...common, n_sims: next.nSims }, controller.signal));
      }
    } catch (err) {
      if ((err as Error)?.name === "AbortError") return;
      const e = err instanceof SimulationError ? err : new SimulationError("internal_error", String(err));
      if (isBacktest) setBtResult(null);
      else setResult(null);
      setError(friendlyError(e.code, { ticker, detail: e.message, backtest: isBacktest }));
    } finally {
      if (abortRef.current === controller) {
        abortRef.current = null;
        setLoading(false);
      }
    }
  }, []);

  // Auto-run when the page opens with ?ticker=...&horizon=...[&drift=risk_free&rate=4.5]
  // [&mode=backtest&test=rolling | &start=2025-05-01]
  useEffect(() => {
    const now = localToday();
    todayRef.current = now;
    const params = new URLSearchParams(window.location.search);
    const fromUrl = readBacktestParams(params);
    queueMicrotask(() => {
      setToday(now);
      if (fromUrl.mode === "backtest") setForm((f) => ({ ...f, ...fromUrl }));
    });
    const ticker = normalizeTicker(params.get("ticker") ?? "");
    if (!ticker) return;
    const horizonParam = params.get("horizon")?.toLowerCase();
    const initial: FormState = {
      ...INITIAL_FORM,
      ticker,
      horizon: isHorizon(horizonParam) ? horizonParam : DEFAULTS.horizon,
      ...readDriftParams(params),
      ...fromUrl,
    };
    queueMicrotask(() => {
      setForm(initial);
      void run(initial, { scroll: false });
    });
    return () => abortRef.current?.abort();
  }, [run]);

  const update = (patch: Partial<FormState>) => {
    setForm((f) => {
      const next = { ...f, ...patch };
      // A start date that no longer leaves room for the new horizon moves back to the latest valid one.
      if (patch.horizon !== undefined && next.startDate && today) {
        next.startDate = clampStartDate(next.startDate, next.horizon, today);
      }
      return next;
    });
    if ((patch.startDate !== undefined || patch.horizon !== undefined || patch.backtest !== undefined) && fieldErrors.startDate) {
      setFieldErrors((e) => ({ ...e, startDate: undefined }));
    }
    if (patch.mode !== undefined && patch.mode !== form.mode) setError(null);
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
        today={today}
      />

      <div ref={resultsRef} className="mt-6 scroll-mt-6 sm:mt-8" aria-live="polite" aria-busy={loading}>
        {loading ? (
          <>
            <p className="sr-only">{form.mode === "backtest" ? "Running backtest…" : "Running simulation…"}</p>
            <ResultsSkeleton />
          </>
        ) : error ? (
          <ErrorAlert error={error} onRetry={() => void run(lastFormRef.current)} />
        ) : form.mode === "backtest" ? (
          btResult ? (
            isRollingBacktest(btResult) ? (
              <RollingBacktestResults data={btResult} />
            ) : (
              <SingleBacktestResults data={btResult} />
            )
          ) : (
            <EmptyState mode="backtest" />
          )
        ) : result ? (
          <Results data={result} />
        ) : (
          <EmptyState />
        )}
      </div>
    </section>
  );
}
