from agents import debate
from utils import safe_execute
from memory import get_user_memory, update_memory


def run_agent(prompt, user_id="default_user"):
    if not prompt:
        return {"error": "Empty prompt"}

    # 🧠 LOAD MEMORY
    memory = get_user_memory(user_id)

    context = f"""
USER MEMORY:
{memory['soul_file']}

CURRENT INPUT:
{prompt}
"""

    result = safe_execute(debate, context)

    if isinstance(result, dict) and "error" in result:
        return result

    try:
        response, critique, quality = result
    except:
        return {"error": "Agent response format failed"}

    # 🧠 UPDATE MEMORY
    update_memory(user_id, {
        "issue": prompt,
        "sentiment": 5  # default for chat mode
    }, response)

    return {
        "final": response,
        "critique": critique,
        "quality": quality,
        "confidence": round(quality, 2)
    }