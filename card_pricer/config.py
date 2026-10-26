"""
Central configuration for the Card Pricing Agent.
Adjust timeouts, headless mode, and output paths here.
"""

import sys
import os
from pathlib import Path

# Bump this on every release handed to the client. Shown in the GUI title
# bar and logged at startup, so a stale build is immediately obvious from a
# screenshot or a log file alone instead of having to infer it from behavior.
APP_VERSION = "5"

# Browser behavior
HEADLESS = True
NAV_TIMEOUT_MS = 30000
DEFAULT_SLOWMO_MS = 0

# Pricing thresholds
HIGH_VALUE_THRESHOLD = 500.00

# Parallel workers — each runs its own Chromium browser instance
# 5 workers = ~5x speed (~250MB RAM each = ~1.25GB total)
PARALLEL_WORKERS = 5

# Rough seconds for ONE worker to price ONE card (a serial TCGPlayer and/or
# PriceCharting round-trip) -- used only to show an estimated completion
# time in the GUI. Derived from a real run: 67 cards with 5 workers took
# ~226s wall-clock, i.e. ~17s/card/worker. Actual time varies with network
# conditions and card mix (high-value/graded/Japanese cards make extra
# PriceCharting round-trips, raw misses that fall back to Collectr are
# faster) -- treat the GUI's estimate as a rough guide, not a guarantee.
AVG_SECONDS_PER_CARD_PER_WORKER = 17


def _default_output_dir() -> str:
    """
    Where finished Excel files and the run log live. Deliberately OUTSIDE
    the application folder (never next to the .exe) so it survives:
      - re-running build_windows.bat, which deletes dist/ entirely before
        every rebuild -- previously this silently wiped every past result
        and the run log along with it (the actual cause of a client
        reporting their run log had "gone missing")
      - the client (or developer) unzipping a newer build over the old one
      - double-clicking the .exe straight out of Windows' built-in zip
        viewer without extracting first -- that runs from a temporary
        extraction that gets cleaned up afterward, taking results/
        and run_log.txt with it
    """
    try:
        home = Path.home()
        documents = home / "Documents"
        base = documents if documents.is_dir() else home
        return str(base / "CardPricingAgent Results")
    except Exception:
        # Last-resort fallback: old next-to-the-exe behavior.
        if getattr(sys, "frozen", False):
            base_dir = os.path.dirname(sys.executable)
        else:
            base_dir = os.path.dirname(os.path.abspath(__file__))
        return os.path.join(base_dir, "results")


# Output
OUTPUT_DIR = _default_output_dir()
LOG_PATH = os.path.join(OUTPUT_DIR, "run_log.txt")

os.makedirs(OUTPUT_DIR, exist_ok=True)
