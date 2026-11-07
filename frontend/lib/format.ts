/** Number, money, date and label formatting. Pure functions, unit-tested in lib/format.test.ts. */

const LOCALE_BY_CURRENCY: Record<string, string> = { INR: "en-IN" };

function localeFor(currency: string | null | undefined): string {
  return (currency && LOCALE_BY_CURRENCY[currency.toUpperCase()]) || "en-US";
}

function safeFormat(value: number, locale: string, options: Intl.NumberFormatOptions): string {
  try {
    return new Intl.NumberFormat(locale, options).format(value);
  } catch {
    // Unknown currency code from the provider: fall back to a plain number with the code.
    const { currency } = options;
    const n = new Intl.NumberFormat(locale, {
      notation: options.notation,
      minimumFractionDigits: options.minimumFractionDigits,
      maximumFractionDigits: options.maximumFractionDigits,
    }).format(value);
    return currency ? `${n} ${currency}` : n;
  }
}

/** Full-precision money, e.g. 1234.5 USD -> "$1,234.50", INR -> "₹1,234.50". */
export function formatMoney(value: number, currency: string | null | undefined): string {
  if (!Number.isFinite(value)) return "—";
  const options: Intl.NumberFormatOptions = { minimumFractionDigits: 2, maximumFractionDigits: 2 };
  if (!currency) return safeFormat(value, "en-US", options);
  return safeFormat(value, localeFor(currency), { ...options, style: "currency", currency });
}

/** Short money for chart axes: no decimals from 100 up, compact from 100,000 up. */
export function formatMoneyCompact(value: number, currency: string | null | undefined): string {
  if (!Number.isFinite(value)) return "—";
  const abs = Math.abs(value);
  const options: Intl.NumberFormatOptions =
    abs >= 100_000
      ? { notation: "compact", maximumFractionDigits: 1, minimumFractionDigits: 0 }
      : { maximumFractionDigits: abs >= 100 ? 0 : 2, minimumFractionDigits: 0 };
  if (!currency) return safeFormat(value, "en-US", options);
  return safeFormat(value, localeFor(currency), { ...options, style: "currency", currency });
}

/** Round half away from zero, ignoring binary noise (0.2365 * 100 = 23.649999... rounds to 23.7). */
function roundHalfUp(value: number, digits: number): number {
  const f = 10 ** digits;
  const scaled = Number((Math.abs(value) * f).toPrecision(12));
  return (Math.sign(value) * Math.round(scaled)) / f;
}

/** A value already in percent units: 12.345 -> "12.3%", signed -> "+12.3%". */
export function formatPercent(value: number, { signed = false, digits = 1 } = {}): string {
  if (!Number.isFinite(value)) return "—";
  const rounded = roundHalfUp(value, digits);
  const body = `${Math.abs(rounded).toFixed(digits)}%`;
  if (rounded === 0) return signed ? `${(0).toFixed(digits)}%` : body;
  if (rounded < 0) return `−${body}`;
  return signed ? `+${body}` : body;
}

/** A probability 0-1 as a percentage: 0.2365 -> "23.7%". */
export function formatProbability(p: number, digits = 1): string {
  if (!Number.isFinite(p)) return "—";
  return formatPercent(p * 100, { digits });
}

/** A fraction (0.316) as an annual percentage: "31.6%". */
export function formatAnnualRate(rate: number, { signed = false } = {}): string {
  return formatPercent(rate * 100, { signed, digits: 1 });
}

export function formatInteger(value: number): string {
  if (!Number.isFinite(value)) return "—";
  return new Intl.NumberFormat("en-US", { maximumFractionDigits: 0 }).format(value);
}

/** "2026-11-06" -> "Nov 6, 2026" (read as a calendar date, independent of time zone). */
export function formatDate(iso: string): string {
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(iso ?? "");
  if (!m) return iso ?? "";
  const date = new Date(Date.UTC(Number(m[1]), Number(m[2]) - 1, Number(m[3])));
  return new Intl.DateTimeFormat("en-US", {
    year: "numeric",
    month: "short",
    day: "numeric",
    timeZone: "UTC",
  }).format(date);
}

const UNIT_NAMES: Record<string, [string, string]> = {
  d: ["day", "days"],
  w: ["week", "weeks"],
  m: ["month", "months"],
  y: ["year", "years"],
};

/** "6m" -> "6 months", "1y" -> "1 year", "6mo" -> "6 months". */
export function formatHorizon(label: string): string {
  const m = /^(\d+)\s*(mo|[dwmy])$/i.exec((label ?? "").trim());
  if (!m) return label;
  const n = Number(m[1]);
  const unit = m[2].toLowerCase() === "mo" ? "m" : m[2].toLowerCase();
  const [one, many] = UNIT_NAMES[unit];
  return `${n} ${n === 1 ? one : many}`;
}

export interface VarDisplay {
  /** True when the 5th percentile ends above today's price. */
  noLoss: boolean;
  /** "16.9%" or "No loss at 95% confidence". */
  text: string;
}

/** 95% VaR is a loss as % of today's price; negative means no loss at 95% confidence. */
export function describeVar(varPct: number): VarDisplay {
  if (!Number.isFinite(varPct) || varPct <= 0) {
    return { noLoss: true, text: "No loss at 95% confidence" };
  }
  return { noLoss: false, text: formatPercent(varPct, { digits: 1 }) };
}
