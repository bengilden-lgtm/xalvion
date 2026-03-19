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
    try:
        result = run_agent(req.message)

        return {
            "response": result.get("final", "No response"),
            "confidence": result.get("confidence", 0),
            "quality": result.get("quality", 0),
            "mode": result.get("mode", "unknown")
        }

    except Exception as e:
        return {
            "response": f"ERROR: {str(e)}",
            "confidence": 0,
            "quality": 0,
            "mode": "crash"
        }