"""
Validates the PriceCharting grade-matching logic against the real
"Full Price Guide" table structure extracted from the user's uploaded
product-page HTML (Mega Charizard X ex #125, Phantasmal Flames).
"""
from scrapers.pricecharting import _target_row_label, _parse_price

# Exact rows from the real page, as (label, price_text)
REAL_ROWS = [
    ("Ungraded", "$840.38"),
    ("Grade 1", "-"),
    ("Grade 2", "$253.00"),
    ("Grade 3", "$281.00"),
    ("Grade 4", "$331.00"),
    ("Grade 5", "$389.00"),
    ("Grade 6", "$486.00"),
    ("Grade 7", "$608.00"),
    ("Grade 8", "$759.61"),
    ("Grade 9", "$790.00"),
    ("Grade 9.5", "$1,257.47"),
    ("TAG 10", "$2,049.50"),
    ("ACE 10", "$1,271.55"),
    ("SGC 10", "$1,245.91"),
    ("CGC 10", "$1,124.00"),
    ("PSA 10", "$2,010.00"),
    ("BGS 10", "$3,313.46"),
    ("BGS 10 Black", "$37,000.00"),
    ("CGC 10 Pristine", "$2,322.65"),
]


def lookup(grading_company, grade_value):
    target = _target_row_label(grading_company, grade_value)
    for label, price_text in REAL_ROWS:
        if label.upper() == target:
            return _parse_price(price_text)
    return None


# Key quirk test: BGS 9.5 should hit the company-agnostic "Grade 9.5" row, NOT fail
# looking for a nonexistent "BGS 9.5" row.
assert lookup("BGS", "9.5") == 1257.47, "BGS 9.5 should resolve to the shared 'Grade 9.5' row"
assert lookup("PSA", "9.5") == 1257.47, "PSA 9.5 should also resolve to the shared 'Grade 9.5' row"
assert lookup("CGC", "9") == 790.00

# Grade 10 IS split by company
assert lookup("PSA", "10") == 2010.00
assert lookup("BGS", "10") == 3313.46
assert lookup("CGC", "10") == 1124.00
assert lookup("SGC", "10") == 1245.91
assert lookup("TAG", "10") == 2049.50
assert lookup("ACE", "10") == 1271.55

# Grade 1 has no sales -> "-" must parse to None, not 0 or a crash
assert lookup("PSA", "1") is None

print("All PriceCharting grade-matching assertions passed against the real Full Price Guide table.")
