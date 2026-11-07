# Monte Carlo Stock Simulator: frontend

Next.js (App Router) + TypeScript + Tailwind CSS + Recharts. Single page that calls the FastAPI backend at `/api/simulate`.

```bash
npm install
cp .env.example .env.local   # BACKEND_URL=http://localhost:8000
npm run dev                  # http://localhost:3000 (start the API from ../backend first)
```

- Demo mode without the backend: `NEXT_PUBLIC_DEMO_MODE=true npm run dev` (uses `mocks/sample-response.json`).
- Regenerate the mock: `npm run generate:mock` (backend venv active).
- Checks: `npm run lint`, `npm test`, `npm run build`.
