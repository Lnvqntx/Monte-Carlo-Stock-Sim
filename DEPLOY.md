# Deploying the Monte Carlo Stock Simulator

The repo deploys as **two Vercel projects** built from the same GitHub repo:

| Project | Root Directory | Framework preset | What it serves |
|---|---|---|---|
| API | `backend` | FastAPI | `/api/health`, `/api/simulate`, `/docs` |
| Website | `frontend` | Next.js | The UI. The browser calls `/api/*` on the website's own domain, and the website proxies it to the API via `BACKEND_URL`. |

```
browser ──► https://<website>.vercel.app/api/simulate ──(rewrite)──► https://<api>.vercel.app/api/simulate
```

Because the browser only ever talks to the website's own domain, **no CORS setup is needed** (`ALLOWED_ORIGINS` can stay unset).

Vercel's dashboard labels change from time to time. If a button below has a slightly different name, look for the closest match.

---

## 1. Create the API project (Root Directory `backend`)

1. Go to <https://vercel.com/new> (log in with GitHub if asked).
2. Under **Import Git Repository**, find **`Monte-Carlo-Stock-Sim`** and click **Import**.
   - Not listed? Click **Adjust GitHub App Permissions** and give Vercel access to the repo.
3. On the **Configure Project** screen:
   1. **Project Name**: e.g. `mc-stock-api`. This becomes the URL, `https://mc-stock-api.vercel.app`.
   2. **Root Directory**: click **Edit**, select **`backend`**, click **Continue**.
   3. **Framework Preset**: should switch to **FastAPI** on its own. If it doesn't, pick **FastAPI** (or **Other**) from the list.
   4. **Build and Output Settings**: leave everything at the defaults. Vercel installs `requirements.txt`, and only that file. The dev requirements are never installed.
   5. **Environment Variables**: none are required. Optional ones:
      - `CACHE_TTL_SECONDS` (default `900`, `0` disables the cache)
      - `CACHE_MAX_ENTRIES` (default `100`)
      - `ALLOWED_ORIGINS`: **not needed** while the website proxies through the rewrite. Set it (comma-separated, e.g. `https://mc-stock-sim.vercel.app`) only if a browser will call the API URL directly.
4. Click **Deploy** and wait for the "Congratulations" screen (about 1–2 minutes).
5. Click **Continue to Dashboard**. Copy the URL listed under **Domains**, e.g. `https://mc-stock-api.vercel.app`. That's `<api-url>` below.
   - Use the **Domains** URL, not the long per-deployment URL (`mc-stock-api-abc123-you.vercel.app`). Vercel puts login protection on per-deployment URLs, but production domains are public.

### Verify the API

1. Open `<api-url>/api/health` in a browser. You should see `{"status":"ok"}`.
2. Open `<api-url>/docs`. The interactive Swagger page should load.
3. POST a test simulation, either:
   - **In the browser**: on `/docs`, expand **POST /api/simulate**, click **Try it out**, set the body to `{"ticker": "AAPL", "horizon": "6m"}`, then click **Execute**. You should get a `200` response with `metadata`, `parameters`, `analysis` …
   - **From a terminal**:

     ```bash
     curl -s -X POST https://mc-stock-api.vercel.app/api/simulate -H "Content-Type: application/json" -d '{"ticker": "AAPL", "horizon": "6m"}'
     ```

   Also try an Indian ticker: `{"ticker": "RELIANCE.NS", "horizon": "1y"}`.
4. What the result means:
   - `200` with data: the API works. Go to step 2.
   - `{"error": {"code": "data_unavailable", ...}}` for **every** ticker: Yahoo Finance is blocking Vercel's servers. See [section 3](#3-if-the-api-returns-data_unavailable-for-every-ticker-yahoo-blocking).
   - Anything else: open the project's **Logs** tab (or **Deployments → latest → Runtime Logs**) to see the error.

---

## 2. Create the website project (Root Directory `frontend`)

1. Go to <https://vercel.com/new> again and **Import** the same **`Monte-Carlo-Stock-Sim`** repo a second time.
2. On **Configure Project**:
   1. **Project Name**: e.g. `mc-stock-sim`, giving `https://mc-stock-sim.vercel.app`.
   2. **Root Directory**: click **Edit**, select **`frontend`**, click **Continue**.
   3. **Framework Preset**: **Next.js** (detected automatically).
   4. **Build and Output Settings**: leave the defaults (`npm install`, `next build`). Node 22+ is used by default.
   5. **Environment Variables**: add one:

      | Key | Value |
      |---|---|
      | `BACKEND_URL` | `<api-url>` from step 1, e.g. `https://mc-stock-api.vercel.app` |

      - Paste the full URL including `https://`. A trailing `/` or `/api` is fine (both are stripped).
      - Leave it on all environments (Production, Preview, Development).
      - **Do not** add `NEXT_PUBLIC_DEMO_MODE`. Demo mode is off unless it is exactly `true`.
