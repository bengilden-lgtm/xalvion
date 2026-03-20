import os
from openai import OpenAI

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def run_agent(message: str):
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a smart helpful AI assistant."},
                {"role": "user", "content": message}
            ]
        )

        reply = response.choices[0].message.content

        return {
            "final": reply,
            "confidence": 0.95,
            "quality": 0.95,
            "mode": "ai"
        }

    except Exception as e:
        return {
            "final": f"Error: {str(e)}",
            "confidence": 0,
            "quality": 0,
            "mode": "error"
        }
