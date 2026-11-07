"""Matplotlib charts for a run_simulation result, styled with the project palette.

Both functions take the dict returned by core.run_simulation, draw a figure, save it
as a PNG and return the matplotlib Figure (the caller decides whether to show/close it).
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
from matplotlib.figure import Figure
from matplotlib.ticker import FuncFormatter, MaxNLocator

FOREST = "#1F3D2B"  # 60% background
SAND = "#E8DCC4"  # 30% text, axes, secondary
PURPLE = "#8B5CF6"  # 10% accent
LOSS = "#E07A5F"  # terracotta, downside / misses only

CURRENCY_SYMBOLS = {"INR": "₹", "USD": "$"}


def currency_prefix(currency: str | None) -> str:
    """'₹' for INR, '$' for USD, otherwise 'CODE ' (or '' if unknown)."""
    if not currency:
        return ""
    code = currency.upper()
    return CURRENCY_SYMBOLS.get(code, f"{code} ")


def chart_filenames(result: dict[str, Any]) -> tuple[str, str]:
    """('<TICKER>_<horizon>_paths.png', '<TICKER>_<horizon>_hist.png')."""
    ticker = re.sub(r"[^A-Za-z0-9._-]", "_", str(result["metadata"]["ticker"]))
    horizon = result["settings"]["horizon"]
    stem = f"{ticker}_{horizon}"
    return f"{stem}_paths.png", f"{stem}_hist.png"


def _style_axes(fig: Figure, ax: plt.Axes) -> None:
    fig.patch.set_facecolor(FOREST)
    ax.set_facecolor(FOREST)
    for spine in ax.spines.values():
        spine.set_color(SAND)
        spine.set_alpha(0.6)
    ax.tick_params(colors=SAND, which="both")
    ax.xaxis.label.set_color(SAND)
    ax.yaxis.label.set_color(SAND)
    ax.title.set_color(SAND)
    ax.grid(True, color=SAND, alpha=0.12, linewidth=0.6)
    ax.set_axisbelow(True)


def _style_legend(ax: plt.Axes, **kwargs: Any) -> None:
    leg = ax.legend(facecolor=FOREST, edgecolor=SAND, framealpha=0.85, **kwargs)
    for text in leg.get_texts():
        text.set_color(SAND)


def _money_formatter(prefix: str) -> FuncFormatter:
    return FuncFormatter(lambda v, _pos: f"{prefix}{v:,.0f}" if abs(v) >= 100 else f"{prefix}{v:,.2f}")


def _title(result: dict[str, Any], what: str) -> str:
    meta, settings = result["metadata"], result["settings"]
    return f"{meta['ticker']} - {what} ({settings['horizon']} horizon, {settings['n_sims']:,} sims)"


def plot_fan_chart(result: dict[str, Any], path: str | Path) -> Figure:
    """Sample paths, 5-95% and 25-75% bands, mean path and today's price."""
    analysis = result["analysis"]
    s0 = result["parameters"]["S0"]
    prefix = currency_prefix(result["metadata"].get("currency"))
    bands = analysis["bands"]
    days = list(range(len(analysis["mean_path"])))

    fig, ax = plt.subplots(figsize=(11, 6), dpi=120)
    _style_axes(fig, ax)

    for i, sample in enumerate(analysis["sample_paths"]):
        ax.plot(days, sample, color=SAND, alpha=0.12, linewidth=0.6,
                label="Sample paths" if i == 0 else None)
    ax.fill_between(days, bands["p5"], bands["p95"], color=PURPLE, alpha=0.18,
                    linewidth=0, label="5-95% range")
    ax.fill_between(days, bands["p25"], bands["p75"], color=PURPLE, alpha=0.38,
                    linewidth=0, label="25-75% range")
    ax.plot(days, analysis["mean_path"], color=PURPLE, linewidth=2.4, label="Mean path")
    ax.axhline(s0, color=SAND, linestyle="--", linewidth=1.2, alpha=0.9,
               label=f"Today {prefix}{s0:,.2f}")

    ax.set_xlim(0, days[-1])
    ax.set_xlabel("Trading days ahead")
    ax.set_ylabel(f"Price ({result['metadata'].get('currency') or 'n/a'})")
    ax.yaxis.set_major_formatter(_money_formatter(prefix))
    ax.set_title(_title(result, "Simulated price paths"), fontsize=13, pad=12)
    _style_legend(ax, loc="upper left")
    fig.tight_layout()
    fig.savefig(path, facecolor=fig.get_facecolor())
    return fig


def plot_histogram(result: dict[str, Any], path: str | Path) -> Figure:
    """Distribution of final prices with today's price, median and 5th percentile marked."""
    analysis = result["analysis"]
    s0 = result["parameters"]["S0"]
    prefix = currency_prefix(result["metadata"].get("currency"))
    edges = analysis["histogram"]["bin_edges"]
    counts = analysis["histogram"]["counts"]
    final = analysis["final_price"]

    fig, ax = plt.subplots(figsize=(11, 6), dpi=120)
    _style_axes(fig, ax)

    widths = [b - a for a, b in zip(edges[:-1], edges[1:])]
    ax.bar(edges[:-1], counts, width=widths, align="edge", color=PURPLE, alpha=0.85,
           edgecolor=FOREST, linewidth=0.5)
    ax.axvline(s0, color=SAND, linestyle="--", linewidth=1.4,
               label=f"Today {prefix}{s0:,.2f}")
    ax.axvline(final["median"], color=SAND, linestyle="-", linewidth=1.8,
               label=f"Median {prefix}{final['median']:,.2f}")
    ax.axvline(final["p5"], color=SAND, linestyle=":", linewidth=1.8,
               label=f"5th percentile {prefix}{final['p5']:,.2f}")

    ax.set_xlabel(f"Final price ({result['metadata'].get('currency') or 'n/a'})")
    ax.set_ylabel("Number of simulations")
    ax.xaxis.set_major_formatter(_money_formatter(prefix))
    ax.set_title(_title(result, "Distribution of final prices"), fontsize=13, pad=12)
    _style_legend(ax, loc="upper right")
    fig.tight_layout()
    fig.savefig(path, facecolor=fig.get_facecolor())
    return fig


