from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel
from agent import run_agent

# ✅ THIS LINE WAS MISSING (CRITICAL)
app = FastAPI()

API_KEYS = ["xalvion-secret-key"]

def verify_key(x_api_key: str):
    if x_api_key not in API_KEYS:
        raise HTTPException(status_code=403, detail="Unauthorized")

class ChatRequest(BaseModel):
    message: str
    user_id: str

@app.get("/")
def root():
    return {"message": "AI SaaS LIVE"}

@app.post("/chat")
def chat(req: ChatRequest, x_api_key: str = Header(...)):
    verify_key(x_api_key)

    result = run_agent(req.message)

    return {
        "response": result["final"],
        "confidence": result["confidence"],
        "quality": result["quality"],
        "mode": result["mode"]
    }
