"""
eBay Sold Listings scraper.

The page structure on eBay's search results has changed -- all previous
selectors are failing. New approach: instead of relying on class-based
selectors (which eBay changes frequently), we use a combination of
structural selectors and data attributes which are more stable.

We also try a direct URL approach: eBay's sold listings page uses
a predictable URL structure and the items are in a well-known container.
"""

import re
from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout
from logger import log
from config import HEADLESS, NAV_TIMEOUT_MS, EBAY_SOLD_COUNT

SEARCH_URL = (
    "https://www.ebay.com/sch/i.html"
    "?_nkw={query}"
    "&LH_Sold=1"
    "&LH_Complete=1"
    "&LH_ItemLocation=1"
    "&LH_PrefLoc=2"
    "&_stpos=10001"
    "&_sop=13"
    "&_ipg=60"
)

PRICE_CLEAN_RE = re.compile(r"[^\d.]")

EBAY_DISMISS_SELECTORS = [
    "button#gdpr-banner-accept",
    "button[aria-label*='Accept']",
    "button[aria-label*='accept']",
    "#consent-modal button",
    "button.btn--primary",
]


def _dismiss_ebay_dialogs(page):
    for sel in EBAY_DISMISS_SELECTORS:
        try:
            btn = page.query_selector(sel)
            if btn:
                btn.click(timeout=3000)
                page.wait_for_timeout(400)
                return
        except Exception:
            continue


def _clean_query(query: str) -> str:
    cleaned = re.sub(r"[()[\]{}]", " ", query)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned


def _parse_price(text: str) -> float | None:
    if not text:
        return None
    parts = re.findall(r"[\d,]+\.\d{2}", text)
    if not parts:
        return None
    try:
        floats = [float(p.replace(",", "")) for p in parts]
        return round(sum(floats) / len(floats), 2)
    except ValueError:
        return None


def _looks_like_mismatch(query: str, title: str) -> bool:
    title_lower = title.lower()
    significant = [w for w in query.lower().split() if len(w) > 2]
    if not significant:
        return False
    hits = sum(1 for w in significant if w in title_lower)
    return hits == 0


def _extract_prices_from_page(page, query: str) -> list[float]:
    """
    Try multiple strategies to extract prices from eBay sold listings page.
    Returns list of prices found.
    """
    prices = []

    # Strategy 1: Use JavaScript to extract all price elements
    # eBay renders prices in spans with data-testid or aria-label attributes
    try:
        price_data = page.evaluate("""
            () => {
                const results = [];
                // Try multiple selector patterns
                const selectors = [
                    '[data-testid="item-price"]',
                    '.s-item__price',
                    '[class*="price"][class*="item"]',
                    '.srp-results .s-item .notranslate',
                    'li[data-viewport] .s-item__price',
                    '.srp-river-results .s-item__price',
                    '[itemprop="price"]',
                    '.positive-feedback-score + span',
                ];

                for (const sel of selectors) {
                    const els = document.querySelectorAll(sel);
                    if (els.length > 1) {
                        els.forEach(el => {
                            const txt = el.textContent.trim();
                            if (txt && txt.includes('$')) results.push(txt);
                        });
                        if (results.length > 0) break;
                    }
                }

                // Fallback: find all text nodes containing dollar amounts
                // in the main results area
                if (results.length === 0) {
                    const walker = document.createTreeWalker(
                        document.querySelector('#srp-river-results, .srp-results, main') || document.body,
                        NodeFilter.SHOW_TEXT
                    );
                    let node;
                    while ((node = walker.nextNode()) && results.length < 30) {
                        const txt = node.textContent.trim();
                        if (/^\$[\d,]+\.\d{2}$/.test(txt)) {
                            results.push(txt);
                        }
                    }
                }
                return results;
            }
        """)

        if price_data:
            for price_text in price_data:
                p = _parse_price(price_text)
                if p and p > 0:
                    prices.append(p)

    except Exception as e:
        log(f"eBay JS price extraction error: {e}", level="WARN")

    # Strategy 2: Try getting all text that looks like a sold price
    # by reading the full page text and finding price patterns near "Sold"
    if not prices:
        try:
            page_text = page.inner_text("body")
            # Find prices that appear near sold indicators
            price_matches = re.findall(r'\$[\d,]+\.\d{2}', page_text)
            for match in price_matches[:20]:
                p = _parse_price(match)
                if p and 0.01 < p < 100000:
                    prices.append(p)
        except Exception as e:
            log(f"eBay text extraction error: {e}", level="WARN")

    # Filter out obvious duplicates and keep only reasonable prices
    seen = set()
    unique_prices = []
    for p in prices:
        if p not in seen:
            seen.add(p)
            unique_prices.append(p)

    return unique_prices


