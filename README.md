# Xalvion Sovereign Brain

AI-powered support operations system with a Chrome extension, FastAPI backend, adaptive learning engine, and Stripe billing integration.

---

## Quickstart (Windows)

```bash
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
UVICORN_RELOAD=true python run.py
python -m pytest tests/test_suite.py -v
```

Copy `.env.example` to `.env` and fill in secrets before relying on auth, OpenAI, or Stripe in local runs.

---

## Architecture

```
app.py              FastAPI backend — all HTTP routes, auth, Stripe, tickets
agent.py            Core AI pipeline — builds context, calls LLM, executes actions
actions.py          Business logic — classify, triage, system_decision, calculate_impact
brain.py            Rule engine — learned_rules, weights, system prompt evolution
memory.py           Per-user history — sentiment tracking, soul file, importance decay
learning.py         Adaptive rules — learn_from_ticket, validate, simulate, decay
security.py         Input sanitization, output leak prevention
analytics.py        Event logging → SQLite, metrics API
feedback.py         Quality-driven rule reinforcement
router.py           Cost-aware model routing (cheap vs expensive)
tools.py            Mock order/refund/credit tools
utils.py            normalize_ticket, safe_execute helpers
dashboard.py        Simulation run dashboard (used by ticket_engine.py)
ticket_engine.py    Batch simulation harness
```

**Chrome Extension** (`xalvion-extension/` — `sidepanel.html`, `sidepanel.js`, `manifest.json`)  
Calls the operator API at `POST /analyze` (local default: `http://127.0.0.1:8000`). Production URL is set in `xalvion-extension/operator-config.js` (see **Deployment**).

---

## Setup

### 1. Clone and install

```bash
pip install -r requirements.txt
```

### 2. Configure environment

```bash
cp .env.example .env
# Edit .env — set JWT_SECRET, OPENAI_API_KEY, Stripe keys
```

### 3. Run the backend

```bash
# Listens on 0.0.0.0:$PORT (default PORT=8000). Enable reload:
UVICORN_RELOAD=true python run.py
```

For a strict local bind:

```bash
uvicorn app:app --host 127.0.0.1 --port 8000 --reload
```

### 4. Load the Chrome extension

1. Open `chrome://extensions`
2. Enable **Developer mode**
3. Click **Load unpacked** → select the `xalvion-extension` folder in this repository
4. Open Gmail or Zendesk — click the Xalvion icon

---

## Environment Variables

See `.env.example` for the full list.

### URL model (local vs production)

| Concept | Env vars | Purpose |
|--------|-----------|---------|
| **Frontend / workspace public origin** | `FRONTEND_PUBLIC_ORIGIN` (preferred) or `FRONTEND_URL` | Checkout success/cancel URLs, Stripe Connect UX redirects (`?stripe=…`, `?surface=integrations&stripe=…`). |
| **API public origin** | `API_PUBLIC_ORIGIN` (preferred) or `APP_ORIGIN` | Base URL of this FastAPI app. Stripe Connect callback defaults to `{API_PUBLIC_ORIGIN}/integrations/stripe/callback`. Must match the URL you deploy. |
| **Extension → API** | Not on the server | Set `DEFAULT_OPERATOR_API_ORIGIN` in `xalvion-extension/operator-config.js` to the same URL as `API_PUBLIC_ORIGIN` (HTTPS). |
| **Split UI hosting** | `WORKSPACE_API_BASE_URL` | Only if the workspace HTML is served from a different origin than the API; otherwise leave unset (same-origin, empty base). |

Local defaults keep prior behavior: frontend default `http://127.0.0.1:8001`, API default `http://127.0.0.1:8000`. Override API host/port locally with `XALVION_LOCAL_API_ORIGIN` if needed.

CORS: common PaaS hostnames (`*.up.railway.app`, `*.onrender.com`, `*.fly.dev`) are allowed via regex; add custom domains with `ALLOWED_ORIGINS` (comma-separated) or `CORS_ORIGIN_REGEX` (advanced).

### Core variables

| Variable | Required | Description |
|---|---|---|
| `JWT_SECRET` | Yes (prod) | Min 32-char random string |
| `OPENAI_API_KEY` | Yes | OpenAI key |
| `STRIPE_SECRET_KEY` | Billing | Stripe secret key |
| `STRIPE_WEBHOOK_SECRET` | Prod | Webhook signature secret |
| `ENVIRONMENT` | Recommended | `development` or `production` |
| `FRONTEND_PUBLIC_ORIGIN` / `FRONTEND_URL` | Prod | Public workspace URL users open in the browser |
| `API_PUBLIC_ORIGIN` / `APP_ORIGIN` | Prod | Public API URL (HTTPS) |
| `DATABASE_URL` | Prod (recommended) | Postgres URL on hosted infra; SQLite is ephemeral unless you attach a volume (see risks below) |
| `PORT` | Hosted | Set automatically on Railway/Render/Fly |

---

## Deployment (Railway first)

1. **Create a Railway service** from this repo. The included `Procfile` runs `uvicorn` on `0.0.0.0` with `$PORT`.
2. **Set environment variables** on the service (see table below for Railway).
3. **Database**: Prefer `DATABASE_URL` pointing to Railway Postgres (or another managed Postgres). If you use SQLite, set `STATE_STORE_DIR` to a mounted volume path so the file survives restarts (`db.py` respects `RAILWAY_VOLUME_MOUNT_PATH` / `STATE_STORE_DIR`).
4. **Stripe Dashboard**:
   - **Connect** redirect URI must match `STRIPE_CONNECT_REDIRECT_URI` (default `{API_PUBLIC_ORIGIN}/integrations/stripe/callback`).
   - **Webhooks** endpoint: `{API_PUBLIC_ORIGIN}/stripe/webhook` (path name unchanged).
