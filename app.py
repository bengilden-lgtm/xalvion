from fastapi import FastAPI, Header
from agent import run_agent
from saas import register_user, login_user, authenticate
from billing import check_limit, increment_usage, upgrade_user, init_user_plan

app = FastAPI()


@app.get("/")
def root():
    return {"message": "AI SaaS LIVE"}


# 🆕 REGISTER
@app.post("/register")
def register(data: dict):
    result = register_user(data["username"], data["password"])

    if "api_key" in result:
        init_user_plan(data["username"])

    return result


# 🔑 LOGIN
@app.post("/login")
def login(data: dict):
    return login_user(data["username"], data["password"])


# 🔼 UPGRADE
@app.post("/upgrade")
def upgrade(data: dict, x_api_key: str = Header(None)):
    user = authenticate(x_api_key)

    if not user:
        return {"error": "Invalid API key"}

    return upgrade_user(user, data["tier"])


# 🤖 AI (WITH BILLING)
@app.post("/chat")
def chat(data: dict, x_api_key: str = Header(None)):
    user = authenticate(x_api_key)

    if not user:
        return {"error": "Invalid API key"}

    if not check_limit(user):
        return {"error": "Usage limit reached. Upgrade required."}

    increment_usage(user)

    result = run_agent(data["message"], user)

    return {
        "user": user,
        "response": result.get("final"),
        "confidence": result.get("confidence"),
        "quality": result.get("quality")
    }