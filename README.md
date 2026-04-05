# Xalvion Sovereign Brain

AI-powered support operations system with a Chrome extension, FastAPI backend, adaptive learning engine, and Stripe billing integration.

---

## Quickstart (Windows)

```bash
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
uvicorn app:app --reload
pytest -v
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
Connects to `http://127.0.0.1:8000/analyze` — reads the active tab, sends ticket text, renders the decision panel.

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
uvicorn app:app --host 127.0.0.1 --port 8000 --reload
```

### 4. Load the Chrome extension

1. Open `chrome://extensions`
2. Enable **Developer mode**
3. Click **Load unpacked** → select the `xalvion-extension` folder in this repository
4. Open Gmail or Zendesk — click the Xalvion icon

---

## Environment Variables

See `.env.example` for the full list. Critical ones:

| Variable | Required | Description |
|---|---|---|
| `JWT_SECRET` | Yes (prod) | Min 32-char random string |
| `OPENAI_API_KEY` | Yes | OpenAI key |
| `STRIPE_SECRET_KEY` | Billing | Stripe secret key |
| `STRIPE_WEBHOOK_SECRET` | Prod | Webhook signature secret |
| `ENVIRONMENT` | Recommended | `development` or `production` |

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
