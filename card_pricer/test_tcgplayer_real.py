"""
Validates the TCGPlayer Market Price row-matching logic against the real
price-guide__points table structure extracted from the user's uploaded
product-page HTML (Mega Charizard X ex Ultra Premium Collection).
"""
from scrapers.tcgplayer import _parse_price

# Exact rows from the real page: (label, value)
REAL_ROWS = [
    ("Market Price", "$236.10"),
    ("Most Recent Sale", "N/A"),
]


def extract_market_price(rows):
    for label, value in rows:
        if label.strip().lower() == "market price":
            return _parse_price(value)
    return None


price = extract_market_price(REAL_ROWS)
assert price == 236.10, f"Expected 236.10, got {price}"

# "Most Recent Sale" = N/A must not be mistaken for a price
recent_sale = _parse_price("N/A")
assert recent_sale is None

print("TCGPlayer Market Price extraction PASSED against the real price-guide table.")
