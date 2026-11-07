import { describe, expect, it } from "vitest";
import {
  describeVar,
  formatAnnualRate,
  formatDate,
  formatHorizon,
  formatInteger,
  formatMoney,
  formatMoneyCompact,
  formatMoneyRange,
  formatPercent,
  formatProbability,
} from "./format";

describe("formatMoney", () => {
  it("uses the response currency", () => {
    expect(formatMoney(1234.5, "USD")).toBe("$1,234.50");
    expect(formatMoney(2834.5, "INR")).toBe("₹2,834.50");
    expect(formatMoney(99.999, "EUR")).toBe("€100.00");
  });

  it("uses Indian digit grouping for INR", () => {
    expect(formatMoney(1234567.8, "INR")).toBe("₹12,34,567.80");
  });

  it("falls back to a plain number without a currency", () => {
    expect(formatMoney(1234.5, null)).toBe("1,234.50");
    expect(formatMoney(1234.5, undefined)).toBe("1,234.50");
  });

  it("does not throw on an unknown currency code", () => {
    expect(formatMoney(10, "NOT-A-CODE")).toBe("10.00 NOT-A-CODE");
  });

  it("renders non-finite values as a dash", () => {
    expect(formatMoney(Number.NaN, "USD")).toBe("—");
  });
});

describe("formatMoneyCompact", () => {
  it("drops decimals from 100 up", () => {
    expect(formatMoneyCompact(297.71, "USD")).toBe("$298");
    expect(formatMoneyCompact(2834.5, "INR")).toBe("₹2,835");
  });
  it("keeps cents below 100", () => {
    expect(formatMoneyCompact(42.5, "USD")).toBe("$42.5");
  });
  it("goes compact for large values", () => {
    expect(formatMoneyCompact(250_000, "USD")).toBe("$250K");
  });
});

describe("formatMoneyRange", () => {
  it("uses 2 decimals on both ends below 1,000 and keeps trailing zeros", () => {
    expect(formatMoneyRange(35.4, 66.91, "USD")).toBe("$35.40–$66.91");
    expect(formatMoneyRange(55.24, 106, "USD")).toBe("$55.24–$106.00");
    expect(formatMoneyRange(120, 999.994, "USD")).toBe("$120.00–$999.99");
  });

  it("uses whole numbers on both ends when the larger end is 1,000 or more", () => {
    expect(formatMoneyRange(812.37, 1204.5, "USD")).toBe("$812–$1,205");
    expect(formatMoneyRange(1000, 1500.4, "USD")).toBe("$1,000–$1,500");
  });

  it("applies the same rule to INR", () => {
    expect(formatMoneyRange(845.3, 990, "INR")).toBe("₹845.30–₹990.00");
    expect(formatMoneyRange(1245.6, 1890.25, "INR")).toBe("₹1,246–₹1,890");
  });

  it("handles a missing currency and non-finite values", () => {
    expect(formatMoneyRange(1.5, 2, null)).toBe("1.50–2.00");
    expect(formatMoneyRange(Number.NaN, 2, "USD")).toBe("—");
  });
});

describe("formatPercent", () => {
  it("formats percent-unit values", () => {
    expect(formatPercent(17.2746)).toBe("17.3%");
    expect(formatPercent(17.2746, { digits: 2 })).toBe("17.27%");
  });
  it("signs when asked, with a true minus sign", () => {
    expect(formatPercent(5, { signed: true })).toBe("+5.0%");
    expect(formatPercent(-5, { signed: true })).toBe("−5.0%");
    expect(formatPercent(-5)).toBe("−5.0%");
  });
  it("never shows -0.0%", () => {
    expect(formatPercent(-0.01, { signed: true })).toBe("0.0%");
    expect(formatPercent(0.04)).toBe("0.0%");
  });
});

describe("formatProbability / formatAnnualRate / formatInteger", () => {
  it("converts fractions to percentages", () => {
    expect(formatProbability(0.2365)).toBe("23.7%");
    expect(formatProbability(1)).toBe("100.0%");
    expect(formatAnnualRate(0.316195)).toBe("31.6%");
    expect(formatAnnualRate(-0.05, { signed: true })).toBe("−5.0%");
  });
  it("groups integers", () => {
    expect(formatInteger(10000)).toBe("10,000");
  });
});

describe("formatDate", () => {
  it("formats ISO dates without time-zone drift", () => {
    expect(formatDate("2026-11-06")).toBe("Nov 6, 2026");
    expect(formatDate("2026-01-01")).toBe("Jan 1, 2026");
  });
  it("returns unparseable input unchanged", () => {
    expect(formatDate("yesterday")).toBe("yesterday");
  });
});

describe("formatHorizon", () => {
  it("spells out horizon labels", () => {
    expect(formatHorizon("6m")).toBe("6 months");
    expect(formatHorizon("1y")).toBe("1 year");
    expect(formatHorizon("2y")).toBe("2 years");
    expect(formatHorizon("1m")).toBe("1 month");
    expect(formatHorizon("6mo")).toBe("6 months");
    expect(formatHorizon("weird")).toBe("weird");
  });
});

describe("describeVar", () => {
  it("shows the loss when VaR is positive", () => {
    expect(describeVar(16.9275)).toEqual({ noLoss: false, text: "16.9%" });
  });
  it("shows no loss when VaR is zero or negative", () => {
    expect(describeVar(-3.2)).toEqual({ noLoss: true, text: "No loss at 95% confidence" });
    expect(describeVar(0)).toEqual({ noLoss: true, text: "No loss at 95% confidence" });
  });
});
