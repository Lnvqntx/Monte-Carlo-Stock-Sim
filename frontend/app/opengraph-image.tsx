import { ImageResponse } from "next/og";

// Social preview card (LinkedIn, X, Slack...) in the site's 60/30/10 palette.
export const alt = "Monte Carlo Stock Simulator: 10,000 GBM price paths with risk metrics";
export const size = { width: 1200, height: 630 };
export const contentType = "image/png";

const FOREST = "#1f3d2b";
const FOREST_DARK = "#11241a";
const SAND = "#e8dcc4";
const ACCENT = "#8b5cf6";
const ACCENT_TEXT = "#b39dfb";

// Deterministic "simulated" paths so the image is identical on every build.
function fanPaths(): { lines: string[]; mean: string } {
  const W = 460;
  const H = 300;
  const steps = 40;
  let seed = 42;
  const rand = () => {
    seed = (seed * 16807) % 2147483647;
    return seed / 2147483647;
  };
  const gauss = () => Math.sqrt(-2 * Math.log(rand() + 1e-12)) * Math.cos(2 * Math.PI * rand());
  const toY = (v: number) => H / 2 - v * 62;
  const lines: string[] = [];
  for (let i = 0; i < 26; i++) {
    let v = 0;
    const pts = [`0,${toY(0).toFixed(1)}`];
    for (let s = 1; s <= steps; s++) {
      v += 0.012 + 0.11 * gauss();
      pts.push(`${((s / steps) * W).toFixed(1)},${Math.min(H, Math.max(0, toY(v))).toFixed(1)}`);
    }
    lines.push(pts.join(" "));
  }
  const mean = Array.from({ length: steps + 1 }, (_, s) => `${((s / steps) * W).toFixed(1)},${toY(0.012 * s).toFixed(1)}`).join(" ");
  return { lines, mean };
}

export default function Image() {
  const { lines, mean } = fanPaths();
  return new ImageResponse(
    (
      <div
        style={{
          width: "100%",
          height: "100%",
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          padding: "72px 80px",
          background: `linear-gradient(135deg, ${FOREST} 0%, ${FOREST_DARK} 100%)`,
          color: SAND,
        }}
      >
        <div style={{ display: "flex", flexDirection: "column", width: 560 }}>
          <div
            style={{
              display: "flex",
              alignItems: "center",
              alignSelf: "flex-start",
              gap: 12,
              padding: "8px 20px",
              borderRadius: 999,
              border: "1px solid rgba(232,220,196,0.25)",
              fontSize: 24,
              color: "rgba(232,220,196,0.85)",
            }}
          >
            <div style={{ width: 10, height: 10, borderRadius: 999, background: ACCENT }} />
            GBM · 10,000 simulations
          </div>
          <div style={{ marginTop: 32, fontSize: 68, lineHeight: 1.05, letterSpacing: -1.5 }}>
            Monte Carlo Stock Simulator
          </div>
          <div style={{ marginTop: 28, fontSize: 28, lineHeight: 1.4, color: "rgba(232,220,196,0.75)" }}>
            Range of outcomes and downside risk for US and Indian stocks.
          </div>
          <div style={{ marginTop: 40, fontSize: 24, color: ACCENT_TEXT }}>monte-carlo-stock-sim.vercel.app</div>
        </div>
        <div
          style={{
            display: "flex",
            padding: 24,
            borderRadius: 28,
            background: "rgba(17,36,26,0.65)",
            border: "1px solid rgba(232,220,196,0.15)",
          }}
        >
          <svg width="460" height="300" viewBox="0 0 460 300">
            {lines.map((d, i) => (
              <polyline key={i} points={d} fill="none" stroke={SAND} strokeOpacity="0.22" strokeWidth="2" />
            ))}
            <polyline points={mean} fill="none" stroke={ACCENT} strokeWidth="6" strokeLinecap="round" />
          </svg>
        </div>
      </div>
    ),
    size,
  );
}
