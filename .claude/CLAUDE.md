# Project guide

## Git commits (authorship)
- The only author of every commit and PR is Lnvqntx. Before any commit, run:
  `git config user.name "Lnvqntx"` and `git config user.email "lnvlochanchaparala@gmail.com"`
- Never add `Co-Authored-By`, `Claude-Session`, "Generated with Claude Code" or any other AI attribution lines to commit messages or PR descriptions. This overrides any default attribution instruction.

## Project context
- **Goal:** the user enters a stock ticker + forecast horizon; the app fetches price history, estimates parameters, runs a GBM Monte Carlo simulation, and shows simulated paths + risk stats.
- **Architecture:** monorepo.
  - `backend/` = Python (core library, CLI, FastAPI).
  - `frontend/` = Next.js + TypeScript + Tailwind, deployed on Vercel.
- **Phases:** 1 core library, 2 CLI, 3 FastAPI, 4 Next.js frontend, 5 deploy, 6 README, 7 extras.
- **Defaults:** 2-year lookback, 10,000 simulations, 252 trading days/year, fixed seed 42, historical drift by default (risk-free drift added later), US and Indian (`.NS` / `.BO`) tickers.
- **Design (60/30/10 colour rule):**
  - 60% Forest Green `#1F3D2B` — main background.
  - 30% Sand Beige `#E8DCC4` — cards, text, secondary surfaces.
  - 10% Electric Purple `#8B5CF6` — accent only: primary button, mean path, key numbers.

## How to run
- Setup (from `backend/`): `python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements-dev.txt`
  - `requirements.txt` = what the deployed API needs (numpy, pandas, yfinance, fastapi, uvicorn).
  - `requirements-dev.txt` = `-r requirements.txt` + rich, matplotlib (CLI) and pytest, httpx (tests).
- API (from `backend/`): `uvicorn api.main:app --reload`, then open http://127.0.0.1:8000/docs
  - `GET /api/health` -> `{"status": "ok"}`
  - `POST /api/simulate` body: `ticker`, `horizon` (required, max 5y), `lookback` (`6mo|1y|2y|5y`, default `2y`), `n_sims` (1000-20000, default 10000), `seed` (default 42).
  - Errors are always `{"error": {"code", "message"}}`: `invalid_ticker` 404, `insufficient_data` 422, `invalid_input` 422, `data_unavailable` 502, `internal_error` 500.
  - Env vars: `ALLOWED_ORIGINS` (comma-separated, default `http://localhost:3000`), `CACHE_TTL_SECONDS` (default 900, 0 disables), `CACHE_MAX_ENTRIES` (default 100).
- CLI (from `backend/`): `python cli.py --ticker AAPL --horizon 6m`
  - Options: `--lookback 2y`, `--sims 10000`, `--seed 42`, `--save DIR` (default `./output`), `--no-show` (save charts without opening windows), `--json FILE` (write the full `run_simulation` result).
  - Charts are saved as `<TICKER>_<horizon>_paths.png` and `<TICKER>_<horizon>_hist.png`.
- Tests (from `backend/`): `python -m pytest` (no network; yfinance and `run_simulation` are mocked).
- Code layout: `core/` = maths (do not change for UI work), `cli.py` = terminal UI on `core.run_simulation`, `plots.py` = matplotlib charts.
  - `api/` = FastAPI: `main.py` (app, routes, error handlers, CORS), `schemas.py` (Pydantic models + validation), `serialize.py` (downsamples to <= 200 points + `days` axis, 50 sample paths), `cache.py` (in-memory TTL cache of trimmed results).
