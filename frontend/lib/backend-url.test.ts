import { describe, expect, it } from "vitest";
import { parseBackendUrl } from "./backend-url";

describe("parseBackendUrl", () => {
  it("accepts a production https URL and strips trailing slashes", () => {
    expect(parseBackendUrl("https://mc-api.vercel.app/")).toEqual({ ok: true, url: "https://mc-api.vercel.app" });
  });

  it("accepts the local dev URL", () => {
    expect(parseBackendUrl("http://localhost:8000")).toEqual({ ok: true, url: "http://localhost:8000" });
  });

  it("trims whitespace and a pasted /api suffix", () => {
    expect(parseBackendUrl("  https://mc-api.onrender.com/api/ \n")).toEqual({
      ok: true,
      url: "https://mc-api.onrender.com",
    });
  });

  it("keeps a real base path", () => {
    expect(parseBackendUrl("https://example.com/sim")).toEqual({ ok: true, url: "https://example.com/sim" });
  });

  it("reports a missing value", () => {
    expect(parseBackendUrl(undefined)).toMatchObject({ ok: false, reason: "missing" });
    expect(parseBackendUrl("   ")).toMatchObject({ ok: false, reason: "missing" });
  });

  it("rejects values without a scheme or with the wrong scheme", () => {
    expect(parseBackendUrl("mc-api.vercel.app")).toMatchObject({ ok: false, reason: "invalid" });
    expect(parseBackendUrl("ftp://mc-api.vercel.app")).toMatchObject({ ok: false, reason: "invalid" });
  });

  it("rejects query strings and fragments", () => {
    expect(parseBackendUrl("https://mc-api.vercel.app/?x=1")).toMatchObject({ ok: false, reason: "invalid" });
  });
});
