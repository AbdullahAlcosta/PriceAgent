import re
from dataclasses import dataclass, field
from typing import Optional

GRADING_COMPANIES = ["PSA", "BGS", "CGC", "SGC", "ACE", "HGA", "TAG"]
GRADE_PATTERN = re.compile(
    r"\b(" + "|".join(GRADING_COMPANIES) + r")\s*-?\s*(\d{1,2}(\.\d)?)\b",
    re.IGNORECASE,
)
SEALED_KEYWORDS = [
    "booster box", "booster pack", "etb", "elite trainer box", "sealed",
    "case", "bundle", "tin", "collection box", "blister",
]


@dataclass
class Card:
    name: str
    set_name: str = ""
    number: str = ""
    condition_or_grade: str = ""
    image_url: str = ""
    quantity: int = 1
    foil: str = ""

    # Filled by classify_card
    card_type: str = ""
    grading_company: Optional[str] = None
    grade_value: Optional[str] = None

    # Prices
    collectr_price: Optional[float] = None
    ebay_listing_price: Optional[float] = None   # from Collectr JSON
    tcgplayer_price: Optional[float] = None
    pricecharting_price: Optional[float] = None

    # Pre-built URLs from Collectr JSON
    tcgplayer_search_url: str = ""
    ebay_sold_url: str = ""
    pricecharting_url: str = ""
    collectr_item_url: str = ""
    pricecharting_result_url: str = ""  # actual matched product page URL

    price_source_used: str = ""
    notes: str = ""

    # Collectr-specific grade info (grade_id based, company unknown)
    collectr_grade_id: str = ""
    collectr_grade_value: str = ""


def classify_card(card: Card) -> Card:
    text = f"{card.condition_or_grade} {card.name}".strip()

    # Collectr grade_id-based detection (set by collectr.py scraper)
    # Format: "GRADE 10", "GRADE 9", "GRADED" etc.
    if card.condition_or_grade.upper().startswith("GRADE") or \
       card.condition_or_grade.upper() == "GRADED":
        card.card_type = "graded"
        # grade_value comes from collectr_grade_value set by scraper
        card.grade_value = card.collectr_grade_value or ""
        # grading_company unknown from API — leave empty
        card.grading_company = ""
        return card

    # Standard grading company pattern (PSA 10, BGS 9.5 etc.)
    match = GRADE_PATTERN.search(text)
    if match:
        card.card_type = "graded"
        card.grading_company = match.group(1).upper()
        card.grade_value = match.group(2)
        return card

    lower_name = card.name.lower()
    if any(keyword in lower_name for keyword in SEALED_KEYWORDS):
        card.card_type = "raw_sealed"
        return card

    card.card_type = "raw_sealed"
    return card
