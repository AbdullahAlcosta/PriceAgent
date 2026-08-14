"""
Offline tests — updated business rules.

Rules:
  1. Raw, TCGPlayer hit ≤ $500          → TCGPlayer only
  2. Raw, TCGPlayer hit > $500           → TCGPlayer + PriceCharting ungraded
  3. Raw, TCGPlayer miss                 → Collectr fallback
  4. Graded, Collectr > $500             → Collectr price + PriceCharting ungraded
  5. Graded, Collectr ≤ $500            → Collectr price only
  6. Graded, PC miss (>$500)             → Collectr price only (PC note added)
  7. Graded, no Collectr price           → Not Found
"""

from unittest.mock import patch
from engine.classify import Card
from engine.pricing_engine import price_all_cards
from output.excel_writer import write_cards_to_excel

test_cards = [
    Card(name="Charizard VMAX",    set_name="Darkness Ablaze", number="020/189",
         collectr_price=45.00),                                          # 1. raw ≤500
    Card(name="Charizard",         set_name="Base Set",        number="4",
         collectr_price=700.00),                                         # 2. raw >500
    Card(name="Pikachu Promo",     set_name="Black Star Promos", number="SWSH001",
         collectr_price=12.00),                                          # 3. raw TCG miss
    Card(name="Charizard",         set_name="Base Set",        number="4",
         condition_or_grade="GRADE 10", collectr_grade_value="10",
         collectr_price=700.00),                                         # 4. graded >500
    Card(name="Umbreon VMAX",      set_name="Evolving Skies",  number="215/203",
         condition_or_grade="GRADE 9", collectr_grade_value="9",
         collectr_price=400.00),                                         # 5. graded ≤500
    Card(name="Mewtwo",            set_name="Base Set",        number="10",
         condition_or_grade="GRADE 10", collectr_grade_value="10",
         collectr_price=600.00),                                         # 6. graded >500, PC miss
    Card(name="Oddish",            set_name="Base Set",        number="69",
         condition_or_grade="GRADE 10", collectr_grade_value="10"),      # 7. no collectr price
]


def fake_tcg(query, card_name="", set_name="", card_number=""):
    if "Pikachu" in query:
        return {"found": False, "price": None, "url": None}
    if "Base Set" in query and "Charizard" in query:
        return {"found": True, "price": 750.00, "url": "https://tcg.com/fake"}
    return {"found": True, "price": 45.00, "url": "https://tcg.com/fake"}


def fake_pc(query, grading_company="", grade_value="", **kwargs):
    if "Mewtwo" in query or "Oddish" in query:
        return {"found": False, "price": None, "url": None,
                "grade_label": "Ungraded",
                "reason": "PriceCharting: no confident match"}
    return {"found": True, "price": 280.00, "url": "https://pc.com/fake",
            "grade_label": "Ungraded", "reason": ""}


with patch("engine.pricing_engine.search_tcgplayer", side_effect=fake_tcg), \
     patch("engine.pricing_engine.search_pricecharting", side_effect=fake_pc):
    results = price_all_cards(test_cards)

print("\n--- RESULTS ---")
for c in results:
    print(f"{c.name:25s} #{c.number:10s} | {c.card_type:10s} "
          f"| tcg={str(c.tcgplayer_price):6} | pc={str(c.pricecharting_price):6} "
          f"| collectr={str(c.collectr_price):6} | source={c.price_source_used}")

# 1. Raw ≤$500 → TCGPlayer only, no PC
assert results[0].tcgplayer_price == 45.0
assert results[0].pricecharting_price is None
assert results[0].price_source_used == "TCGPlayer"

# 2. Raw >$500 → PriceCharting only (skip TCGPlayer)
assert results[1].tcgplayer_price is None
assert results[1].pricecharting_price == 280.0
assert results[1].price_source_used == "PriceCharting (high value)"

# 3. Raw, TCGPlayer miss → Collectr fallback
assert results[2].tcgplayer_price is None
assert results[2].price_source_used == "Collectr Price (fallback)"

# 4. Graded >$500 → Collectr price + PriceCharting ungraded
assert results[3].card_type == "graded"
assert results[3].tcgplayer_price is None
assert results[3].pricecharting_price == 280.0
assert "Collectr" in results[3].price_source_used
assert "PriceCharting" in results[3].price_source_used

# 5. Graded ≤$500 → Collectr price only, no PC
assert results[4].card_type == "graded"
assert results[4].pricecharting_price is None
assert results[4].price_source_used == "Collectr Price (Graded)"

# 6. Graded >$500, PC miss → Collectr price only
assert results[5].card_type == "graded"
assert results[5].pricecharting_price is None
assert results[5].price_source_used == "Collectr Price (Graded)"

# 7. Graded, no Collectr price → Not Found
assert results[6].price_source_used == "Not Found"

print("\nAll business-rule assertions passed ✓")
filepath = write_cards_to_excel(results, filename="offline_test_results.xlsx")
print(f"Sample Excel: {filepath}")
