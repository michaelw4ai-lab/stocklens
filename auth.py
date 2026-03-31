import hashlib
import json
import os
import secrets
import threading

AUTH_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cache", "users.json")
_lock = threading.Lock()


def _load_users():
    try:
        with open(AUTH_FILE, "r") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _save_users(users):
    os.makedirs(os.path.dirname(AUTH_FILE), exist_ok=True)
    with open(AUTH_FILE, "w") as f:
        json.dump(users, f)


def _hash_password(password, salt=None):
    if salt is None:
        salt = secrets.token_hex(16)
    hashed = hashlib.sha256((salt + password).encode()).hexdigest()
    return salt, hashed


def register(username, password):
    username = username.strip().lower()
    if not username or not password:
        return False, "Username and password are required."
    if len(username) < 3:
        return False, "Username must be at least 3 characters."
    if len(password) < 6:
        return False, "Password must be at least 6 characters."

    with _lock:
        users = _load_users()
        if username in users:
            return False, "Username already exists."
        salt, hashed = _hash_password(password)
        users[username] = {"salt": salt, "password": hashed}
        _save_users(users)
    return True, "Registration successful."


def authenticate(username, password):
    username = username.strip().lower()
    with _lock:
        users = _load_users()
    user = users.get(username)
    if not user:
        return False
    salt = user["salt"]
    _, hashed = _hash_password(password, salt)
    return hashed == user["password"]
