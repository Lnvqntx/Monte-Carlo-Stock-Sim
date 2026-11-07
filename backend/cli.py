"""Command-line interface for the Monte Carlo GBM stock simulator.

Run from backend/:
    python cli.py --ticker AAPL --horizon 6m
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Any

from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

import core
import plots
from core.errors import (
    DataFetchError,
    InsufficientDataError,
    InvalidTickerError,
    SimulatorError,
)
from core.rates import MAX_RATE, MIN_RATE

EXIT_OK = 0
EXIT_ERROR = 1
EXIT_USAGE = 2

DISCLAIMER = (
    "Model output from a GBM simulation on historical data - not a price prediction "
    "or financial advice."
)

RISK_FREE_NOTE = (
    "Risk-free drift: a neutral baseline where every path grows at the risk-free rate, "
    "not a forecast of this stock's return."
)


def fmt_money(value: float, prefix: str) -> str:
    return f"{prefix}{value:,.2f}"


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="cli.py",
        description="Monte Carlo (GBM) stock price simulator.",
        epilog="Example: python cli.py --ticker RELIANCE.NS --horizon 3m --no-show",
    )
    p.add_argument("--ticker", required=True, help="Stock symbol, e.g. AAPL or RELIANCE.NS")
    p.add_argument("--horizon", required=True, help="Forecast horizon, e.g. 1w, 3m, 6m, 1y")
    p.add_argument("--lookback", default="2y", help="History window for estimation (default: 2y)")
    p.add_argument("--sims", type=int, default=10_000, help="Number of simulations (default: 10000)")
    p.add_argument("--seed", type=int, default=42, help="Random seed (default: 42)")
    p.add_argument("--drift", choices=core.DRIFT_MODELS, default="historical",
                   help="Drift model: historical (estimated from past returns, default) or "
                        "risk_free (drift = risk-free rate, a risk-neutral baseline)")
    p.add_argument("--rate", type=float, metavar="FLOAT",
                   help="Risk-free rate as a decimal, e.g. 0.045 (only with --drift risk_free; "
                        "default: live 13-week T-bill for USD, else a per-currency default)")
    p.add_argument("--save", metavar="DIR", default="output",
                   help="Directory to save chart PNGs into (default: ./output)")
    p.add_argument("--no-show", action="store_true", help="Don't open chart windows (just save)")
    p.add_argument("--json", metavar="FILE", help="Also write the full result to a JSON file")
    return p


def render_summary(console: Console, result: dict[str, Any]) -> None:
    meta, params = result["metadata"], result["parameters"]
    settings, analysis = result["settings"], result["analysis"]
    prefix = plots.currency_prefix(meta.get("currency"))
    final = analysis["final_price"]
    s0 = params["S0"]

    name = meta.get("long_name") or meta["ticker"]
    header = (
        f"[bold]{name}[/bold]  ([bold]{meta['ticker']}[/bold])\n"
        f"Currency: {meta.get('currency') or 'unknown'}   "
        f"Last price date: {meta['last_date']}"
    )
    console.print(Panel(header, title="Monte Carlo GBM simulation", border_style="magenta",
                        expand=False))

    p_table = Table(title="Estimated parameters", box=box.SIMPLE_HEAD, title_justify="left")
    p_table.add_column("Parameter")
    p_table.add_column("Value", justify="right")
    p_table.add_row("Current price (S0)", fmt_money(s0, prefix))
    risk_free = settings.get("drift") == "risk_free"
    p_table.add_row("Annual drift (mu)" + (" used" if risk_free else ""),
                    f"{params['mu'] * 100:.2f}%")
    if risk_free and params.get("mu_historical") is not None:
        p_table.add_row("Historical drift (not used)", f"{params['mu_historical'] * 100:.2f}%")
    p_table.add_row("Annual volatility (sigma)", f"{params['sigma'] * 100:.2f}%")
    p_table.add_row("Daily returns used", f"{params['n_returns']:,}")

    s_table = Table(title="Settings", box=box.SIMPLE_HEAD, title_justify="left")
    s_table.add_column("Setting")
    s_table.add_column("Value", justify="right")
    s_table.add_row("Horizon", settings["horizon"])
    s_table.add_row("Trading days", str(settings["n_steps"]))
    s_table.add_row("Simulations", f"{settings['n_sims']:,}")
    s_table.add_row("Lookback", settings["lookback"])
    s_table.add_row("Seed", str(settings["seed"]))
    if risk_free:
        s_table.add_row("Drift model", "Risk-free (risk-neutral)")
        rate = settings.get("risk_free_rate")
        if rate is not None:
            s_table.add_row("Risk-free rate",
                            f"{rate * 100:.2f}% ({settings.get('rate_source') or 'unknown'})")
    else:
        s_table.add_row("Drift model", "Historical")

    console.print(p_table)
    console.print(s_table)

    r_table = Table(title=f"Results after {settings['horizon']}", box=box.SIMPLE_HEAD,
                    title_justify="left")
    r_table.add_column("Statistic")
    r_table.add_column("Value", justify="right")
    r_table.add_row("Mean final price", f"[bold magenta]{fmt_money(final['mean'], prefix)}[/]")
    r_table.add_row("Median final price", fmt_money(final["median"], prefix))
    r_table.add_row("5th percentile", fmt_money(final["p5"], prefix))
    r_table.add_row("25th percentile", fmt_money(final["p25"], prefix))
    r_table.add_row("75th percentile", fmt_money(final["p75"], prefix))
    r_table.add_row("95th percentile", fmt_money(final["p95"], prefix))
    r_table.add_row("Expected return", f"[bold magenta]{analysis['expected_return_pct']:+.2f}%[/]")
    r_table.add_row("Probability of ending below today",
                    f"{analysis['prob_below_start'] * 100:.1f}%")
    var_pct = analysis["var_95_pct"]
    if var_pct < 0:
        var_text = "No loss at 95% confidence"
    else:
        var_text = f"{fmt_money(s0 * var_pct / 100, prefix)} ({var_pct:.2f}%)"
    r_table.add_row("95% Value at Risk", f"[bold magenta]{var_text}[/]")
    console.print(r_table)

    if risk_free:
        console.print(f"[dim italic]{RISK_FREE_NOTE}[/]")
    console.print(f"[dim italic]{DISCLAIMER}[/]")


def save_charts(result: dict[str, Any], out_dir: Path, show: bool) -> list[Path]:
    import matplotlib

    if not show:
        matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    out_dir.mkdir(parents=True, exist_ok=True)
    paths_name, hist_name = plots.chart_filenames(result)
    paths_png, hist_png = out_dir / paths_name, out_dir / hist_name
    fig1 = plots.plot_fan_chart(result, paths_png)
    fig2 = plots.plot_histogram(result, hist_png)
    if show:
        plt.show()
    plt.close(fig1)
    plt.close(fig2)
    return [paths_png, hist_png]


def _fail(err: Console, message: str) -> int:
    err.print(f"[bold red]Error:[/] {message}", highlight=False)
    return EXIT_ERROR


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    logging.getLogger("yfinance").setLevel(logging.CRITICAL)  # we print our own messages
    console = Console()
    err = Console(stderr=True)
    ticker = args.ticker.strip().upper()

    if args.sims < 1:
        return _fail(err, "--sims must be at least 1.")
    if args.rate is not None:
        if args.drift != "risk_free":
            return _fail(err, "--rate only applies with --drift risk_free.")
        try:
            core.validate_rate(args.rate)
        except ValueError:
            return _fail(err, f"--rate must be a decimal between {MIN_RATE} and {MAX_RATE} "
                              f"(e.g. 0.045 for 4.5%), got {args.rate}.")

    try:
        with console.status(f"Fetching {ticker} and running {args.sims:,} simulations..."):
            result = core.run_simulation(
                ticker, args.horizon, lookback=args.lookback, n_sims=args.sims, seed=args.seed,
                drift=args.drift, risk_free_rate=args.rate,
            )
    except InvalidTickerError:
        return _fail(
            err,
            f"No data found for {ticker}. Check the symbol; Indian stocks need .NS or .BO "
            f"(e.g. RELIANCE.NS). It can also be a temporary network issue.",
        )
    except InsufficientDataError as exc:
        return _fail(
            err,
            f"Not enough price history for {ticker} ({exc}). Try a longer --lookback "
            f"(e.g. 5y) or a stock with a longer trading history.",
        )
    except DataFetchError:
        return _fail(
            err,
            f"Could not download data for {ticker}. Check your internet connection and "
            f"try again in a moment.",
        )
    except ValueError as exc:
        return _fail(
            err,
            f"Invalid input: {exc}. Horizons look like 1w, 3m, 6m or 1y.",
        )
    except SimulatorError as exc:
        return _fail(err, f"Simulation failed: {exc}")

    render_summary(console, result)

    if args.json:
        try:
            json_path = Path(args.json)
            if json_path.parent != Path("."):
                json_path.parent.mkdir(parents=True, exist_ok=True)
            json_path.write_text(json.dumps(result, indent=2), encoding="utf-8")
        except OSError as exc:
            return _fail(err, f"Could not write JSON to {args.json}: {exc.strerror or exc}")
        console.print(f"Saved JSON: [bold]{json_path}[/]")

    try:
        saved = save_charts(result, Path(args.save), show=not args.no_show)
    except OSError as exc:
        return _fail(err, f"Could not save charts to {args.save}: {exc.strerror or exc}")
    for png in saved:
        console.print(f"Saved chart: [bold]{png}[/]")

    return EXIT_OK


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        Console(stderr=True).print("[bold red]Interrupted.[/]")
        sys.exit(130)
