import type { ErrorCode } from "./types";

export interface FriendlyError {
  code: ErrorCode;
  title: string;
  message: string;
}

const KNOWN_CODES: readonly ErrorCode[] = [
  "invalid_ticker",
  "insufficient_data",
  "invalid_input",
  "data_unavailable",
  "internal_error",
  "network_error",
];

/** Narrow an arbitrary code string from the API to a code we have copy for. */
export function normalizeErrorCode(code: string | null | undefined): ErrorCode {
  return (KNOWN_CODES as readonly string[]).includes(code ?? "") ? (code as ErrorCode) : "internal_error";
}

/**
 * Turn an API error code into copy for the error alert.
 * `detail` is the API's own message; it's only shown for invalid_input, where it names the bad field.
 */
export function friendlyError(
  code: string | null | undefined,
  { ticker, detail }: { ticker?: string; detail?: string } = {},
): FriendlyError {
  const symbol = ticker?.trim().toUpperCase() || "that ticker";
  const c = normalizeErrorCode(code);
  switch (c) {
    case "invalid_ticker":
      return {
        code: c,
        title: `We couldn't find ${symbol}`,
        message:
          "Check the symbol. Indian stocks need an exchange suffix: .NS for NSE or .BO for BSE (e.g. RELIANCE.NS). If the symbol is right, the data provider may be having a moment, so try again shortly.",
      };
    case "insufficient_data":
      return {
        code: c,
        title: "Not enough price history",
        message: `${symbol} doesn't have enough trading days in the selected lookback to estimate drift and volatility. Choose a longer lookback under Advanced.`,
      };
    case "invalid_input":
      return {
        code: c,
        title: "Please check your inputs",
        message: detail?.trim() || "One of the settings isn't valid. Check the ticker and options and try again.",
      };
    case "data_unavailable":
      return {
        code: c,
        title: "Market data is temporarily unavailable",
        message: "The price data provider didn't respond. Please try again in a minute.",
      };
    case "network_error":
      return {
        code: c,
        title: "Can't reach the simulator",
        message:
          process.env.NODE_ENV === "production"
            ? "The request didn't get through. Check your connection and try again."
            : "The request didn't get through. Check your connection and try again. Running locally? Make sure the API is running on port 8000 and BACKEND_URL is set.",
      };
    case "internal_error":
    default:
      return {
        code: "internal_error",
        title: "Something went wrong",
        message: "The simulation failed unexpectedly on the server. Please try again.",
      };
  }
}
