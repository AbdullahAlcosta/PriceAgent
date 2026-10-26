"""
Card Pricing Agent — desktop GUI.

This is the day-to-day app the client runs (via run.command / run.bat, or
the bundled CardPricingAgent.exe). Unlike the old command-line launcher,
this window stays open after a run finishes: paste another Collectr URL
and click Run again to price another collection in the same session.

Built on CustomTkinter (a thin layer over Tkinter) for a modern look --
rounded widgets, a proper color palette, light/dark mode -- without the
bundle-size or complexity cost of a web-based UI. Dialogs (messagebox)
stay as plain Tkinter, which is a deliberate, low-risk choice: CustomTkinter
has no dialog widgets of its own, and the OS-native alert look is a minor
and expected inconsistency next to the custom main window.
"""

import os
import sys
import platform
import subprocess
import threading
import queue
import time
import math
import tkinter as tk
from tkinter import messagebox
import customtkinter as ctk

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

# Theme-aware (light_mode, dark_mode) colors for the status line.
COLOR_WORKING = ("#1F6FB2", "#5AA9E6")
COLOR_DONE = ("#1F7A4D", "#4CC38A")
COLOR_ERROR = ("#B3261E", "#FF6B6B")
COLOR_IDLE = ("gray10", "gray90")

PROGRESS_STEP = 0.025  # per animation tick -- full sweep takes ~1.6s either way
PULSE_INTERVAL_MS = 450
TICK_INTERVAL_MS = 1000


def _format_duration(seconds: float) -> str:
    seconds = max(0, int(seconds))
    minutes, secs = divmod(seconds, 60)
    return f"{minutes}:{secs:02d}"


