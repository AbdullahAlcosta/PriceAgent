"""
PriceCharting scraper — confirmed real selectors from live HTML.

SEARCH PAGE (confirmed from Pricecharting_search_listing_page.txt):
  URL:          https://www.pricecharting.com/search-products?q={query}&type=prices
  table:        table#games_table
  each row:     tr#product-{id}
  title cell:   td.title > a  (text: "Staryu #84", href: "/game/pokemon-heartgold-&-soulsilver/staryu-84")
  set cell:     td.console  (text: "Pokemon HeartGold & SoulSilver")
  ungraded:     td.price.numeric.used_price
  grade 7:      td.price.numeric.cib_price
  grade 8:      td.price.numeric.new_price

PRODUCT PAGE (confirmed from pricecharting_product_page.txt):
  title:        h1#product_name  (text: "Staryu #84")
  full grades:  div#full-prices table tr
                  <td>LABEL</td><td class="price js-price">VALUE</td>
  Label → value format confirmed:
    "Ungraded", "Grade 1"..."Grade 9.5",
    "TAG 10", "ACE 10", "SGC 10", "CGC 10", "PSA 10",
    "BGS 10", "BGS 10 Black", "CGC 10 Pristine"
  Grade labels 1-9.5 are NOT split by company (confirmed).
  Grade 10 IS split by company (PSA 10, BGS 10, etc.).

MATCHING LOGIC:
  1. Search for card name + set name
  2. Score each result row by name + set similarity
  3. Card number is a strong signal (e.g. "#84" in title)
  4. Open best-match product page
  5. Confirm title still matches
  6. Read the row matching requested grade label
"""

import re
from difflib import SequenceMatcher
from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout
from logger import log
from config import HEADLESS, NAV_TIMEOUT_MS

SEARCH_URL = "https://www.pricecharting.com/search-products?q={query}&type=prices"

ROW_SELECTOR    = "table#games_table tbody tr"
TITLE_SEL       = "td.title a"
SET_SEL         = "td.console"
UNGRADED_SEL    = "td.price.numeric.used_price"

PRODUCT_TITLE_SEL  = "h1#product_name"
FULL_PRICE_ROW_SEL = "div#full-prices table tr"

PRICE_CLEAN_RE = re.compile(r"[^\d.]")


def _parse_price(text: str) -> float | None:
    if not text or text.strip() in ("-", "", "N/A"):
        return None
    cleaned = PRICE_CLEAN_RE.sub("", text)
    try:
        v = float(cleaned)
        return v if v > 0 else None
    except ValueError:
        return None


def _sim(a: str, b: str) -> float:
    return SequenceMatcher(None, a.lower().strip(), b.lower().strip()).ratio()


def _grade_label(grading_company: str, grade_value: str) -> str:
    """
    Convert grading info to PriceCharting price table label.
    Grades 1-9.5 → "Grade X"  (company-agnostic row, confirmed from real HTML)
    Grade 10 with known company → "PSA 10" / "BGS 10" etc.
    Grade 10 with unknown company → "PSA 10" as best default
    No grading → "Ungraded"
    """
    if not grade_value:
        return "Ungraded"
    grade_value = grade_value.strip()
    if grade_value in ("10", "10.0"):
        if grading_company:
            return f"{grading_company.strip().upper()} 10"
        else:
            # Company unknown (Collectr API doesn't expose it) — default PSA 10
            # since it's the most common; user can cross-check via link
            return "PSA 10"
    return f"Grade {grade_value}"


def _score_row(title_text: str, set_text: str,
               card_name: str, set_name: str, card_number: str) -> float:
    score = _sim(card_name, title_text) * 0.5
    if set_name:
        score += _sim(set_name, set_text) * 0.25
    if card_number:
        num_clean = card_number.lstrip("0").lower()
        if num_clean and (num_clean in title_text.lower()
                          or card_number.lower() in title_text.lower()):
            score += 0.35
        else:
            score -= 0.05
    return min(score, 1.0)


