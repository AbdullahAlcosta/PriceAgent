"""
Pricing Engine — business rules.

ALL CARDS (graded or raw):
  If Collectr price > $500 → also search PriceCharting (ungraded for raw,
  grade-specific for graded) for cross-validation.

RAW / SEALED:
  1. TCGPlayer primary
  2. If Collectr price > $500: also PriceCharting (ungraded)
  3. TCGPlayer not found → Collectr price fallback

GRADED:
  1. PriceCharting primary (grade-specific)
  2. If Collectr price > $500: PriceCharting regardless (already done in step 1)
  3. PriceCharting not found → Collectr price fallback

Logging: every not-found includes specific reason.
"""

import threading
from engine.classify import Card, classify_card
from scrapers.tcgplayer import search_tcgplayer
from scrapers.pricecharting import search_pricecharting
from config import HIGH_VALUE_THRESHOLD, PARALLEL_WORKERS
from logger import log


import re


# Words/patterns that appear in Collectr card names but should be
# stripped before searching TCGPlayer (they confuse the search or
# are not used in TCGPlayer's naming convention)
_STRIP_PATTERNS = [
    r'\s*-\s*OP\d{2}-\d+\b',      # " - OP09-119" card code embedded in name
    r'\s*-\s*[A-Z]{2}\d{2}-\d+\b', # other card codes like " - ST22-001"
    r'\b(?:JP|EN|CN|TW|KR|DE|FR|IT|ES|PT)\b',  # language tags
    r'\b(?:Parallel|Alternate Art|Alternate Full Art|Full Art|Special|SP|TR|SR|SEC|L|R|UC|C)\b',  # rarity/variant tags
    r'\b(?:Reprint)\b',
]
_STRIP_RE = re.compile('|'.join(_STRIP_PATTERNS), re.IGNORECASE)


def _clean_name_for_search(name: str) -> str:
    """
    Clean a card name for search engine queries.
    Handles issues found in real One Piece / Pokemon card data:
      - Dots in names: Portgas.D.Ace → Portgas D Ace
      - Embedded card codes: Monkey.D.Luffy - OP09-119 SP → Monkey D Luffy
      - Language tags: Uta JP → Uta
      - Variant tags: Portgas.D.Ace Parallel → Portgas D Ace
    """
    cleaned = name
    # Remove embedded card codes and variant tags
    cleaned = _STRIP_RE.sub(' ', cleaned)
    # Replace dots used as name separators (D.Ace, D.Luffy etc.)
    cleaned = re.sub(r'\.', ' ', cleaned)
    # Collapse multiple spaces
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()
    return cleaned


def _clean_query_for_tcg(name: str, set_name: str) -> str:
    """
    Build TCGPlayer search query.
    Strip parenthetical variants and clean dots/codes from names.
    """
    # Remove parenthetical content
    name_clean = re.sub(r'\([^)]*\)', '', name).strip()
    name_clean = _clean_name_for_search(name_clean)
    set_clean  = _clean_name_for_search(set_name)
    # Remove dashes used as decorators in set names (e.g. "-The Best-")
    set_clean  = re.sub(r'\s*-\s*', ' ', set_clean)
    set_clean  = re.sub(r'\s+', ' ', set_clean).strip()
    return " ".join(p for p in [name_clean, set_clean] if p).strip()


def _tcg_query(card: Card) -> str:
    return _clean_query_for_tcg(card.name, card.set_name)


def _pc_query(card: Card) -> str:
    """
    PriceCharting query — name + set only, NO card number.
    PriceCharting's search doesn't handle slash-numbers (e.g. 125/094, GG69/GG70)
    well and often returns no results when they're included.
    Name is cleaned of dots but parenthetical content is KEPT because
    PriceCharting uses it (e.g. "Giratina VSTAR" not "Giratina VSTAR (Secret)").
    """
    name_clean = _clean_name_for_search(card.name)
    set_clean  = _clean_name_for_search(card.set_name)
    # Remove set suffixes that PriceCharting doesn't use
    set_clean  = re.sub(r'\s*:.*$', '', set_clean).strip()  # e.g. "Crown Zenith: Galarian Gallery" → "Crown Zenith"
    query = " ".join(p for p in [name_clean, set_clean] if p).strip()
    # _clean_name_for_search strips the "JP" language tag along with other
    # noise tags — re-append it so PriceCharting searches the Japanese print
    # instead of silently matching the English one.
    if card.is_japanese:
        query = f"{query} (JP)".strip()
    return query


def _run_pricecharting(card: Card, grading_company: str = "",
                        grade_value: str = "") -> dict:
    """Run PriceCharting lookup with error handling."""
    try:
        return search_pricecharting(
            _pc_query(card),
            grading_company=grading_company,
            grade_value=grade_value,
            card_name=card.name,
            set_name=card.set_name,
            card_number=card.number,
        )
    except Exception as e:
        log(f"PriceCharting error for '{card.name}': {e}", level="ERROR")
        return {"found": False, "price": None, "url": None,
                "grade_label": "", "reason": f"PriceCharting exception: {e}"}


def _apply_pc(card: Card, pc: dict):
    """Write PriceCharting result onto card."""
    if pc["found"]:
        card.pricecharting_price = pc["price"]
        card.pricecharting_result_url = pc.get("url") or ""
        log(f"  → PriceCharting ({pc['grade_label']}): ${pc['price']:.2f}")
    else:
        reason = pc.get("reason", "Unknown")
        log(f"  → PriceCharting not found: {reason}", level="WARN")
        card.notes = (card.notes + " | " if card.notes else "") + reason


