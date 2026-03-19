from fastapi import FastAPI
from pydantic import BaseModel
from agent import run_agent

app = FastAPI()

class ChatRequest(BaseModel):
    message: str

@app.get("/")
def root():
    return {"message": "AI SaaS LIVE"}

@app.post("/chat")
def chat(req: ChatRequest):
    result = run_agent(req.message)

    return {
        "response": result["final"],
        "confidence": result["confidence"],
        "quality": result["quality"],
        "mode": result["mode"]
    }