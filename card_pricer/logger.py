import datetime
import threading
from config import LOG_PATH

_lock = threading.Lock()


def log(message: str, level: str = "INFO"):
    """Thread-safe logger -- safe to call from multiple worker threads."""
    ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    thread = threading.current_thread().name
    line = f"[{ts}] [{level}] [{thread}] {message}"
    print(line)
    with _lock:
        with open(LOG_PATH, "a", encoding="utf-8") as f:
            f.write(line + "\n")