3. Click **Deploy**.
4. Optional: open the build log and check there's **no** line starting `⚠ BACKEND_URL`. That warning means the value was missing or not a valid URL, in which case the site builds but shows "Market data is temporarily unavailable" for every run.

### Verify end to end

1. Open the website URL (Dashboard → **Domains**).
2. Enter `AAPL`, pick a horizon (e.g. 6 months), click **Run simulation**.
3. The fan chart, histogram and risk stats should appear within a few seconds.
4. Try `RELIANCE.NS` and an invalid ticker such as `NOTREAL1`. The invalid one should show "We couldn't find NOTREAL1".
5. Optional: open `<website-url>/api/health` and check it shows `{"status":"ok"}`. That proves the rewrite reaches the API.

`BACKEND_URL` is read **at build time**. If you ever change it, you must **redeploy** the website (Deployments → latest → **⋯** → **Redeploy**) for the change to take effect.

---

## 3. If the API returns `data_unavailable` for every ticker (Yahoo blocking)

Yahoo Finance sometimes rate-limits or blocks cloud-provider IP ranges. The code doesn't need to change: move the API to Render's free tier with the Blueprint in `backend/render.yaml`.

### 3a. Deploy the API on Render

1. Go to <https://dashboard.render.com> and sign in with GitHub.
2. Click **New +** → **Blueprint**.
3. Connect / select the **`Monte-Carlo-Stock-Sim`** repo (click **Configure account** if it isn't listed). Then click **Connect**.
4. **Blueprint Name**: e.g. `mc-stock-api`.
5. **Blueprint Path**: change it from `render.yaml` to **`backend/render.yaml`**.
6. Render shows the service it will create (`monte-carlo-api`, free plan, Python). It also asks for a value for **`ALLOWED_ORIGINS`**. **Leave it blank**: it isn't needed behind the rewrite.
7. Click **Deploy Blueprint** (or **Apply**). The first build takes about 2–4 minutes.
8. Open the service and copy its URL, e.g. `https://monte-carlo-api.onrender.com`.
9. Verify it exactly like [section 1](#verify-the-api): `/api/health`, `/docs`, then the test POST.
   - Free Render services **sleep after ~15 minutes of inactivity**. The first request after a sleep can take 30–60 seconds. Just retry if it times out.

### 3b. Point the website at Render

1. Vercel → website project (`mc-stock-sim`) → **Settings** → **Environment Variables**.
2. Find `BACKEND_URL` → **⋯** → **Edit**, then set it to the Render URL, e.g. `https://monte-carlo-api.onrender.com`. Click **Save**.
3. **Deployments** tab → the latest production deployment → **⋯** → **Redeploy** → **Redeploy**. This is required because `BACKEND_URL` is read at build time.
4. Re-run the [end-to-end check](#verify-end-to-end).
5. Optional: in the Vercel API project, go to **Settings** → **General** → **Delete Project**, or just leave it, since it costs nothing idle.

Switching back later is the same three steps with the Vercel API URL.

---

## 4. Redeploys after pushing to `main`

- Every push to **`main`** triggers a **production** deployment of **both** Vercel projects (and of the Render service, if you used it; `autoDeploy: true`). There's nothing to click.
- Pushes to other branches and pull requests get **preview** deployments with their own URLs. The website's previews still use the `BACKEND_URL` you set, i.e. the production API.
- Both Vercel projects build on every push, even if only one folder changed. To skip unneeded builds, open each project's **Settings** → **Build and Deployment** → **Root Directory** and turn on **Skip deployments when there are no changes to the root directory or its dependencies**.
- Changing an environment variable does **not** redeploy on its own. Redeploy from the **Deployments** tab (see above).
- To roll back: **Deployments** → pick an earlier good deployment → **⋯** → **Promote to Production** (Vercel calls it **Instant Rollback**).

---

## Reference: what's in the repo for deployment

| File | Purpose |
|---|---|
| `backend/index.py` | Vercel entrypoint. It re-exports `app` from `api/main.py` (the FastAPI preset looks for `app` in `index.py`). |
| `backend/.python-version` | Pins Python **3.12** (Vercel's default and supported version; also respected by `uv`). |
| `backend/requirements.txt` | The only deps installed on Vercel/Render: numpy, pandas, yfinance, fastapi, uvicorn. `pyproject.toml` lists the same set, and a test keeps them in sync. |
| `backend/.vercelignore` | Keeps tests, the CLI, plots, dev requirements, `output/`, venvs and caches out of the function bundle. |
| `backend/render.yaml` | Render Blueprint fallback (free plan, health check `/api/health`). |
| `frontend/next.config.ts` + `frontend/lib/backend-url.ts` | Validates `BACKEND_URL` at build time and adds the `/api/:path*` rewrite. If it's missing or invalid, the build still passes with a warning, and the UI shows "data unavailable". |

Function size: the installed runtime dependencies are about **180 MB unzipped / 55 MB zipped** (pandas 45 MB, curl_cffi 40 MB, numpy 57 MB with its bundled libs). That is well under Vercel's Python function size limit.
