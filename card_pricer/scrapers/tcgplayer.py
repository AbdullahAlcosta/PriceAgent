"""
TCGPlayer scraper — confirmed real selectors from live HTML.

Confirmed selectors (verified August 2026):
  result wrapper      : div.search-result
  product link        : a[data-testid^="product-card__image--"]
  card title          : span.product-card__title.truncate  (text: "Mystery Plate Beta")
  set name            : div.product-card__set-name__variant (text: "Skyridge")
  rarity + number     : div.product-card__rarity__variant   (text: "Uncommon, \n#134/144")
  market price tile   : span.product-card__market-price--value (text: "$6.68")
  product page title  : h1.product-details__name
  market price page   : section.price-guide__points table tr -> td[0]=="Market Price"
  shipping badge      : div.shipping-badge
  US shipping option  : a#ShiptoCountry-UnitedStates-filter
  dialog backdrop     : div.tcg-base-dialog__backdrop

Key fix: use domcontentloaded not networkidle (networkidle times out on TCGPlayer)
Key fix: read market price from search tile (span.product-card__market-price--value)
         instead of navigating to product page — faster and confirmed working.
         Only navigate to product page for high-confidence matches to verify.
"""

import re
from difflib import SequenceMatcher
from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout
from logger import log
from config import HEADLESS, NAV_TIMEOUT_MS

SEARCH_URL = "https://www.tcgplayer.com/search/all/product?q={query}&view=grid"

RESULT_WRAPPER_SELECTOR   = "div.search-result"
PRODUCT_LINK_SELECTOR     = "a[data-testid^='product-card__image--']"
TITLE_SELECTOR            = "span.product-card__title"
SET_NAME_SELECTOR         = "div.product-card__set-name__variant"
RARITY_SELECTOR           = "div.product-card__rarity__variant"
TILE_PRICE_SELECTOR       = "span.product-card__market-price--value"

PRODUCT_TITLE_SELECTOR    = "h1.product-details__name"
MARKET_PRICE_ROW_SELECTOR = "section.price-guide__points table tr"

SHIP_TO_BADGE_SELECTOR    = "div.shipping-badge"
SHIP_TO_US_OPTION_SELECTOR = "a#ShiptoCountry-UnitedStates-filter"

DIALOG_BACKDROP_SELECTOR  = "div.tcg-base-dialog__backdrop"
DIALOG_CLOSE_SELECTORS    = [
    "button[aria-label='Close']",
    "button.tcg-base-dialog__close",
    "button[data-testid='close-button']",
]

PRICE_CLEAN_RE = re.compile(r"[^\d.]")


def _parse_price(text: str) -> float | None:
    if not text or text.strip() in ("-", "N/A", ""):
        return None
    cleaned = PRICE_CLEAN_RE.sub("", text.split("to")[0])
    try:
        v = float(cleaned)
        return v if v > 0 else None
    except ValueError:
        return None


def _dismiss_dialogs(page):
    try:
        for _ in range(3):
            if not page.query_selector(DIALOG_BACKDROP_SELECTOR):
                break
            for sel in DIALOG_CLOSE_SELECTORS:
                btn = page.query_selector(sel)
                if btn:
                    try:
                        btn.click(timeout=2000)
                        page.wait_for_timeout(400)
                        log("TCGPlayer: dismissed dialog")
                        break
                    except Exception:
                        continue
            else:
                page.keyboard.press("Escape")
                page.wait_for_timeout(400)
    except Exception:
        pass


def _ensure_ship_to_us(page):
    try:
        badge = page.query_selector(SHIP_TO_BADGE_SELECTOR)
        if not badge:
            return
        if "united states" in badge.inner_text().lower():
            return
        badge.click()
        page.wait_for_selector(SHIP_TO_US_OPTION_SELECTOR, timeout=4000)
        page.click(SHIP_TO_US_OPTION_SELECTOR)
        page.wait_for_timeout(400)
        log("TCGPlayer: set shipping to United States")
    except Exception as e:
        log(f"TCGPlayer: could not set shipping ({e})", level="WARN")


def _sim(a: str, b: str) -> float:
    return SequenceMatcher(None, a.lower().strip(), b.lower().strip()).ratio()


