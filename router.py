def route_task(user_input):
    low_effort_keywords = ["status", "where is my order", "tracking"]

    if any(k in user_input.lower() for k in low_effort_keywords):
        return "cheap"
    else:
        return "expensive"