def _estimate_seconds(num_cards: int) -> int:
    """Rough ETA for pricing num_cards -- see config.AVG_SECONDS_PER_CARD_PER_WORKER."""
    batches = math.ceil(num_cards / config.PARALLEL_WORKERS)
    return batches * config.AVG_SECONDS_PER_CARD_PER_WORKER


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
    def __init__(self, root: "ctk.CTk"):
        self.root = root
        root.title(f"Card Pricing Agent v{config.APP_VERSION}")
        root.geometry("780x560")
        root.minsize(640, 420)

        self.msg_queue: "queue.Queue" = queue.Queue()
        self.is_running = False
        self.last_result_path: str | None = None
        self.run_start_time: float | None = None
        self.num_cards: int | None = None
        self.eta_seconds: int | None = None

        # "idle" | "scraping" | "pricing" -- gates which animation loop is
        # allowed to keep rescheduling itself, so the pulsing-dots loop and
        # the elapsed-time ticker never fight over the status text.
        self._phase = "idle"
        self._progress_value = 0.0
        self._progress_direction = 1
        self._pulse_base = ""
        self._pulse_dots = 0

        self._build_widgets()
        add_log_listener(lambda line: self.msg_queue.put(("log", line)))
        self.root.after(150, self._poll_queue)
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        log(f"Card Pricing Agent v{config.APP_VERSION} starting (GUI).")

    # ------------------------------------------------------------------ UI
    def _build_widgets(self):
        pad = {"padx": 14, "pady": 8}

        top = ctk.CTkFrame(self.root, fg_color="transparent")
        top.pack(fill="x", **pad)

        ctk.CTkLabel(
            top, text="Collectr showcase URL",
            font=ctk.CTkFont(size=13, weight="bold"),
        ).pack(anchor="w")
        url_row = ctk.CTkFrame(top, fg_color="transparent")
        url_row.pack(fill="x", pady=(6, 0))
        self.url_var = tk.StringVar()
        self.url_entry = ctk.CTkEntry(
            url_row, textvariable=self.url_var,
            placeholder_text="https://app.getcollectr.com/showcase/profile/@you",
            height=36,
        )
        self.url_entry.pack(side="left", fill="x", expand=True)
        self.url_entry.bind("<Return>", lambda _e: self._start_run())
        self.run_btn = ctk.CTkButton(
            url_row, text="Run", command=self._start_run,
            width=90, height=36, corner_radius=8,
        )
        self.run_btn.pack(side="left", padx=(8, 0))

        self.status_var = tk.StringVar(
            value="Ready. Paste a Collectr showcase URL above and click Run."
        )
        self.status_label = ctk.CTkLabel(
            self.root, textvariable=self.status_var, text_color=COLOR_IDLE,
            anchor="w", font=ctk.CTkFont(size=12),
        )
        self.status_label.pack(fill="x", padx=14)

        self.progress = ctk.CTkProgressBar(self.root, height=8, corner_radius=4)
        self.progress.set(0)
        self.progress.pack(fill="x", padx=14, pady=(6, 8))

        log_frame = ctk.CTkFrame(self.root, fg_color="transparent")
        log_frame.pack(fill="both", expand=True, padx=14, pady=(0, 8))
        self.log_box = ctk.CTkTextbox(
            log_frame, wrap="word", state="disabled",
            fg_color="#0f1117", text_color="#d6d6d6",
            font=ctk.CTkFont(family="Consolas", size=12),
            corner_radius=8,
        )
        self.log_box.pack(fill="both", expand=True)

        bottom = ctk.CTkFrame(self.root, fg_color="transparent")
        bottom.pack(fill="x", padx=14, pady=(0, 14))
        self.open_file_btn = ctk.CTkButton(
            bottom, text="Open Last Result", command=self._open_last_result,
            state="disabled", fg_color="transparent", border_width=1,
            text_color=COLOR_IDLE,
        )
        self.open_file_btn.pack(side="left")
        ctk.CTkButton(
            bottom, text="Open Results Folder", command=self._open_results_folder,
            fg_color="transparent", border_width=1, text_color=COLOR_IDLE,
        ).pack(side="left", padx=(8, 0))
        ctk.CTkButton(
            bottom, text="Clear Log", command=self._clear_log,
            fg_color="transparent", border_width=1, text_color=COLOR_IDLE,
        ).pack(side="right")
        ctk.CTkLabel(
            bottom, text=f"v{config.APP_VERSION}", text_color=("gray60", "gray50"),
        ).pack(side="right", padx=(0, 10))

    # -------------------------------------------------------- log plumbing
    def _poll_queue(self):
        try:
            while True:
                kind, payload = self.msg_queue.get_nowait()
                if kind == "log":
                    self._append_log(payload)
                elif kind == "scraped":
                    self._on_scraped(payload)
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

    # ----------------------------------------------------------- animation
    def _animate_progress(self):
        if self._phase == "idle":
            self.progress.set(0)
            return
        self._progress_value += self._progress_direction * PROGRESS_STEP
        if self._progress_value >= 1.0:
            self._progress_value = 1.0
            self._progress_direction = -1
        elif self._progress_value <= 0.0:
            self._progress_value = 0.0
            self._progress_direction = 1
        self.progress.set(self._progress_value)
        self.root.after(30, self._animate_progress)

    def _pulse_tick(self):
        if self._phase != "scraping":
            return
        self._pulse_dots = (self._pulse_dots + 1) % 4
        self.status_var.set(self._pulse_base + "." * self._pulse_dots)
        self.root.after(PULSE_INTERVAL_MS, self._pulse_tick)

    def _tick_elapsed(self):
        if self._phase != "pricing":
            return
        elapsed = time.time() - self.run_start_time
        self.status_var.set(
            f"Pricing {self.num_cards} cards — elapsed {_format_duration(elapsed)}, "
            f"estimated total ~{_format_duration(self.eta_seconds)}"
        )
        self.root.after(TICK_INTERVAL_MS, self._tick_elapsed)

    # ------------------------------------------------------- run lifecycle
    def _start_run(self):
        if self.is_running:
            return
        url = self.url_var.get().strip()
        if not url:
            messagebox.showwarning("Missing URL", "Paste a Collectr showcase URL first.")
            return

        self.is_running = True
        self.run_start_time = time.time()
        self.num_cards = None
        self.eta_seconds = None
        self.run_btn.configure(state="disabled", text="Working...")
        self.url_entry.configure(state="disabled")
        self.status_label.configure(text_color=COLOR_WORKING)

        self._phase = "scraping"
        self._pulse_base = "Scraping your collection "
        self._pulse_dots = 0
        self.status_var.set(self._pulse_base)
        self._pulse_tick()

        self._progress_value = 0.0
        self._progress_direction = 1
        self._animate_progress()

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
            self.msg_queue.put(("scraped", (len(cards), _estimate_seconds(len(cards)))))
            priced_cards = price_all_cards(cards)
            filepath = write_cards_to_excel(priced_cards)
            log(f"=== Done. {len(priced_cards)} cards processed. Results: {filepath} ===")
            self.msg_queue.put(("done", (filepath, len(priced_cards))))
        except Exception as e:
            log(f"Unexpected error: {e}", level="ERROR")
            self.msg_queue.put(("error", str(e)))

    def _on_scraped(self, payload):
        num_cards, eta_seconds = payload
        self.num_cards = num_cards
        self.eta_seconds = eta_seconds
        self._phase = "pricing"
        self.status_var.set(
            f"Pricing {num_cards} cards — estimated time: ~{_format_duration(eta_seconds)}"
        )
        self._tick_elapsed()

    def _on_run_finished(self, payload):
        filepath, count = payload
        self.last_result_path = filepath
        self._phase = "idle"
        self.is_running = False
        self.run_btn.configure(state="normal", text="Run")
        self.url_entry.configure(state="normal")
        self.open_file_btn.configure(state="normal", text_color=COLOR_IDLE)
        self.status_label.configure(text_color=COLOR_DONE)
        elapsed_str = (
            _format_duration(time.time() - self.run_start_time)
            if self.run_start_time else "?"
        )
        self.status_var.set(
            f"Done — priced {count} cards in {elapsed_str}. Ready for another URL."
        )
        _open_path(filepath)
        messagebox.showinfo(
            "Done",
            f"Priced {count} cards in {elapsed_str}.\n\nResults saved to:\n{filepath}\n\n"
            "You can paste another Collectr URL above to run again.",
        )

    def _on_run_error(self, message: str):
        self._phase = "idle"
        self.is_running = False
        self.run_btn.configure(state="normal", text="Run")
        self.url_entry.configure(state="normal")
        self.status_label.configure(text_color=COLOR_ERROR)
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
    ctk.set_appearance_mode("system")
    ctk.set_default_color_theme("blue")
    root = ctk.CTk()
    CardPricingApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
