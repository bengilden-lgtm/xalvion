from fastapi import FastAPI
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from openai import OpenAI
import os

app = FastAPI()

# 🔐 Load API key
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# 🧠 Memory
memory = [
    {"role": "system", "content": "You are Xalvion, a powerful, intelligent AI assistant."}
]

class ChatRequest(BaseModel):
    message: str

@app.get("/")
def serve():
    return FileResponse("index.html")

# ✅ FIX: serve fluid correctly
app.mount("/fluid", StaticFiles(directory="fluid"), name="fluid")


@app.post("/support")
async def support(req: ChatRequest):
    user_msg = req.message

    memory.append({"role": "user", "content": user_msg})

    def stream():
        full_reply = ""

        try:
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=memory,
                stream=True
            )

            for chunk in response:
                if chunk.choices[0].delta.content:
                    text = chunk.choices[0].delta.content
                    full_reply += text
                    yield text

        except Exception as e:
            yield f"\n[Error: {str(e)}]"

        memory.append({"role": "assistant", "content": full_reply})

    return StreamingResponse(stream(), media_type="text/plain")