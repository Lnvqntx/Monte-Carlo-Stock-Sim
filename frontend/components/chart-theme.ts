/** Chart colours (60/30/10): sand for structure, purple for the forecast, terracotta for downside only. */
export const CHART = {
  accent: "#8B5CF6",
  accentText: "#B39DFB",
  sand: "#E8DCC4",
  loss: "#E07A5F",
  grid: "rgba(232, 220, 196, 0.08)",
  axis: "rgba(232, 220, 196, 0.55)",
  tooltipBg: "#11241A",
} as const;

export const AXIS_TICK = { fill: CHART.axis, fontSize: 12 };
