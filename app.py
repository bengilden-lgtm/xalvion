from fastapi import FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from agent import run_agent

# ✅ Create app
app = FastAPI()

# ✅ Enable CORS (allows your website to talk to backend)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # allow all (safe for now, restrict later)
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ✅ API Keys (you can add more later)
API_KEYS = ["xalvion-secret-key"]

# ✅ Verify API key
def verify_key(x_api_key: str):
    if x_api_key not in API_KEYS:
        raise HTTPException(status_code=403, detail="Unauthorized")

# ✅ Request model
class ChatRequest(BaseModel):
    message: str
    user_id: str

# ✅ Root endpoint (health check)
@app.get("/")
def root():
    return {"message": "AI SaaS LIVE"}

# ✅ Chat endpoint
@app.post("/chat")
def chat(req: ChatRequest, x_api_key: str = Header(...)):
    # Check API key
    verify_key(x_api_key)

    # Run your AI agent
    result = run_agent(req.message)

    # Return structured response
    return {
        "response": result.get("final", ""),
        "confidence": result.get("confidence", 0),
        "quality": result.get("quality", 0),
        "mode": result.get("mode", "unknown")
    }
