"""
Collectr showcase scraper.

Uses Playwright to load the showcase page and intercept the paginated
API responses the browser makes naturally.

COLLECTION FILTER LOGIC (confirmed from real network traffic):
  When user opens a collection-filtered URL:
    Page URL:  /showcase/profile/@peeko?collection=9c1c5040-...
  The browser fires TWO API calls simultaneously:
    Call 1 (unfiltered): /data/showcase/@peeko?offset=0&limit=30&...
    Call 2 (filtered):   /data/showcase/@peeko?offset=0&limit=30&id=9c1c5040-...

  We only want Call 2. The mapping is confirmed:
    collection=UUID in page URL  →  id=UUID in API URL

  When user opens full portfolio (no ?collection= param):
    Only the unfiltered call fires — we accept everything normally.
"""

import json
import re
import threading
from urllib.parse import urlparse, parse_qs
from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout
from engine.classify import Card
from logger import log
from config import HEADLESS, NAV_TIMEOUT_MS

API_BASE         = "api-v2.getcollectr.com/data/showcase/"
PAGE_SIZE        = 30
MAX_PAGES        = 200
SCROLL_WAIT_MS   = 1500
NEW_DATA_TIMEOUT = 8
STABLE_LIMIT     = 5


def _safe_float(val) -> float | None:
    try:
        v = float(val)
        return v if v > 0 else None
    except (TypeError, ValueError):
        return None


def _make_collectr_url(product_id, product_name: str) -> str:
    if not product_id:
        return ""
    slug = re.sub(r"[^a-z0-9]+", "-", product_name.lower().strip()).strip("-")
    return f"https://app.getcollectr.com/explore/product/{product_id}/{slug}"


def _get_collection_id(profile_url: str) -> str | None:
    """
    Extract collection UUID from the page URL if present.
    Page URL ?collection=UUID  →  API URL ?id=UUID
    Returns None for plain full-portfolio URLs.
    """
    try:
        params = parse_qs(urlparse(profile_url).query)
        ids = params.get("collection", [])
        return ids[0] if ids else None
    except Exception:
        return None


