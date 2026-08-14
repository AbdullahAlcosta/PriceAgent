"""
Central configuration for the Card Pricing Agent.
Adjust timeouts, headless mode, and output paths here.
"""

import sys
import os

# Browser behavior
HEADLESS = True
NAV_TIMEOUT_MS = 30000
DEFAULT_SLOWMO_MS = 0

# Pricing thresholds
HIGH_VALUE_THRESHOLD = 500.00

# Parallel workers — each runs its own Chromium browser instance
# 5 workers = ~5x speed (~250MB RAM each = ~1.25GB total)
PARALLEL_WORKERS = 5

# Where is the base directory (works both frozen .exe and plain script)
if getattr(sys, "frozen", False):
    _base_dir = os.path.dirname(sys.executable)
else:
    _base_dir = os.path.dirname(os.path.abspath(__file__))

# Output
OUTPUT_DIR = os.path.join(_base_dir, "results")
LOG_PATH = os.path.join(OUTPUT_DIR, "run_log.txt")

os.makedirs(OUTPUT_DIR, exist_ok=True)
