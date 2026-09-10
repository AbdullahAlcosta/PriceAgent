import datetime
import threading
from config import LOG_PATH

_lock = threading.Lock()
_listeners: list = []


def add_log_listener(callback):
    """
    Register a callback(line: str) invoked for every log line, in addition
    to the normal console + file output. Used by the GUI to stream progress
    into its on-screen log panel without changing CLI behavior.
    """
    _listeners.append(callback)


def remove_log_listener(callback):
    if callback in _listeners:
        _listeners.remove(callback)


def log(message: str, level: str = "INFO"):
    """Thread-safe logger -- safe to call from multiple worker threads."""
    ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    thread = threading.current_thread().name
    line = f"[{ts}] [{level}] [{thread}] {message}"
    print(line)
    with _lock:
        with open(LOG_PATH, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    for cb in _listeners:
        try:
            cb(line)
        except Exception:
            pass
