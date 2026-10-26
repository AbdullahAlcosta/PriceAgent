# Release Notes

The running version is shown in the GUI's title bar and bottom-right corner,
and logged as the first line of every run in `run_log.txt` — check it first
whenever behavior doesn't match what's described here, especially after a
report that turns out to be an already-fixed bug on an old build.

## v1.2.0 — Collection scraping & query fixes

- **Fixed: every collection was silently missing its first ~30 cards** (or
  coming back completely empty for collections of 30 or fewer). Collectr's
  page renders the first page of cards from the initial page load rather
  than a trackable network request, so the scraper never saw it. It now
  backfills that first page directly after scraping. If you previously saw
  a card count noticeably lower than your real collection size, re-run —
  it should now match.
- **Fixed: a stray empty `( )` could appear in Japanese-card search queries**
  (e.g. `"Rebecca ( ) ( ) Adventure on KAMI's Island (JP)"`), hurting
  PriceCharting matches for those cards.
- **Fixed: results and the run log could be silently deleted on rebuild.**
  They now save to `Documents\CardPricingAgent Results\` instead of next to
  the app, so rebuilding, reinstalling, or updating can never wipe them.

## v1.1.0 — Desktop GUI

- Replaced the command-line prompt with a GUI window (`gui.py`): paste a
  URL, click Run, watch live progress in an on-screen log panel.
- The window stays open after a run finishes — paste another collection's
  URL and click Run again without restarting the app.
- Added "Open Last Result" and "Open Results Folder" buttons.

## v1.0.0 — Initial delivery

- Fixed Japanese-card pricing: cards tagged "(JP)" were being priced off
  TCGPlayer's English-print listing. All Japanese raw cards now route
  through PriceCharting with "(JP)" kept in the search query.
- Removed the unused eBay scraper (preserved on the `archive/ebay-scraper`
  branch) — it was never actually called by the pricing engine.
- Added a "Language" column to the Excel output so Japanese vs. English
  prints are visible at a glance.
