"""
Card Pricing Agent — desktop GUI.

This is the day-to-day app the client runs (via run.command / run.bat, or
the bundled CardPricingAgent.exe). Unlike the old command-line launcher,
this window stays open after a run finishes: paste another Collectr URL
and click Run again to price another collection in the same session.
"""

import os
import sys
import platform
import subprocess
import threading
import queue
import tkinter as tk
from tkinter import ttk, messagebox

# --- Bundled-exe support -----------------------------------------------
# When this script has been packaged into a Windows .exe with PyInstaller
# (see build_windows.bat), PyInstaller sets sys.frozen = True and extracts
# any bundled data (including the Chromium browser Playwright needs) into
# sys._MEIPASS. We point Playwright at that bundled browser here, BEFORE
# importing anything that touches Playwright, so the compiled .exe never
# tries to download a browser over the internet -- it's already inside it.
if getattr(sys, "frozen", False):
    bundled_browsers = os.path.join(sys._MEIPASS, "ms-playwright")  # type: ignore[attr-defined]
    if os.path.isdir(bundled_browsers):
        os.environ["PLAYWRIGHT_BROWSERS_PATH"] = bundled_browsers
# -------------------------------------------------------------------------

import config
from scrapers.collectr import scrape_collectr_showcase
from engine.pricing_engine import price_all_cards
from output.excel_writer import write_cards_to_excel
from logger import log, add_log_listener


def _open_path(path: str):
    """Open a file or folder in whatever the OS's default app is."""
    system = platform.system()
    try:
        if system == "Windows":
            os.startfile(path)  # type: ignore[attr-defined]
        elif system == "Darwin":
            subprocess.run(["open", path])
        else:
            subprocess.run(["xdg-open", path])
    except Exception:
        pass


class CardPricingApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        root.title("Card Pricing Agent")
        root.geometry("780x560")
        root.minsize(640, 420)

        self.msg_queue: "queue.Queue" = queue.Queue()
        self.is_running = False
        self.last_result_path: str | None = None

        self._build_widgets()
        add_log_listener(lambda line: self.msg_queue.put(("log", line)))
        self.root.after(150, self._poll_queue)
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    # ------------------------------------------------------------------ UI
    def _build_widgets(self):
        pad = {"padx": 10, "pady": 6}

        top = ttk.Frame(self.root)
        top.pack(fill="x", **pad)

        ttk.Label(top, text="Collectr showcase URL:").pack(anchor="w")
        url_row = ttk.Frame(top)
        url_row.pack(fill="x", pady=(4, 0))
        self.url_var = tk.StringVar()
        self.url_entry = ttk.Entry(url_row, textvariable=self.url_var)
        self.url_entry.pack(side="left", fill="x", expand=True)
        self.url_entry.bind("<Return>", lambda _e: self._start_run())
        self.run_btn = ttk.Button(url_row, text="Run", command=self._start_run)
        self.run_btn.pack(side="left", padx=(8, 0))

        self.status_var = tk.StringVar(
            value="Ready. Paste a Collectr showcase URL above and click Run."
        )
        ttk.Label(self.root, textvariable=self.status_var, foreground="#1F4E79").pack(
            anchor="w", padx=10
        )

        self.progress = ttk.Progressbar(self.root, mode="indeterminate")
        self.progress.pack(fill="x", padx=10, pady=(0, 6))

        log_frame = ttk.Frame(self.root)
        log_frame.pack(fill="both", expand=True, padx=10, pady=(0, 6))
        self.log_box = tk.Text(
            log_frame, wrap="word", state="disabled",
            bg="#0f1117", fg="#d6d6d6", insertbackground="#d6d6d6",
            font=("Consolas", 9), height=10,
        )
        scroll = ttk.Scrollbar(log_frame, command=self.log_box.yview)
        self.log_box.configure(yscrollcommand=scroll.set)
        self.log_box.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")

        bottom = ttk.Frame(self.root)
        bottom.pack(fill="x", padx=10, pady=(0, 10))
        self.open_file_btn = ttk.Button(
            bottom, text="Open Last Result", command=self._open_last_result,
            state="disabled",
        )
        self.open_file_btn.pack(side="left")
        ttk.Button(
            bottom, text="Open Results Folder", command=self._open_results_folder
        ).pack(side="left", padx=(8, 0))
        ttk.Button(bottom, text="Clear Log", command=self._clear_log).pack(side="right")

    # -------------------------------------------------------- log plumbing
    def _poll_queue(self):
        try:
            while True:
                kind, payload = self.msg_queue.get_nowait()
                if kind == "log":
                    self._append_log(payload)
                elif kind == "done":
                    self._on_run_finished(payload)
                elif kind == "error":
                    self._on_run_error(payload)
        except queue.Empty:
            pass
        self.root.after(150, self._poll_queue)

    def _append_log(self, line: str):
        self.log_box.configure(state="normal")
        self.log_box.insert("end", line + "\n")
        self.log_box.see("end")
        self.log_box.configure(state="disabled")

    def _clear_log(self):
        self.log_box.configure(state="normal")
        self.log_box.delete("1.0", "end")
        self.log_box.configure(state="disabled")

    # ------------------------------------------------------- run lifecycle
    def _start_run(self):
        if self.is_running:
            return
        url = self.url_var.get().strip()
        if not url:
            messagebox.showwarning("Missing URL", "Paste a Collectr showcase URL first.")
            return

        self.is_running = True
        self.run_btn.configure(state="disabled", text="Working...")
        self.url_entry.configure(state="disabled")
        self.status_var.set(
            "Scraping and pricing — this can take a while for large collections..."
        )
        self.progress.start(12)

        threading.Thread(target=self._run_pipeline, args=(url,), daemon=True).start()

    def _run_pipeline(self, url: str):
        try:
            log(f"=== Card Pricing Agent starting for {url} ===")
            cards = scrape_collectr_showcase(url)
            if not cards:
                self.msg_queue.put((
                    "error",
                    "No cards were found at that URL. Double-check the link and try again.",
                ))
                return
            priced_cards = price_all_cards(cards)
            filepath = write_cards_to_excel(priced_cards)
            log(f"=== Done. {len(priced_cards)} cards processed. Results: {filepath} ===")
            self.msg_queue.put(("done", (filepath, len(priced_cards))))
        except Exception as e:
            log(f"Unexpected error: {e}", level="ERROR")
            self.msg_queue.put(("error", str(e)))

    def _on_run_finished(self, payload):
        filepath, count = payload
        self.last_result_path = filepath
        self.progress.stop()
        self.is_running = False
        self.run_btn.configure(state="normal", text="Run")
        self.url_entry.configure(state="normal")
        self.open_file_btn.configure(state="normal")
        self.status_var.set(f"Done — priced {count} cards. Ready for another URL.")
        _open_path(filepath)
        messagebox.showinfo(
            "Done",
            f"Priced {count} cards.\n\nResults saved to:\n{filepath}\n\n"
            "You can paste another Collectr URL above to run again.",
        )

    def _on_run_error(self, message: str):
        self.progress.stop()
        self.is_running = False
        self.run_btn.configure(state="normal", text="Run")
        self.url_entry.configure(state="normal")
        self.status_var.set("Something went wrong — see log below, or try again.")
        messagebox.showerror("Error", message)

    # ------------------------------------------------------------- helpers
    def _open_last_result(self):
        if self.last_result_path and os.path.exists(self.last_result_path):
            _open_path(self.last_result_path)

    def _open_results_folder(self):
        _open_path(config.OUTPUT_DIR)

    def _on_close(self):
        if self.is_running:
            if not messagebox.askyesno(
                "Run in progress",
                "A pricing run is still in progress. Close anyway?",
            ):
                return
        self.root.destroy()


def main():
    root = tk.Tk()
    try:
        style = ttk.Style(root)
        if platform.system() == "Windows" and "vista" in style.theme_names():
            style.theme_use("vista")
        elif "clam" in style.theme_names():
            style.theme_use("clam")
    except Exception:
        pass
    CardPricingApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
