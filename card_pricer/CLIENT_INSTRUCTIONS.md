# Card Pricing Agent — How to Use

## If you received a folder with `CardPricingAgent.exe` in it

This is the simplest version — nothing to install.

1. Unzip the folder anywhere (Desktop is fine).
2. Double-click **`CardPricingAgent.exe`**.
3. A window opens with a box for your Collectr showcase link. Paste it and click **Run** (or press Enter).
4. Wait — pricing a full collection takes a while since it's checking real prices on TCGPlayer, PriceCharting, and eBay for every card. You'll see live progress in the log panel.
5. When it's done, an Excel file with all your prices opens automatically.
6. **The window stays open** — to price another collection, just paste a new link and click **Run** again. No need to close and reopen the app between collections.

Buttons at the bottom let you reopen the last result (**Open Last Result**) or jump to the folder with every past run's Excel file (**Open Results Folder**).

**Windows may show a blue "Windows protected your PC" warning the first time** — this happens for any new program that isn't from a large registered publisher, not because anything is wrong. Click **"More info"** → **"Run anyway"**. You'll only see this once.

That's it. No Python, no setup, no separate downloads. Every time after, it's just double-click → paste link → click Run → wait → done — and the app is ready for your next collection right away.

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
2. A window opens with a box for your Collectr showcase link. Paste it and click **Run**.
3. Wait — pricing a full collection can take a while since it's checking real prices on TCGPlayer, PriceCharting, and eBay for each card.
4. When it's done, an Excel file with all your prices will open automatically.
5. The window stays open — paste another collection's link and click **Run** again whenever you like.

That's it — no need to touch anything else. Every future run is just double-click, paste link, click Run, wait, done.

---

## If something looks wrong

Every run writes a log file at **`results/run_log.txt`** — it records every card it looked up and what happened. If a lot of cards say "Not Found" or the prices look off, send that log file along with your question and it can be diagnosed quickly.