def get_ebay_sold_average(query: str) -> dict:
    result = {"found": False, "prices": [], "average": None}
    clean = _clean_query(query)
    url = SEARCH_URL.format(query=clean.replace(" ", "+").replace("&", "%26"))

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=HEADLESS,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--disable-features=IsolateOrigins,site-per-process",
                "--no-sandbox",
            ]
        )
        context = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1280, "height": 800},
            locale="en-US",
            timezone_id="America/New_York",
            extra_http_headers={
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.9",
                "Accept-Encoding": "gzip, deflate, br",
                "Sec-Fetch-Dest": "document",
                "Sec-Fetch-Mode": "navigate",
                "Sec-Fetch-Site": "none",
                "Upgrade-Insecure-Requests": "1",
            }
        )

        # Remove webdriver property that bot detectors check
        page = context.new_page()
        page.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
            Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3] });
            Object.defineProperty(navigator, 'languages', { get: () => ['en-US', 'en'] });
        """)
        page.set_default_timeout(NAV_TIMEOUT_MS)

        try:
            log(f"eBay Sold: searching '{clean}'")
            page.goto(url, wait_until="domcontentloaded")
            _dismiss_ebay_dialogs(page)

            # Wait for actual listing content
            item_loaded = False
            for wait_sel in ["li.s-card", "li.s-item.s-item__pl-on-bottom", "li.s-item", ".srp-results li"]:
                try:
                    page.wait_for_selector(wait_sel, timeout=8000)
                    item_loaded = True
                    log(f"eBay Sold: items loaded with selector '{wait_sel}'")
                    break
                except PWTimeout:
                    continue

            if not item_loaded:
                page.wait_for_timeout(3000)

        except Exception as e:
            log(f"eBay Sold: page load error for '{clean}': {e}", level="WARN")
            browser.close()
            # Retry once on network errors
            if "ERR_NETWORK" in str(e) or "net::" in str(e):
                log(f"eBay Sold: network error — waiting 5s then retrying once...", level="WARN")
                import time; time.sleep(5)
                try:
                    with sync_playwright() as p2:
                        b2 = p2.chromium.launch(headless=HEADLESS)
                        pg2 = b2.new_page()
                        pg2.set_default_timeout(NAV_TIMEOUT_MS)
                        pg2.goto(url, wait_until="domcontentloaded")
                        pg2.wait_for_timeout(3000)
                        prices = _extract_prices_from_page(pg2, clean)
                        b2.close()
                        if prices:
                            selected = prices[:EBAY_SOLD_COUNT]
                            result["found"] = True
                            result["prices"] = selected
                            result["average"] = round(sum(selected) / len(selected), 2)
                            log(f"eBay Sold (retry): {len(selected)} prices, avg ${result['average']:.2f}")
                except Exception as e2:
                    log(f"eBay Sold: retry also failed: {e2}", level="ERROR")
            return result

        prices = []

        # Primary: try confirmed CSS selectors for price elements
        PRICE_SELECTORS_TO_TRY = [
            "li.s-item .s-item__price",
            "li.s-item__pl-on-bottom .s-item__price",
            ".s-item__price",
            "[data-testid='item-price']",
            ".notranslate[class*='price']",
        ]
        for sel in PRICE_SELECTORS_TO_TRY:
            try:
                els = page.query_selector_all(sel)
                if len(els) > 1:
                    log(f"eBay Sold: found {len(els)} prices with selector '{sel}'")
                    for el in els:
                        txt = el.inner_text().strip()
                        p = _parse_price(txt)
                        if p and 0.01 < p < 100000:
                            prices.append(p)
                    if prices:
                        break
            except Exception:
                continue

        # Fallback: JS extraction if selectors found nothing
        if not prices:
            prices = _extract_prices_from_page(page, clean)

        browser.close()

        if prices:
            # Take the most recent EBAY_SOLD_COUNT prices
            selected = prices[:EBAY_SOLD_COUNT]
            result["found"] = True
            result["prices"] = selected
            result["average"] = round(sum(selected) / len(selected), 2)
            log(f"eBay Sold: {len(selected)} prices, avg ${result['average']:.2f} for '{clean}'")
        else:
            log(f"eBay Sold: no prices found for '{clean}'", level="WARN")

    return result
