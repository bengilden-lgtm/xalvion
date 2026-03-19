from agent import run_agent
from analytics import get_metrics

print("🧠 Sovereign Support Engine (Human Mode Enabled)")

while True:
    user = input("\nYou: ")

    if user.lower() == "exit":
        break

    if user.lower() == "/stats":
        print(get_metrics())
        continue

    result = run_agent(user)

    if "error" in result:
        print("❌", result["error"])
        continue

    print("\nAI:", result["final"])
    print(f"\n📊 Confidence: {round(result['confidence'], 2)}")
    print(f"🧠 Quality: {round(result['quality'], 2)}")
    print(f"🎭 Mode: {result['mode']}")

@app.post("/chat")
def chat(req: ChatRequest):
    return {"response": f"SAFE MODE: {req.message}"}