def _score_tile(tile, card_name: str, set_name: str, card_number: str,
                card_name_original: str = "") -> float:
    """
    Score a search result tile. Card number is highest priority signal.
    card_name_original: the name before parenthetical stripping, used as
    a secondary match signal for cards like 'Palkia & Dialga Legend (Bottom)'.
    """
    try:
        title_el  = tile.query_selector(TITLE_SELECTOR)
        set_el    = tile.query_selector(SET_NAME_SELECTOR)
        rarity_el = tile.query_selector(RARITY_SELECTOR)

        title_text  = title_el.inner_text().strip()  if title_el  else ""
        set_text    = set_el.inner_text().strip()     if set_el    else ""
        rarity_text = rarity_el.inner_text().strip()  if rarity_el else ""

        full_tile_text = f"{title_text} {set_text} {rarity_text}".lower()

        # Base: name similarity — take the BEST of cleaned name vs original name
        score_cleaned  = _sim(card_name, title_text) * 0.5
        score_original = _sim(card_name_original, title_text) * 0.5 if card_name_original else 0
        score = max(score_cleaned, score_original)

        # Set similarity
        if set_name:
            score += _sim(set_name, set_text) * 0.2

        # Card number
        if card_number:
            num_clean = card_number.lstrip("0").lower()
            num_full  = card_number.lower()
            if num_full in full_tile_text or num_clean in full_tile_text:
                score += 0.4
            else:
                num_base = num_full.split("/")[0].lstrip("0")
                if num_base and num_base in full_tile_text:
                    score += 0.3
                else:
                    score -= 0.1

        return min(score, 1.0)
    except Exception:
        return 0.0


def search_tcgplayer(query: str, card_name: str = "", set_name: str = "",
                     card_number: str = "") -> dict:
    result = {"found": False, "price": None, "url": None}
    card_name   = card_name or query
    card_number = card_number or ""
    # Keep original card name for secondary matching (e.g. "(Bottom)" in Palkia & Dialga)
    card_name_original = card_name

    # Clean query: remove parentheses, replace dots (Portgas.D.Ace → Portgas D Ace),
    # collapse spaces. The pricing_engine already strips most issues but we
    # do it here too as a safety net since the query comes in pre-cleaned.
    clean_query = re.sub(r"[()[\]]", "", query)
    clean_query = re.sub(r"\.", " ", clean_query)
    clean_query = re.sub(r"\s+", " ", clean_query).strip()
    # Clean card_name too for primary matching
    card_name = re.sub(r"\([^)]*\)", "", card_name).strip()
    card_name = re.sub(r"\.", " ", card_name)
    card_name = re.sub(r"\s+", " ", card_name).strip()
    url = SEARCH_URL.format(query=clean_query.replace(" ", "+"))

    MAX_RETRIES = 2
    for attempt in range(MAX_RETRIES):
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

            try:
                log(f"TCGPlayer: searching '{clean_query}'"
                    + (f" (retry {attempt})" if attempt > 0 else ""))
                # Use domcontentloaded — networkidle times out on TCGPlayer
                page.goto(url, wait_until="domcontentloaded")
                _dismiss_dialogs(page)
                _ensure_ship_to_us(page)

                # Wait for results to appear
                page.wait_for_selector(RESULT_WRAPPER_SELECTOR, timeout=12000)

            except PWTimeout:
                log(f"TCGPlayer: no results / timeout for '{clean_query}'", level="WARN")
                browser.close()
                break
            except Exception as e:
                browser.close()
                if attempt < MAX_RETRIES - 1 and (
                    "net::" in str(e) or "ERR_" in str(e)
                ):
                    log(f"TCGPlayer: network error, retrying ({e})", level="WARN")
                    import time; time.sleep(3)
                    continue
                log(f"TCGPlayer: error for '{clean_query}': {e}", level="ERROR")
                break

            tiles = page.query_selector_all(RESULT_WRAPPER_SELECTOR)
            if not tiles:
                browser.close()
                break

            # Score all tiles and pick best
            best_tile, best_score = None, -1.0
            for tile in tiles[:15]:
                score = _score_tile(tile, card_name, set_name, card_number,
                                    card_name_original)
                if score > best_score:
                    best_score, best_tile = score, tile

            if best_tile is None or best_score < 0.3:
                log(f"TCGPlayer: no confident match for '{clean_query}' "
                    f"(best score {best_score:.2f})", level="WARN")
                browser.close()
                break

            log(f"TCGPlayer: best tile score {best_score:.2f} for '{clean_query}'")

            # Read price directly from the tile (confirmed selector: span.product-card__market-price--value)
            price_el = best_tile.query_selector(TILE_PRICE_SELECTOR)
            price = _parse_price(price_el.inner_text()) if price_el else None

            link_el = best_tile.query_selector(PRODUCT_LINK_SELECTOR)
            href = link_el.get_attribute("href") if link_el else None
            if href and href.startswith("/"):
                href = "https://www.tcgplayer.com" + href

            browser.close()

            if price is not None:
                result["found"] = True
                result["price"] = price
                result["url"] = href
                log(f"TCGPlayer: '{clean_query}' -> ${price:.2f}")
            else:
                log(f"TCGPlayer: tile found but no price for '{clean_query}'",
                    level="WARN")
            break  # success or no-price, don't retry

    return result
