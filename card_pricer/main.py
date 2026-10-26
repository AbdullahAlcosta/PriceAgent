"""
Card Pricing Agent — main entry point.

Usage:
    python main.py "https://app.getcollectr.com/showcase/profile/@asos4"

Pipeline:
    1. Scrape the Collectr showcase URL for the full card list.
    2. Classify each card as graded vs raw/sealed.
    3. Price each card per the business rules (TCGPlayer primary, Collectr fallback).
    4. Write everything to a new timestamped Excel file in results/.

A failure at any single step for any single card is logged and skipped —
the batch always runs to completion.
"""

import sys
import config
from scrapers.collectr import scrape_collectr_showcase
from engine.pricing_engine import price_all_cards
from output.excel_writer import write_cards_to_excel
from logger import log


def run(showcase_url: str):
    log(f"=== Card Pricing Agent v{config.APP_VERSION} starting for {showcase_url} ===")

    cards = scrape_collectr_showcase(showcase_url)
    if not cards:
        log("No cards were scraped from the showcase. Aborting — nothing to price.", level="ERROR")
        return None

    priced_cards = price_all_cards(cards)
    filepath = write_cards_to_excel(priced_cards)

    log(f"=== Done. {len(priced_cards)} cards processed. Results: {filepath} ===")
    return filepath


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python main.py <collectr_showcase_url>")
        sys.exit(1)

    run(sys.argv[1])
