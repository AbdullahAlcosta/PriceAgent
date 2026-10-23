# Building the standalone .exe (developer notes — not for the client)

This produces a fully self-contained Windows package: Python interpreter +
all dependencies + the Chromium browser Playwright needs, all bundled
together. The client only ever sees `CardPricingAgent.exe` and double-clicks
it — no Python install, no `pip install`, no separate browser download.

## Requirements to build (one time, on your side)

- A **Windows machine** (real or VM). PyInstaller cannot cross-compile —
  building on Mac/Linux produces a Mac/Linux binary, not a Windows `.exe`.
  If you don't have a Windows machine handy, a free option is a Windows
  GitHub Actions runner (`runs-on: windows-latest`) running the same steps
  as `build_windows.bat`.
- Python 3.10+ installed on that Windows machine (only needed for the build
  — the client's machine will need none of this).

## Steps

1. Copy this whole `card_pricer` folder onto the Windows machine.
2. Double-click `build_windows.bat`. It will:
   - Create a clean build environment
   - Install all dependencies + PyInstaller
   - Download Chromium into a local `.ms-playwright` folder (instead of the
     usual hidden system cache) so it can be bundled
   - Run PyInstaller to produce `dist/CardPricingAgent/`
3. Test it: go into `dist/CardPricingAgent/` and double-click
   `CardPricingAgent.exe` directly — confirm the window opens, accepts a
   URL, runs end to end, and stays open afterward ready for another URL, on
   a machine that does NOT have Python installed if you can (a clean VM is
   the real test — your dev machine having Python already installed can
   mask problems).
4. Zip the entire `dist/CardPricingAgent/` folder (not just the .exe --
   PyInstaller's `--onedir` build needs the supporting files alongside it)
   and send that zip to your client. That's the whole deliverable.

## How the bundling actually works

- `PLAYWRIGHT_BROWSERS_PATH` is set to an explicit local folder
  (`pw-browsers`, right next to the build script) before running
  `playwright install chromium`, so the browser downloads to a known,
  predictable location instead of the OS's hidden system cache.
- PyInstaller's `--add-data` flag then bundles that **exact same folder**
  into the compiled `.exe`. (An earlier version of this script used
  `PLAYWRIGHT_BROWSERS_PATH=0` for the download step but pointed
  `--add-data` at the OS's default cache location -- those two locations
  don't match, which silently produced an empty `dist\` folder. Fixed now
  by using one explicit path for both steps.)
- `gui.py` (the build target — see `--windowed ... gui.py` in
  `build_windows.bat`) checks `sys.frozen` (a flag PyInstaller sets at
  runtime) and, if true, points `PLAYWRIGHT_BROWSERS_PATH` at the bundled
  browser folder inside the extracted package -- so the compiled .exe never
  tries to reach the internet for a browser, it already has one.
  `launcher.py` (the older console-only entry point) does the same check,
  and still works if you build it directly, but `gui.py` is what ships.
- `config.py` writes results and the run log to `Documents/CardPricingAgent
  Results/` (falls back to the home directory if there's no Documents
  folder) -- deliberately NOT next to the `.exe` or anywhere under `dist/`.
  This used to write to `results/` next to `sys.executable`, but that meant
  every past result and the run log got silently deleted by this very
  script's `rmdir /s /q dist` step on the next rebuild -- which is exactly
  what happened to a client's "missing" run log. Keeping output outside
  the app folder means rebuilding, reinstalling, or re-unzipping a newer
  version can never touch it.
- The build script now checks the exit code after every step (pip install,
  playwright install, pyinstaller itself) and stops with a clear error
  message instead of silently continuing -- if `dist\CardPricingAgent\
  CardPricingAgent.exe` doesn't exist at the end, the script will tell you
  why rather than exiting quietly.

## Known caveats

- **Unsigned .exe**: Windows SmartScreen will show a "Windows protected your
  PC" warning on first run, since the executable isn't signed with a paid
  code-signing certificate. The client clicks "More info" → "Run anyway"
  once. Getting rid of this entirely requires purchasing a code-signing
  certificate (~$100-400/year from a CA) and signing the build -- a
  reasonable thing to add later if this becomes a recurring product, but
  not required for it to work.
- **Antivirus false positives**: PyInstaller-built executables occasionally
  trigger heuristic AV warnings (unsigned binary + browser automation
  library) even though there's nothing malicious in it. If a client's AV
  quarantines it, an exception/allowlist entry resolves it.
- **File size**: expect the final zipped package to be several hundred MB,
  almost entirely from the bundled Chromium browser. This is unavoidable --
  it's the actual cost of "client never installs anything."
- **Still needs live internet access** at runtime to actually reach
  TCGPlayer, PriceCharting, eBay, and Collectr -- bundling removes the
  *setup* dependency, not the need for internet during use.
