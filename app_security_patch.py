"""
app_security_patch.py — documents the security hardening changes needed in app.py.

These are the specific changes to make in app.py to bring Security to 9/10.
Apply each patch to the corresponding section in app.py.
"""

# =============================================================================
# PATCH 1: Enforce JWT_SECRET is set — add after load_dotenv() in app.py
# =============================================================================

PATCH_1_ENFORCE_JWT_SECRET = '''
import sys

SECRET_KEY = os.getenv("JWT_SECRET", "").strip()
if not SECRET_KEY or SECRET_KEY == "dev_secret_change_me":
    if os.getenv("ENVIRONMENT", "development").lower() == "production":
        print("FATAL: JWT_SECRET must be set in production.", file=sys.stderr)
        sys.exit(1)
    # Development fallback — still warn loudly
    SECRET_KEY = "dev_secret_change_me"
    print("WARNING: Using insecure JWT_SECRET. Set JWT_SECRET env var before deploying.")
'''

# =============================================================================
# PATCH 2: Add auth to /analyze endpoint — replace current @app.post("/analyze")
# =============================================================================

PATCH_2_ANALYZE_RATE_LIMIT = '''
# Add a simple per-IP rate limit to /analyze (no auth required, but throttled)
from collections import defaultdict
import time

_analyze_rate: dict[str, list[float]] = defaultdict(list)
_ANALYZE_LIMIT = 30  # requests per minute per IP

def _check_analyze_rate(request: Request) -> None:
    ip = request.client.host if request.client else "unknown"
    now = time.time()
    _analyze_rate[ip] = [t for t in _analyze_rate[ip] if now - t < 60]
    if len(_analyze_rate[ip]) >= _ANALYZE_LIMIT:
        raise HTTPException(status_code=429, detail="Too many requests from this IP.")
    _analyze_rate[ip].append(now)

# Updated /analyze signature:
@app.post("/analyze")
def analyze_extension_ticket(
    req: ExtensionAnalyzeRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    _check_analyze_rate(request)
    # ... rest of handler unchanged
'''

# =============================================================================
# PATCH 3: Enforce Stripe webhook secret — replace optional check
# =============================================================================

PATCH_3_STRIPE_WEBHOOK = '''
# Replace:
#   if STRIPE_WEBHOOK_SECRET
# With a hard failure when in production:

if not STRIPE_WEBHOOK_SECRET and os.getenv("ENVIRONMENT", "").lower() == "production":
    raise HTTPException(status_code=500, detail="Stripe webhook secret not configured.")

try:
    if STRIPE_WEBHOOK_SECRET:
        event = stripe.Webhook.construct_event(payload, sig_header, STRIPE_WEBHOOK_SECRET)
    else:
        # Dev/test only — accept unsigned events
        event = stripe.Event.construct_from(json.loads(payload.decode("utf-8")), stripe.api_key)
except Exception as exc:
    raise HTTPException(status_code=400, detail=f"Webhook parse failed: {exc}") from exc
'''

# =============================================================================
# PATCH 4: Add ENVIRONMENT variable to .env.example
# =============================================================================

DOTENV_EXAMPLE = """
# === Xalvion .env.example ===
# Copy to .env and fill in real values before running

ENVIRONMENT=development          # Set to 'production' on live server

# Auth
JWT_SECRET=change_me_to_a_long_random_string_min_32_chars
TOKEN_EXPIRE_MINUTES=120

# Admin
ADMIN_USERNAME=your_admin_username

# AI
OPENAI_API_KEY=sk-...

# Database (defaults to local SQLite)
DATABASE_URL=sqlite:///./aurum.db

# Stripe
STRIPE_SECRET_KEY=sk_test_...
STRIPE_WEBHOOK_SECRET=whsec_...
STRIPE_PRICE_PRO=price_...
STRIPE_PRICE_ELITE=price_...
STRIPE_CONNECT_CLIENT_ID=ca_...

# CORS
FRONTEND_URL=http://127.0.0.1:8001
APP_ORIGIN=http://127.0.0.1:8000
ALLOWED_ORIGINS=

# Behaviour
LIVE_MODE=false
ALLOW_DIRECT_BILLING_BYPASS=true
MAX_AUTO_REFUND=50
APPROVAL_THRESHOLD=25.00
"""