# --- backtests ---------------------------------------------------------------------------

def backtest_filename(result: dict[str, Any]) -> str:
    """'<TICKER>_<horizon>_backtest_<start>.png' or '<TICKER>_<horizon>_calibration.png'."""
    ticker = re.sub(r"[^A-Za-z0-9._-]", "_", str(result["metadata"]["ticker"]))
    settings = result["settings"]
    stem = f"{ticker}_{settings['horizon']}"
    if settings.get("mode") == "rolling":
        return f"{stem}_calibration.png"
    return f"{stem}_backtest_{result['backtest']['start_date']}.png"


def plot_backtest_fan(result: dict[str, Any], path: str | Path) -> Figure:
    """Forecast fan from a past start date with the actual price path drawn on top."""
    analysis, bt = result["analysis"], result["backtest"]
    s0 = result["parameters"]["S0"]
    prefix = currency_prefix(result["metadata"].get("currency"))
    bands = analysis["bands"]
    days = list(range(len(analysis["mean_path"])))

    fig, ax = plt.subplots(figsize=(11, 6), dpi=120)
    _style_axes(fig, ax)
    ax.fill_between(days, bands["p5"], bands["p95"], color=PURPLE, alpha=0.18,
                    linewidth=0, label="Forecast 5-95%")
    ax.fill_between(days, bands["p25"], bands["p75"], color=PURPLE, alpha=0.38,
                    linewidth=0, label="Forecast 25-75%")
    ax.plot(days, analysis["mean_path"], color=PURPLE, linewidth=2.0, label="Forecast mean")
    ax.axhline(s0, color=SAND, linestyle="--", linewidth=1.0, alpha=0.6,
               label=f"Start {prefix}{s0:,.2f}")
    actual_days = list(range(len(bt["actual_path"])))
    ax.plot(actual_days, bt["actual_path"], color=SAND, linewidth=2.4,
            label=f"Actual {prefix}{bt['actual_final']:,.2f} "
                  f"({bt['percentile_rank']:.0f}th pct)")
    ax.scatter([actual_days[-1]], [bt["actual_final"]], s=40, zorder=5,
               color=SAND if bt["inside_90"] else LOSS, edgecolor=FOREST)

    ax.set_xlim(0, days[-1])
    ax.set_xlabel(f"Trading days after {bt['start_date']}")
    ax.set_ylabel(f"Price ({result['metadata'].get('currency') or 'n/a'})")
    ax.yaxis.set_major_formatter(_money_formatter(prefix))
    ax.set_title(_title(result, f"Backtest from {bt['start_date']}"), fontsize=13, pad=12)
    _style_legend(ax, loc="upper left")
    fig.tight_layout()
    fig.savefig(path, facecolor=fig.get_facecolor())
    return fig


def plot_calibration(result: dict[str, Any], path: str | Path) -> Figure:
    """PIT histogram of percentile ranks across rolling windows, with the flat 'ideal' line."""
    summary, settings = result["summary"], result["settings"]
    edges = summary["pit_histogram"]["bin_edges"]
    counts = summary["pit_histogram"]["counts"]
    n = summary["n_windows"]
    ideal = n / len(counts)

    fig, ax = plt.subplots(figsize=(11, 6), dpi=120)
    _style_axes(fig, ax)
    ax.bar(edges[:-1], counts, width=[b - a for a, b in zip(edges[:-1], edges[1:])],
           align="edge", color=PURPLE, alpha=0.85, edgecolor=FOREST, linewidth=1.0)
    ax.axhline(ideal, color=SAND, linestyle="--", linewidth=1.6,
               label=f"Ideal (flat): {ideal:.1f} per bin")
    ax.set_xlim(0, 100)
    ax.set_ylim(0, max(max(counts), ideal) * 1.3 + 0.5)  # headroom for the legend and note
    ax.yaxis.set_major_locator(MaxNLocator(integer=True))
    ax.set_xticks(edges)
    ax.set_xlabel("Percentile of the actual final price within the forecast")
    ax.set_ylabel("Number of start dates")
    ax.text(0.99, 0.97,
            f"90% band coverage: {summary['coverage_90'] * 100:.0f}% (ideal 90%)\n"
            f"50% band coverage: {summary['coverage_50'] * 100:.0f}% (ideal 50%)",
            transform=ax.transAxes, ha="right", va="top", color=SAND, fontsize=10,
            bbox=dict(facecolor=FOREST, edgecolor=SAND, alpha=0.85, boxstyle="round,pad=0.4"))
    ax.set_title(f"{result['metadata']['ticker']} - Calibration over {n} start dates "
                 f"({settings['horizon']} horizon, {settings['lookback']} lookback)",
                 fontsize=13, pad=12)
    _style_legend(ax, loc="upper left")
    fig.tight_layout()
    fig.savefig(path, facecolor=fig.get_facecolor())
    return fig
