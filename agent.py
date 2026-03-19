import os
from openai import OpenAI

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

SYSTEM_PROMPT = """
You are Xalvion AI — a powerful, intelligent assistant.

Rules:
- Be clear, helpful, and slightly confident
- Keep answers clean and easy to read
- If user is vague, guide them
- If user asks something complex, break it down simply
- Feel premium, not robotic
"""


def run_agent(message: str):
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": message},
            ],
        )

        reply = response.choices[0].message.content

        return {
            "final": reply,
            "confidence": 0.98,
            "quality": 0.98,
            "mode": "xalvion-ai",
        }

    except Exception as e:
        return {
            "final": f"ERROR: {str(e)}",
            "confidence": 0,
            "quality": 0,
            "mode": "error",
        }