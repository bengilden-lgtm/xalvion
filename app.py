from fastapi import FastAPI
from pydantic import BaseModel
from agent import run_agent

app = FastAPI()


# Request format
class ChatRequest(BaseModel):
    message: str


# Health check
@app.get("/")
def root():
    return {"message": "AI SaaS LIVE"}


# AI endpoint
@app.post("/chat")
def chat(req: ChatRequest):
    try:
        result = run_agent(req.message)

        # If your agent returns dict
        if isinstance(result, dict):
            return {
                "response": result.get("final", str(result)),
                "confidence": result.get("confidence", None),
                "quality": result.get("quality", None),
                "mode": result.get("mode", None)
            }

        # If your agent returns string
        return {"response": str(result)}

    except Exception as e:
        return {"error": str(e)}