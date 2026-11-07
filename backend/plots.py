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
from matplotlib.ticker import FuncFormatter

FOREST = "#1F3D2B"  # 60% background
SAND = "#E8DCC4"  # 30% text, axes, secondary
PURPLE = "#8B5CF6"  # 10% accent

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
