"""
Card Pricing Agent — friendly launcher.

This is what the client actually runs day-to-day (via run.command / run.bat,
or directly via the bundled CardPricingAgent.exe). It asks for the Collectr
URL in plain English, runs the full pipeline, and opens the finished Excel
file automatically when done.
"""

import os
import sys
import platform
import subprocess

# --- Bundled-exe support -----------------------------------------------
# When this script has been packaged into a Windows .exe with PyInstaller
# (see build_windows.bat), PyInstaller sets sys.frozen = True and extracts
# any bundled data (including the Chromium browser Playwright needs) into
# sys._MEIPASS. We point Playwright at that bundled browser here, BEFORE
# importing anything that touches Playwright, so the compiled .exe never
# tries to download a browser over the internet -- it's already inside it.
if getattr(sys, "frozen", False):
    bundled_browsers = os.path.join(sys._MEIPASS, "ms-playwright")  # type: ignore[attr-defined]
    if os.path.isdir(bundled_browsers):
        os.environ["PLAYWRIGHT_BROWSERS_PATH"] = bundled_browsers
# -------------------------------------------------------------------------

from scrapers.collectr import scrape_collectr_showcase
from engine.pricing_engine import price_all_cards
from output.excel_writer import write_cards_to_excel
from logger import log


def open_file(filepath: str):
    """Open the finished Excel file in whatever the OS's default app is."""
    system = platform.system()
    try:
        if system == "Windows":
            os.startfile(filepath)  # type: ignore[attr-defined]
        elif system == "Darwin":
            subprocess.run(["open", filepath])
        else:
            subprocess.run(["xdg-open", filepath])
    except Exception:
        print(f"\n(Could not auto-open the file. You can find it here:\n{filepath})")


def main():
    print("=" * 60)
    print("  Card Pricing Agent")
    print("=" * 60)
    print()
    url = input("Paste your Collectr showcase URL and press Enter:\n> ").strip()

    if not url:
        print("\nNo URL entered. Closing.")
        input("\nPress Enter to exit...")
        return

    import config
    print("\nWorking on it — this may take a while for large collections.")
    print(f"Running {config.PARALLEL_WORKERS} parallel workers to speed things up.")
    print(f"(Full details are being written to {config.LOG_PATH} as it runs.)\n")

    cards = scrape_collectr_showcase(url)
    if not cards:
        print("\nCouldn't find any cards at that URL. Please double-check the link and try again.")
        input("\nPress Enter to exit...")
        return

    priced_cards = price_all_cards(cards)
    filepath = write_cards_to_excel(priced_cards)

    print(f"\nDone! Priced {len(priced_cards)} cards.")
    print(f"Results saved to: {filepath}\n")

    open_file(filepath)

    input("Press Enter to close this window...")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        log(f"Unexpected error in launcher: {e}", level="ERROR")
        print(f"\nSomething went wrong: {e}")
        import config
        print(f"Check {config.LOG_PATH} for details, or contact support.")
        input("\nPress Enter to close...")
        sys.exit(1)
