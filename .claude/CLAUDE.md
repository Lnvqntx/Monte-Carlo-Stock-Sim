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
- **Phases:** 1 core library, 2 CLI, 3 FastAPI, 4 Next.js frontend, 5 deploy, 6 README, 7 extras. Phases 1-6 are done; next is 7 (extras).
- **Live:** website https://monte-carlo-stock-sim.vercel.app, API https://monte-carlo-stock-api.vercel.app (docs at `/docs`).
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
  - `GET /` -> service name, description and links (`/docs`, `/api/health`, website).
  - `GET /api/health` -> `{"status": "ok"}`
  - `POST /api/simulate` body: `ticker`, `horizon` (required, max 5y), `lookback` (`6mo|1y|2y|5y`, default `2y`), `n_sims` (1000-20000, default 10000), `seed` (default 42).
  - Errors are always `{"error": {"code", "message"}}`: `invalid_ticker` 404, `insufficient_data` 422, `invalid_input` 422, `data_unavailable` 502, `internal_error` 500.
  - Env vars: `ALLOWED_ORIGINS` (comma-separated, default `http://localhost:3000`), `CACHE_TTL_SECONDS` (default 900, 0 disables), `CACHE_MAX_ENTRIES` (default 100).
- CLI (from `backend/`): `python cli.py --ticker AAPL --horizon 6m`
  - Options: `--lookback 2y`, `--sims 10000`, `--seed 42`, `--save DIR` (default `./output`), `--no-show` (save charts without opening windows), `--json FILE` (write the full `run_simulation` result).
  - Charts are saved as `<TICKER>_<horizon>_paths.png` and `<TICKER>_<horizon>_hist.png`.
- Tests (from `backend/`): `python -m pytest` (no network; yfinance and `run_simulation` are mocked).
- Frontend (from `frontend/`, Node 22+): `npm install`, then `cp .env.example .env.local` (sets `BACKEND_URL=http://localhost:8000`), then `npm run dev` and open http://localhost:3000
  - Run both together locally: terminal 1 `cd backend && source .venv/bin/activate && uvicorn api.main:app --reload` (port 8000); terminal 2 `cd frontend && npm run dev` (port 3000). The browser calls the relative `/api/simulate`; `next.config.ts` rewrites `/api/*` to `BACKEND_URL` only when it is a valid http(s) URL (validated by `lib/backend-url.ts`; read at build time). Do not add Next.js API routes under `/api`.
  - Demo mode (no backend / no Yahoo access): `NEXT_PUBLIC_DEMO_MODE=true npm run dev` serves `mocks/sample-response.json`. Regenerate it with `npm run generate:mock` (needs the backend venv active; uses `core` + `api.serialize` on synthetic prices).
  - Checks: `npm run lint`, `npm test` (Vitest: formatting helpers, error-code mapping, chart data), `npm run build`.
  - Layout: `app/` (layout with site metadata + Open Graph/Twitter tags, page, globals.css with the palette tokens, `opengraph-image.tsx` generated share card), `components/` (BackgroundGlow = fixed page-wide glow that follows the cursor and drifts, paused when hidden, static with reduced motion; Simulator = state + URL sync, InputCard, Results, FanChart, HistogramChart, States, HowItWorks), `lib/` (`types.ts` mirrors the API response, `api.ts` fetch + demo mode, `errors.ts` code -> friendly copy, `format.ts` Intl money/percent/date, `chart.ts` Recharts data + nice axis ticks + reference-label layout, `options.ts` tickers/horizons/defaults, `site.ts` site URL/name/description).
  - Downside figures (probability of loss, VaR, negative changes) use terracotta `#E07A5F`; purple text uses the lighter tint `#B39DFB` for contrast.
- Code layout: `core/` = maths (do not change for UI work), `cli.py` = terminal UI on `core.run_simulation`, `plots.py` = matplotlib charts.
  - `api/` = FastAPI: `main.py` (app, routes, error handlers, CORS), `schemas.py` (Pydantic models + validation), `serialize.py` (downsamples to <= 200 points + `days` axis, 50 sample paths), `cache.py` (in-memory TTL cache of trimmed results).

## Docs
- `README.md` (root) = project overview for visitors; `frontend/README.md` = short frontend dev notes; `LICENSE` = MIT. Screenshots live in `docs/images/` (hero, results, distribution).

## Deployment
- Full click-by-click steps: `DEPLOY.md` (repo root). Two Vercel projects from this repo:
  - **API**: Root Directory `backend`, FastAPI preset. Entrypoint `backend/index.py` (re-exports `api.main:app`; keep it a one-line import). Python pinned by `backend/.python-version` (3.12). Vercel installs only the runtime deps (`requirements.txt`, mirrored in `pyproject.toml` `[project].dependencies`; `tests/test_deploy.py` keeps them in sync). `backend/.vercelignore` drops tests, CLI, plots, dev requirements, output and caches. Installed deps are ~180 MB unzipped / ~55 MB zipped.
  - **Website**: Root Directory `frontend`, Next.js preset, env var `BACKEND_URL` = the API's production URL (e.g. `https://<api>.vercel.app`). It is read at build time, so redeploy after changing it. Missing/invalid -> build still succeeds with a warning, no rewrite, and the UI shows "data unavailable" (production builds map non-JSON `/api` responses to `data_unavailable`).
  - `ALLOWED_ORIGINS` is not needed when the website proxies through the rewrite (the browser only talks to the website's own domain); set it only if a browser calls the API URL directly.
  - `NEXT_PUBLIC_DEMO_MODE` is off unless exactly `true`; never set it on the production website.
- Fallback if Yahoo blocks Vercel's IPs (every ticker returns `data_unavailable`): Render Blueprint `backend/render.yaml` (free plan, `pip install -r requirements.txt`, `uvicorn api.main:app --host 0.0.0.0 --port $PORT`, health check `/api/health`), then point `BACKEND_URL` at the Render URL and redeploy the website.
- Pushing to `main` redeploys both projects to production; other branches get preview deployments.
