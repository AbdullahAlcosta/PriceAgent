# Card Pricing Agent — How to Use

## If you received a folder with `CardPricingAgent.exe` in it

This is the simplest version — nothing to install.

1. Unzip the folder anywhere (Desktop is fine).
2. Double-click **`CardPricingAgent.exe`**.
3. A window will open asking for your Collectr showcase link. Paste it and press Enter.
4. Wait — pricing a full collection takes a while since it's checking real prices on TCGPlayer, PriceCharting, and eBay for every card.
5. When it's done, an Excel file with all your prices opens automatically.

**Windows may show a blue "Windows protected your PC" warning the first time** — this happens for any new program that isn't from a large registered publisher, not because anything is wrong. Click **"More info"** → **"Run anyway"**. You'll only see this once.

That's it. No Python, no setup, no separate downloads. Every time after, it's just double-click → paste link → wait → done.

---

## If you instead received a folder with `run.bat` / `run.command` (older version)

## One-time setup (Mac)

1. If you don't already have Python installed: go to **python.org/downloads**, click the big yellow download button, and run the installer with default settings.
2. Unzip the folder somewhere easy to find, like your Desktop.
3. Double-click **`run.command`**.
   - The first time, a black window will open and do some setup — this takes a few minutes. You'll see a lot of text scroll by; that's normal.
   - When it says "Setup complete!", it's ready.

*If macOS blocks it the first time ("cannot be opened because it is from an unidentified developer"):* right-click `run.command` → **Open** → click **Open** again in the popup. You only need to do this once.

## One-time setup (Windows)

1. If you don't already have Python installed: go to **python.org/downloads**, click the download button, run the installer, and **make sure to check "Add Python to PATH"** during install — this is important.
2. Unzip the folder somewhere easy to find, like your Desktop.
3. Double-click **`run.bat`**.
   - The first time, a black window will open and do some setup — this takes a few minutes.
   - When it says "Setup complete!", it's ready.

## Using it (every time after setup)

1. Double-click `run.command` (Mac) or `run.bat` (Windows).
2. It will ask you to paste your Collectr showcase link. Paste it and press Enter.
3. Wait — pricing a full collection can take a while since it's checking real prices on TCGPlayer, PriceCharting, and eBay for each card.
4. When it's done, an Excel file with all your prices will open automatically.

That's it — no need to touch anything else. Every future run is just double-click, paste link, wait, done.

---

## If something looks wrong

Every run writes a log file at **`results/run_log.txt`** — it records every card it looked up and what happened. If a lot of cards say "Not Found" or the prices look off, send that log file along with your question and it can be diagnosed quickly.
