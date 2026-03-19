from agent import run_agent

print("🧠 Sovereign Support Engine (CLI Mode)")

while True:
    user = input("\nYou: ")

    if user.lower() == "exit":
        break

    result = run_agent(user)

    print("\nAI:", result["final"])
    print(f"📊 Confidence: {result['confidence']}")
    print(f"🧠 Quality: {result['quality']}")
    print(f"🎭 Mode: {result['mode']}")