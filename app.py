from fastapi import FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from agent import run_agent

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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

    try:
        result = run_agent(req.message)
        return {
            "response": result.get("final", "No response"),
            "confidence": result.get("confidence", 0),
            "quality": result.get("quality", 0),
            "mode": result.get("mode", "unknown"),
        }
    except Exception as e:
        return {
            "response": f"ERROR: {str(e)}",
            "confidence": 0,
            "quality": 0,
            "mode": "crash",
        }