import traceback


# 🧼 SAFE STRING
def safe_str(value):
    try:
        if isinstance(value, str):
            return value
        return str(value)
    except:
        return ""


# 🔢 SAFE INT
def safe_int(value, default=0):
    try:
        return int(value)
    except:
        return default


# 🧠 SAFE TICKET NORMALIZER
def normalize_ticket(ticket):
    return {
        "customer": safe_str(ticket.get("customer", "Unknown")),
        "ltv": safe_int(ticket.get("ltv", 0)),
        "issue": safe_str(ticket.get("issue", "")),
        "sentiment": safe_int(ticket.get("sentiment", 5)),
        "timestamp": safe_str(ticket.get("timestamp", ""))
    }


# 🛡️ GLOBAL SAFE EXECUTOR
def safe_execute(func, *args, **kwargs):
    try:
        return func(*args, **kwargs)
    except Exception as e:
        print("\n🚨 SYSTEM ERROR CAUGHT:")
        print(str(e))
        traceback.print_exc()
        return {"error": str(e)}