def search_pricecharting(query: str,
                          grading_company: str = "",
                          grade_value: str = "",
                          card_name: str = "",
                          set_name: str = "",
                          card_number: str = "") -> dict:
    """
    Returns {
        "found": bool,
        "price": float | None,
        "url":   str | None,
        "grade_label": str,         # which row was matched
        "reason": str,              # why not found (for logging)
    }
    """
    result = {
        "found": False, "price": None, "url": None,
        "grade_label": _grade_label(grading_company, grade_value),
        "reason": "",
    }
    card_name = card_name or query
    target_label = result["grade_label"]
    url = SEARCH_URL.format(query=query.replace(" ", "+").replace("&", "%26"))

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

        # ── Search ────────────────────────────────────────────────────────────
        try:
            log(f"PriceCharting: searching '{query}' (target: {target_label})")
            page.goto(url, wait_until="domcontentloaded")
            page.wait_for_selector(ROW_SELECTOR, timeout=10000)
        except PWTimeout:
            result["reason"] = f"No search results on PriceCharting for '{query}'"
            browser.close()
            return result
        except Exception as e:
            result["reason"] = f"PriceCharting search error: {e}"
            browser.close()
            return result

        # ── Score rows ────────────────────────────────────────────────────────
        rows = page.query_selector_all(ROW_SELECTOR)
        best_score, best_url = -1.0, None

        for row in rows[:15]:
            try:
                title_el = row.query_selector(TITLE_SEL)
                set_el   = row.query_selector(SET_SEL)
                if not title_el:
                    continue
                title_text = title_el.inner_text().strip()
                set_text   = set_el.inner_text().strip() if set_el else ""
                href       = title_el.get_attribute("href") or ""
                score = _score_row(title_text, set_text,
                                   card_name, set_name, card_number)
                if score > best_score:
                    best_score = score
                    best_url   = ("https://www.pricecharting.com" + href
                                  if href.startswith("/") else href)
                    # Decode HTML entities in URL
                    best_url = best_url.replace("&amp;", "&")
            except Exception:
                continue

        if not best_url or best_score < 0.35:
            result["reason"] = (
                f"PriceCharting: no confident match for '{query}' "
                f"(best score {best_score:.2f} < 0.35)"
            )
            browser.close()
            return result

        log(f"PriceCharting: best match score {best_score:.2f} → {best_url}")

        # ── Product page ──────────────────────────────────────────────────────
        try:
            page.goto(best_url, wait_until="domcontentloaded")
            page.wait_for_selector(FULL_PRICE_ROW_SEL, timeout=10000)
        except PWTimeout:
            result["reason"] = (
                f"PriceCharting: product page loaded but no price table "
                f"for '{query}' at {best_url}"
            )
            browser.close()
            return result

        # Secondary title check
        title_el = page.query_selector(PRODUCT_TITLE_SEL)
        if title_el:
            page_title = title_el.inner_text().strip()
            confirm_score = _sim(card_name, page_title)
            if confirm_score < 0.3:
                result["reason"] = (
                    f"PriceCharting: page title '{page_title}' doesn't match "
                    f"'{card_name}' (score {confirm_score:.2f})"
                )
                browser.close()
                return result

        # ── Read grade row ────────────────────────────────────────────────────
        matched_price = None
        price_rows = page.query_selector_all(FULL_PRICE_ROW_SEL)
        for price_row in price_rows:
            cells = price_row.query_selector_all("td")
            if len(cells) < 2:
                continue
            label = cells[0].inner_text().strip()
            if label.upper() == target_label.upper():
                matched_price = _parse_price(cells[1].inner_text())
                break

        browser.close()

        if matched_price is not None:
            result["found"] = True
            result["price"] = matched_price
            result["url"]   = best_url
            log(f"PriceCharting: {target_label} = ${matched_price:.2f} for '{query}'")
        else:
            result["reason"] = (
                f"PriceCharting: matched '{query}' but grade row "
                f"'{target_label}' is empty or not found in price table"
            )

    return result
