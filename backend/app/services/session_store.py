import secrets
import threading
import time

_sessions = {}
_lock = threading.Lock()

def create_session(user_id: int) -> str:
    token = secrets.token_urlsafe(32)
    expires_at = time.time() + 1800
    with _lock:
        _sessions[token] = {"user_id": user_id, "expires_at": expires_at}
    return token

def get_session(token: str) -> dict | None:
    with _lock:
        session = _sessions.get(token)
        if session:
            if time.time() < session["expires_at"]:
                return session
            else:
                del _sessions[token]
        return None

def delete_session(token: str) -> None:
    with _lock:
        if token in _sessions:
            del _sessions[token]
