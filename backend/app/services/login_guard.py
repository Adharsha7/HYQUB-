import threading
import time

_failures = {}
_lock = threading.Lock()

def record_failure(username: str) -> None:
    with _lock:
        data = _failures.get(username, {"count": 0, "lockout_until": 0})
        data["count"] += 1
        if data["count"] >= 5:
            data["lockout_until"] = time.time() + 60
        _failures[username] = data

def check_locked(username: str) -> bool:
    with _lock:
        data = _failures.get(username)
        if not data:
            return False
        if time.time() < data["lockout_until"]:
            return True
        if data["lockout_until"] > 0 and time.time() >= data["lockout_until"]:
            # Reset after lockout expires
            data["count"] = 0
            data["lockout_until"] = 0
        return False

def record_success(username: str) -> None:
    with _lock:
        if username in _failures:
            del _failures[username]