def price_graded_card(card: Card) -> Card:
    """
    Graded cards: use Collectr price as primary (grading company unknown from API).
    If Collectr price > $500: also search PriceCharting (ungraded) for cross-reference.
    """
    collectr_is_high = bool(
        card.collectr_price and card.collectr_price > HIGH_VALUE_THRESHOLD
    )

    if card.collectr_price:
        card.price_source_used = "Collectr Price (Graded)"
        log(f"  → [Graded] Using Collectr price: ${card.collectr_price:.2f}")
    else:
        card.price_source_used = "Not Found"
        log(f"  → [Graded] No Collectr price available for '{card.name}'",
            level="WARN")

    # Cross-check PriceCharting (ungraded) for high-value cards
    if collectr_is_high:
        log(f"  → Collectr price ${card.collectr_price:.2f} > "
            f"${HIGH_VALUE_THRESHOLD} — cross-checking PriceCharting (ungraded)...")
        pc = _run_pricecharting(card, grading_company="", grade_value="")
        _apply_pc(card, pc)
        if pc["found"]:
            card.price_source_used = "Collectr (Graded) + PriceCharting"

    return card


def price_raw_sealed_card(card: Card) -> Card:
    """
    Raw/sealed cards:
      Collectr price > $500 → PriceCharting (ungraded) only, skip TCGPlayer
      Collectr price ≤ $500 → TCGPlayer primary, Collectr fallback
    """
    collectr_is_high = bool(
        card.collectr_price and card.collectr_price > HIGH_VALUE_THRESHOLD
    )

    # ── High value: PriceCharting only ────────────────────────────────────────
    if collectr_is_high:
        log(f"  → Collectr price ${card.collectr_price:.2f} > "
            f"${HIGH_VALUE_THRESHOLD} — using PriceCharting (ungraded), skipping TCGPlayer")
        pc = _run_pricecharting(card, grading_company="", grade_value="")
        _apply_pc(card, pc)
        if pc["found"]:
            card.price_source_used = "PriceCharting (high value)"
        else:
            if card.collectr_price:
                card.price_source_used = "Collectr Price (fallback)"
                log(f"  → PriceCharting miss — fallback to Collectr: ${card.collectr_price:.2f}")
            else:
                card.price_source_used = "Not Found"
        return card

    # ── Normal value: TCGPlayer ───────────────────────────────────────────────
    tcg_query = _tcg_query(card)
    try:
        tcg = search_tcgplayer(
            tcg_query,
            card_name=card.name,
            set_name=card.set_name,
            card_number=card.number,
            is_japanese=card.is_japanese,
        )
    except Exception as e:
        tcg = {"found": False, "price": None, "url": None}
        reason = f"TCGPlayer exception: {e}"
        log(f"  → TCGPlayer error: {e}", level="ERROR")
        card.notes = (card.notes + " | " if card.notes else "") + reason

    if tcg["found"]:
        card.tcgplayer_price = tcg["price"]
        card.price_source_used = "TCGPlayer"
        log(f"  → TCGPlayer: ${tcg['price']:.2f}")
    else:
        reason = f"TCGPlayer: no match for '{tcg_query}'"
        log(f"  → {reason}", level="WARN")
        card.notes = (card.notes + " | " if card.notes else "") + reason
        if card.collectr_price:
            card.price_source_used = "Collectr Price (fallback)"
            log(f"  → Fallback to Collectr: ${card.collectr_price:.2f}")
        else:
            card.price_source_used = "Not Found"

    return card


def price_card(card: Card) -> Card:
    """Classify and route. Never raises."""
    try:
        card = classify_card(card)
        log(f"  Type: {card.card_type}"
            + (f" ({card.grading_company} {card.grade_value})"
               if card.card_type == "graded" else "")
            + (f" | Collectr: ${card.collectr_price:.2f}"
               if card.collectr_price else ""))
        if card.card_type == "graded":
            return price_graded_card(card)
        else:
            return price_raw_sealed_card(card)
    except Exception as e:
        log(f"Unexpected error pricing '{card.name}': {e}", level="ERROR")
        card.notes = (card.notes + " | " if card.notes else "") + f"Error: {e}"
        card.price_source_used = "Not Found"
        return card


def _worker(worker_id: int, cards: list[Card], results: list,
            start_idx: int, total: int):
    for i, card in enumerate(cards):
        global_idx = start_idx + i
        log(f"[Worker {worker_id}] [{global_idx+1}/{total}] "
            f"{card.name} | {card.set_name} | #{card.number}")
        results[global_idx] = price_card(card)


def price_all_cards(cards: list[Card]) -> list[Card]:
    total = len(cards)
    if total == 0:
        return []

    workers = min(PARALLEL_WORKERS, total)
    results = [None] * total
    batch_size = (total + workers - 1) // workers

    batches = []
    for w in range(workers):
        start = w * batch_size
        end   = min(start + batch_size, total)
        if start < total:
            batches.append((w + 1, cards[start:end], start))

    log(f"Starting {len(batches)} workers for {total} cards "
        f"(~{total // len(batches)} per worker)...")

    threads = []
    for worker_id, batch, start_idx in batches:
        t = threading.Thread(
            target=_worker,
            args=(worker_id, batch, results, start_idx, total),
            daemon=True,
            name=f"worker-{worker_id}",
        )
        threads.append(t)
        t.start()

    for t in threads:
        t.join()

    for i, r in enumerate(results):
        if r is None:
            results[i] = cards[i]
            results[i].price_source_used = "Not Found"
            results[i].notes = "Worker returned no result"

    log(f"All workers done. {total} cards priced.")
    return results