5. **Workspace**: If the API serves `GET /` from this repo, leave `WORKSPACE_API_BASE_URL` unset; `workspace-bootstrap.js` keeps same-origin API calls. If you host static HTML elsewhere, set `WORKSPACE_API_BASE_URL` to the API origin and ensure that origin is in `ALLOWED_ORIGINS` / CORS regex.
6. **Extension**: Set `DEFAULT_OPERATOR_API_ORIGIN` in `operator-config.js` to your HTTPS API URL. Reload the unpacked extension (or ship a build). Add a `host_permissions` entry for your API host if it is not already covered (manifest includes `*.up.railway.app`, `*.onrender.com`, `*.fly.dev`, and `*.xalvion.tech`).

### Switching the extension between local and production

- **Local:** keep `DEFAULT_OPERATOR_API_ORIGIN = "http://127.0.0.1:8000"` (default) and use localhost `host_permissions` (already in `manifest.json`).
- **Production:** set `DEFAULT_OPERATOR_API_ORIGIN` to your deployed API (e.g. `https://your-service.up.railway.app`), reload the extension, and confirm the manifest allows that host (add explicitly if you use a custom domain).

Render/Fly: same env vars; use their process `PORT` and set `API_PUBLIC_ORIGIN` / `FRONTEND_PUBLIC_ORIGIN` to your public HTTPS URLs.

---

## API Routes

| Method | Path | Auth | Description |
|---|---|---|---|
| POST | `/login` | None | Get JWT token |
| POST | `/signup` | None | Create account |
| GET | `/me` | Bearer | Current user info |
| POST | `/support` | Bearer | Process support ticket |
| POST | `/support/stream` | Bearer | Streaming ticket pipeline |
| POST | `/analyze` | None (rate-limited) | Chrome extension endpoint |
| GET | `/tickets` | Bearer | List tickets |
| GET | `/dashboard/summary` | Bearer | Metrics dashboard |
| POST | `/billing/upgrade` | Bearer | Upgrade plan |
| POST | `/stripe/webhook` | Stripe sig | Webhook handler |
| GET | `/health` | None | Health check |

---

## Operator Modes

| Mode | Behaviour |
|---|---|
| `balanced` | Default — standard policy |
| `conservative` | Refunds routed to review, credits capped at $10 |
| `delight` | Credits increased, reviews converted to credits |
| `fraud_aware` | Repeat refund behaviour triggers review instead of auto |

---

## Running Tests

From the repository root (with the virtual environment activated):

```bash
pytest -v
```

To run only this project’s suite file:

```bash
pytest tests/test_suite.py -v
```

---

## Plan Tiers

| Tier | Monthly Tickets | Dashboard |
|---|---|---|
| Free | 12 | Basic |
| Pro | 500 | Full |
| Elite | 5,000 | Advanced |

---

## Security Notes

- Set `JWT_SECRET` to a long random string before deploying
- Set `STRIPE_WEBHOOK_SECRET` in production — unsigned webhooks are rejected
- `/analyze` endpoint is unauthenticated but rate-limited (30 req/min per IP)
- `ENVIRONMENT=production` enforces hard security requirements at startup

## Hosted deploy — Railway env checklist

Set these on the Railway service (values are examples — use your real URLs):

| Variable | Example / note |
|----------|----------------|
| `ENVIRONMENT` | `production` |
| `JWT_SECRET` | 32+ random characters |
| `OPENAI_API_KEY` | your key |
| `API_PUBLIC_ORIGIN` | `https://your-service.up.railway.app` |
| `FRONTEND_PUBLIC_ORIGIN` | Same as `API_PUBLIC_ORIGIN` if the workspace is served by this app; otherwise your static site origin |
| `DATABASE_URL` | `postgresql+psycopg2://...` (recommended) |
| `STRIPE_SECRET_KEY` | live or test secret |
| `STRIPE_WEBHOOK_SECRET` | from Stripe webhook signing secret |
| `STRIPE_CONNECT_CLIENT_ID` | Connect client id |
| `STRIPE_PRICE_PRO` / `STRIPE_PRICE_ELITE` | price ids if using checkout |
| `CHECKOUT_SUCCESS_URL` / `CHECKOUT_CANCEL_URL` | optional; default uses `FRONTEND_PUBLIC_ORIGIN` |
| `STRIPE_CONNECT_REDIRECT_URI` | optional; default `{API_PUBLIC_ORIGIN}/integrations/stripe/callback` |
| `ALLOWED_ORIGINS` | comma-separated extra CORS origins (custom domains) |
| `WORKSPACE_API_BASE_URL` | optional; only for split static UI |

`PORT` is injected by Railway — do not hardcode in the platform UI unless you know you need to.

### Remaining deployment risks

- **SQLite without a volume** on PaaS loses data on every redeploy; use Postgres or a mounted disk (`STATE_STORE_DIR` / volume path).
- **Stripe redirect mismatch**: Connect and Checkout URLs in Stripe Dashboard must match the values derived from `API_PUBLIC_ORIGIN` and `FRONTEND_PUBLIC_ORIGIN`.
- **Extension host permissions**: Custom API domains must be listed in `manifest.json` if not matched by existing patterns.
- **HTTP localhost** in the extension is dev-only; production should use HTTPS on the API.
