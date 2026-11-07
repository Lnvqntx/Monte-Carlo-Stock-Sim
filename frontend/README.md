# Monte Carlo Stock Simulator: frontend

The website for the [Monte Carlo Stock Simulator](../README.md), live at [monte-carlo-stock-sim.vercel.app](https://monte-carlo-stock-sim.vercel.app).

Next.js (App Router) + TypeScript + Tailwind CSS + Recharts. A single page that calls the FastAPI backend through the relative `/api/simulate`; `next.config.ts` rewrites `/api/*` to `BACKEND_URL` (read at build time).

## Develop

Requires Node 22+. Start the API from `../backend` first (see the [root README](../README.md#run-locally)).

```bash
npm install
```

```bash
cp .env.example .env.local
```

```bash
npm run dev
```

Open http://localhost:3000. `.env.local` sets `BACKEND_URL=http://localhost:8000`.

- **Demo mode** (no backend needed): `NEXT_PUBLIC_DEMO_MODE=true npm run dev` serves `mocks/sample-response.json` (historical) or `mocks/sample-response-risk-free.json` (risk-free drift).
- **Regenerate the mock**: `npm run generate:mock` (backend venv active).
- **Checks**: `npm run lint`, `npm test` (Vitest), `npm run build`.

## Layout

- `app/`: root layout and metadata, the page, `globals.css` (palette tokens), generated Open Graph image.
- `components/`: `Simulator` (state + URL sync), `InputCard`, `Results`, `FanChart`, `HistogramChart`, `HowItWorks`, loading/error states.
- `lib/`: API client and demo mode, response types, drift options and rate parsing, error-code copy, money/percent formatting, chart data helpers, site constants.

Deployment: see [DEPLOY.md](../DEPLOY.md).
