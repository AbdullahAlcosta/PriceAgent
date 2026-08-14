"""
Validates collectr.py's JSON extractor against a real snippet copied from the
user's pasted Collectr page source (the escaped RSC payload format).
"""
from scrapers.collectr import _extract_products_json

# This is a trimmed, real excerpt taken directly from the user-provided Collectr
# HTML: same escaping style (\" for quotes, \u0026 for &), same key names.
REAL_SNIPPET = r'''self.__next_f.push([1,"e:[\"$\",\"div\",\"l\",{\"children\":[\"products\":[{\"product_id\":\"241673\",\"catalog_category_name\":\"Pokemon\",\"catalog_group\":\"Chilling Reign\",\"catalog_group_id\":\"2807\",\"product_name\":\"Blaziken VMAX (Alternate Art Secret) \",\"image_url\":\"https://public.getcollectr.com/public-assets/products/product_241673.jpg\",\"card_number\":\"201/198\",\"rarity\":\"Secret Rare\",\"quantity\":\"1\",\"grade_id\":\"52\",\"market_price\":\"380.2900\",\"card_condition\":\"NM\",\"product_sub_type\":\"Holofoil\",\"grade_company\":null,\"ebay_buy_link\":\"https://www.ebay.com/sch/i.html?_nkw=test\"},{\"product_id\":\"211452\",\"catalog_category_name\":\"Pokemon\",\"catalog_group\":\"Sun \u0026 Moon Promo\",\"catalog_group_id\":\"1861\",\"product_name\":\"Umbreon \u0026 Darkrai GX  \",\"image_url\":\"https://public.getcollectr.com/public-assets/products/product_211452.jpg\",\"card_number\":\"SM241\",\"rarity\":\"Promo\",\"quantity\":\"1\",\"grade_id\":\"52\",\"market_price\":\"255.1100\",\"card_condition\":\"NM\",\"product_sub_type\":\"Holofoil\",\"grade_company\":null,\"ebay_buy_link\":\"https://www.ebay.com/sch/i.html?_nkw=test2\"}]}]\n"])'''

products = _extract_products_json(REAL_SNIPPET)
print(f"Extracted {len(products)} products")
for p in products:
    print(f" - {p['product_name'].strip()} | set={p['catalog_group']} | #={p['card_number']} | price={p['market_price']} | grade_company={p['grade_company']}")

assert len(products) == 2
assert products[0]["product_name"].strip() == "Blaziken VMAX (Alternate Art Secret)"
assert products[1]["catalog_group"] == "Sun & Moon Promo"
print("\nJSON extraction PASSED against real Collectr snippet format.")
