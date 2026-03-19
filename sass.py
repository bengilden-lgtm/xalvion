import json
import os
import uuid
import hashlib

USERS_FILE = "users.json"


# 📂 LOAD USERS
def load_users():
    if not os.path.exists(USERS_FILE):
        return {}

    with open(USERS_FILE, "r") as f:
        return json.load(f)


# 💾 SAVE USERS
def save_users(users):
    with open(USERS_FILE, "w") as f:
        json.dump(users, f, indent=2)


# 🔐 HASH PASSWORD
def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()


# 🆕 REGISTER USER
def register_user(username, password):
    users = load_users()

    if username in users:
        return {"error": "User already exists"}

    api_key = str(uuid.uuid4())

    users[username] = {
        "password": hash_password(password),
        "api_key": api_key,
        "usage": 0
    }

    save_users(users)

    return {"message": "User created", "api_key": api_key}


# 🔑 LOGIN
def login_user(username, password):
    users = load_users()

    if username not in users:
        return {"error": "User not found"}

    if users[username]["password"] != hash_password(password):
        return {"error": "Invalid password"}

    return {"message": "Login successful", "api_key": users[username]["api_key"]}


# 🔍 AUTHENTICATE API KEY
def authenticate(api_key):
    users = load_users()

    for username, data in users.items():
        if data["api_key"] == api_key:
            return username

    return None


# 📊 TRACK USAGE
def track_usage(api_key):
    users = load_users()

    for username in users:
        if users[username]["api_key"] == api_key:
            users[username]["usage"] += 1
            save_users(users)
            return