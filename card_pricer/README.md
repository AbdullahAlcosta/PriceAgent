# Card Pricing Agent

An agentic pricing tool: give it a Collectr showcase URL, it scrapes your full
card list, prices each card according to your business rules (TCGPlayer /
PriceCharting / eBay Sold), and outputs a clean Excel file.

## ⚠️ Must run on your own machine

This was built and rule-tested here, but **cannot run live in this sandbox** —
this environment's network is locked to a handful of dev domains and can't
reach tcgplayer.com, pricecharting.com, ebay.com, or getcollectr.com.
Download the whole `card_pricer/` folder and run it locally, where you have
normal internet access.

## Setup (one time)

```bash
cd card_pricer
python3 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
playwright install chromium     # downloads the headless browser Playwright drives
```

## Run it

**GUI (recommended)** — a window that stays open so you can price multiple
collections back-to-back without restarting:

```bash
python gui.py
```

Paste a Collectr showcase URL, click Run, and paste another one whenever
that run finishes — no need to relaunch between collections.

**Command line** (for scripting/automation):

```bash
python main.py "https://app.getcollectr.com/showcase/profile/@asos4"
```

Results land in `<Documents>/CardPricingAgent Results/card_pricing_results_<timestamp>.xlsx`
(falls back to the home directory if there's no Documents folder — see
`config._default_output_dir()`). This is deliberately outside the app's own
folder so it survives reinstalling/updating the app and isn't wiped by
`build_windows.bat` re-deleting `dist/` on every rebuild. A full log of
every step, warning, and error is written to `run_log.txt` in that same
folder (and mirrored live into the GUI's log panel when using `gui.py`).

## How it follows your business rules

| Rule | Where it's implemented |
|---|---|
| Classify graded vs raw/sealed | `engine/classify.py` |
| Graded → PriceCharting, log+continue on miss | `engine/pricing_engine.py::price_graded_card` |
| Raw/Sealed → TCGPlayer, eBay fallback on miss | `engine/pricing_engine.py::price_raw_sealed_card` |
| >$500 TCGPlayer price → eBay cross-check | same function, `HIGH_VALUE_THRESHOLD` check |
| eBay = Sold listings only, last 5, averaged | `scrapers/ebay.py` (`LH_Sold=1&LH_Complete=1`) |
| Never halt on one failure | every scraper call is wrapped in try/except in `pricing_engine.py`; `price_card()` itself cannot raise |
| Modular / extensible sources | each source is its own file in `scrapers/`; adding one means writing a new module + one `if` branch in `pricing_engine.py` — nothing else changes |

## If scraping comes back empty (site markup changed)

Each scraper file (`scrapers/collectr.py`, `tcgplayer.py`, `pricecharting.py`,
`ebay.py`) has its CSS selectors defined as constants at the top, with a
comment explaining how to re-derive them via browser DevTools. Set
`config.HEADLESS = False` to watch the agent's browser in real time while
you diagnose it.

## Validating rule logic without the internet

```bash
python test_offline.py
```

This feeds the pricing engine mocked responses covering every rule branch
(normal hit, TCGPlayer miss/fallback, >$500 verification, graded hit, graded
miss) and asserts each one routes correctly — useful after any future edit
to `pricing_engine.py`.

## Project layout

```
card_pricer/
├── gui.py                     desktop GUI entry point (recommended)
├── launcher.py                console entry point (legacy, single run)
├── main.py                    CLI entry point (scripting/automation)
├── config.py                  thresholds, timeouts, headless toggle
├── logger.py                  shared logging
├── engine/
│   ├── classify.py            Card model + graded/raw classification
│   └── pricing_engine.py      orchestrates the business rules
├── scrapers/
│   ├── collectr.py            pulls the card list from your showcase URL
│   ├── tcgplayer.py           raw/sealed pricing
│   ├── pricecharting.py       graded pricing
│   └── ebay.py                sold-listings fallback/verification
├── output/
│   └── excel_writer.py        writes the results workbook
└── test_offline.py            mocked end-to-end rule check
```

## Adding a future pricing source

1. Create `scrapers/new_source.py` with a `search_new_source(query) -> dict`
   function returning `{"found": bool, "price": float|None, "url": str|None}`.
2. Import it in `engine/pricing_engine.py` and add one branch (e.g. "if
   still not found, try new_source").
3. Nothing in `classify.py`, `excel_writer.py`, or `main.py` needs to change.