def scrape_collectr_showcase(profile_url: str) -> list[Card]:
    collection_id = _get_collection_id(profile_url)
    if collection_id:
        log(f"Collection filter detected: id={collection_id}")
        log("Will ignore simultaneous unfiltered API calls.")
    else:
        log("Full portfolio URL — accepting all API responses.")

    all_products: list[dict] = []
    seen_ids: set = set()
    lock = threading.Lock()
    last_page_done = threading.Event()
    new_data_event = threading.Event()

    def handle_response(response):
        try:
            if API_BASE not in response.url:
                return
            if response.status != 200:
                return

            # When collection filter is active, skip unfiltered API calls.
            # The page fires both; we only want the one with id=UUID.
            if collection_id and f"id={collection_id}" not in response.url:
                return

            body = response.text()
            data = json.loads(body)

            products = []
            if isinstance(data, list):
                products = data
            elif isinstance(data, dict):
                for key in ("products", "data", "items", "cards", "results"):
                    if key in data and isinstance(data[key], list):
                        products = data[key]
                        break

            if not products:
                return

            new_count = 0
            with lock:
                for p in products:
                    pid = str(p.get("product_id") or p.get("id") or "")
                    dedup_key = pid if pid else p.get("product_name", "")
                    if dedup_key and dedup_key not in seen_ids:
                        seen_ids.add(dedup_key)
                        all_products.append(p)
                        new_count += 1

            if new_count:
                params_str = response.url.split("?")[1][:80] if "?" in response.url else ""
                log(f"Collectr API: +{new_count} cards "
                    f"(total: {len(all_products)}) ← {params_str}")
                new_data_event.set()

            if len(products) < PAGE_SIZE:
                log(f"Collectr: last page received ({len(products)} items).")
                last_page_done.set()

        except Exception:
            pass

    # ── Browser session ────────────────────────────────────────────────────────
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=HEADLESS,
            args=["--disable-blink-features=AutomationControlled", "--no-sandbox"]
        )
        context = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            extra_http_headers={"Accept-Language": "en-US,en;q=0.9"}
        )
        page = context.new_page()
        page.add_init_script(
            "Object.defineProperty(navigator,'webdriver',{get:()=>undefined});"
        )
        page.set_default_timeout(NAV_TIMEOUT_MS)

        # Register BEFORE navigating — catches the very first API call
        page.on("response", handle_response)

        try:
            log(f"Opening Collectr showcase: {profile_url}")
            page.goto(profile_url, wait_until="domcontentloaded")
        except PWTimeout:
            log(f"Timed out loading {profile_url}", level="ERROR")
            browser.close()
            return []

        # Wait up to 15s for first batch
        log("Waiting for initial card batch...")
        if not new_data_event.wait(timeout=15):
            log("No API response in 15s — continuing with scroll...", level="WARN")

        # ── Scroll loop ────────────────────────────────────────────────────────
        stable_rounds = 0
        prev_count    = 0

        for scroll_num in range(MAX_PAGES):
            if last_page_done.is_set():
                log("All pages loaded — last page signal received.")
                break

            with lock:
                current_count = len(all_products)

            if current_count > prev_count:
                stable_rounds = 0
                log(f"  Progress: {current_count} cards loaded (scroll {scroll_num+1})")
            else:
                stable_rounds += 1
                if stable_rounds >= STABLE_LIMIT:
                    log(f"Count stable at {current_count} for "
                        f"{stable_rounds} scrolls — done.")
                    break

            prev_count = current_count
            new_data_event.clear()

            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            page.wait_for_timeout(SCROLL_WAIT_MS)

            try:
                page.evaluate("""
                    const selectors = [
                        '.showcase-grid', '.product-grid', '.card-grid',
                        '[class*="showcase"]', '[class*="grid"]', 'main',
                    ];
                    for (const sel of selectors) {
                        const el = document.querySelector(sel);
                        if (el && el.scrollHeight > el.clientHeight) {
                            el.scrollTop = el.scrollHeight; break;
                        }
                    }
                """)
            except Exception:
                pass

            new_data_event.wait(timeout=NEW_DATA_TIMEOUT)

        log(f"Scroll complete. Total: {len(all_products)} cards.")
        browser.close()

    if not all_products:
        log("No products found — check the URL and try again.", level="ERROR")
        return []

    # ── Build Card objects ─────────────────────────────────────────────────────
    cards: list[Card] = []
    for p in all_products:
        name = (p.get("product_name") or "").strip()
        if not name:
            continue

        pid           = p.get("product_id") or p.get("id")
        grade_company = p.get("grade_company")
        grade_id      = p.get("grade_id")
        condition_or_grade = (
            f"{grade_company} {grade_id or ''}".strip()
            if grade_company else (p.get("card_condition") or "")
        )

        card = Card(
            name=name,
            set_name=p.get("catalog_group") or "",
            number=str(p.get("card_number") or ""),
            condition_or_grade=condition_or_grade,
            image_url=p.get("image_url") or "",
            quantity=int(p.get("quantity") or 1),
        )

        # ── Graded detection via grade_id (confirmed from real API data) ──────
        # grade_id 52 = ungraded (NM/LP etc.) — never has a slab image
        # grade_id 11 = MINT 9 slab
        # grade_id 12 = GEM MT 10 slab
        # grade_company is always null — API doesn't expose grading company.
        # We treat graded cards as "Graded" type so PriceCharting is used,
        # but since we don't know PSA vs CGC vs BGS, we search PriceCharting
        # with no company so it uses the company-agnostic "Grade X" row for
        # grades 1-9.5, and for grade 10 we'll get whichever 10 matches best.
        grade_id_str = str(p.get("grade_id") or "")
        UNGRADED_IDS = {"52", "0", ""}
        GRADE_ID_TO_VALUE = {
            "12": "10",   # GEM MT 10
            "11": "9",    # MINT 9
            "13": "9.5",  # likely NEAR MINT+ / 9.5
            "10": "8",    # EXCELLENT 8
            "9":  "7",    # VERY GOOD 7
            "8":  "6",
            "7":  "5",
        }
        if grade_id_str and grade_id_str not in UNGRADED_IDS:
            grade_val = GRADE_ID_TO_VALUE.get(grade_id_str, "")
            # Set condition_or_grade so classify_card detects it as graded
            # We use a generic "GRADE X" format — classify.py will pick it up
            card.condition_or_grade = f"GRADE {grade_val}" if grade_val else f"GRADED"
            card.collectr_grade_id = grade_id_str
            card.collectr_grade_value = grade_val

        card.collectr_price       = _safe_float(p.get("market_price"))
        card.ebay_listing_price   = _safe_float(p.get("ebay_price"))
        card.tcgplayer_search_url = p.get("tcgplayer_url") or ""
        card.ebay_sold_url        = p.get("ebay_sold_url") or ""
        card.pricecharting_url    = p.get("pricecharting_url") or ""
        card.collectr_item_url    = (
            p.get("item_url") or p.get("url")
            or _make_collectr_url(pid, name)
        )
        card.foil = p.get("product_sub_type") or ""

        cards.append(card)

    log(f"Collectr scrape complete: {len(cards)} unique cards.")
    return cards
