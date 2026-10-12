"""Hoofdvenster: tabs + log-venster onderin."""

from __future__ import annotations

import queue
import threading
import tkinter as tk
import traceback
from tkinter import messagebox, ttk
from typing import Any, Callable

from .. import __version__
from ..config import load_config, save_config
from ..elevate import is_admin
from ..runner import IS_WINDOWS, Runner
from . import theme
from .diagnose_tab import DiagnoseTab
from .widgets import LogPanel


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("SMB Connect")
        self.geometry("1100x800")
        self.minsize(900, 600)
        theme.apply_theme(self)

        self._queue: "queue.Queue[tuple[Callable, tuple]]" = queue.Queue()
        self.runner = Runner(log=lambda kind, text: self.call_ui(self._log, kind, text))
        self.cfg = load_config()

        self._build()
        self.after(50, self._drain)
        self._log("info", f"SMB Connect {__version__} gestart"
                          + (" (als administrator)" if is_admin() else "")
                          + ("" if IS_WINDOWS else " — LET OP: niet op Windows, commando's worden niet uitgevoerd"))

    # ------------------------------------------------------------------ UI
    def _build(self) -> None:
        header = ttk.Frame(self, padding=(16, 12, 16, 0))
        header.pack(fill="x")
        ttk.Label(header, text="SMB Connect", style="Title.TLabel").pack(side="left")
        ttk.Label(header, text="Gedeelde mappen tussen Windows 11-pc's, met één klik.",
                  style="Muted.TLabel").pack(side="left", padx=12, pady=(4, 0))

        paned = ttk.PanedWindow(self, orient="vertical")
        paned.pack(fill="both", expand=True, padx=12, pady=12)

        self.notebook = ttk.Notebook(paned)
        self.tab_client = self._placeholder("Koppelen", "Tab 1 (Koppelen) volgt in de volgende stap.")
        self.tab_diag = DiagnoseTab(self.notebook, self)
        self.tab_server = self._placeholder("Deze machine als server",
                                            "Tab 3 (Deze machine als server) volgt in een volgende stap.")
        self.notebook.add(self.tab_client, text="  Koppelen  ")
        self.notebook.add(self.tab_diag, text="  Diagnose  ")
        self.notebook.add(self.tab_server, text="  Deze machine als server  ")
        self.notebook.select(self.tab_diag)

        self.log_panel = LogPanel(paned)
        paned.add(self.notebook, weight=4)
        paned.add(self.log_panel, weight=1)

    def _placeholder(self, title: str, text: str) -> ttk.Frame:
        f = ttk.Frame(self.notebook, padding=16)
        ttk.Label(f, text=title, style="Title.TLabel").pack(anchor="w")
        ttk.Label(f, text=text, style="Muted.TLabel").pack(anchor="w", pady=8)
        return f

    def _log(self, kind: str, text: str) -> None:
        self.log_panel.append(kind, text)

    # ------------------------------------------------------------ threads
    def call_ui(self, fn: Callable, *args: Any) -> None:
        """Thread-safe: laat ``fn(*args)`` uitvoeren in de UI-thread."""
        self._queue.put((fn, args))

    def _drain(self) -> None:
        try:
            while True:
                fn, args = self._queue.get_nowait()
                try:
                    fn(*args)
                except Exception:
                    self.log_panel.append("err", traceback.format_exc())
        except queue.Empty:
            pass
        self.after(50, self._drain)

    def run_task(self, fn: Callable[[], Any], on_done: Callable[..., None] | None = None) -> None:
        """Voer ``fn`` uit in een achtergrondthread; ``on_done(result, error=None)`` in de UI-thread."""
        def worker():
            try:
                result = fn()
            except Exception as exc:
                self.call_ui(self._log, "err", traceback.format_exc())
                if on_done:
                    self.call_ui(lambda: on_done(None, error=str(exc)))
                return
            if on_done:
                self.call_ui(on_done, result)

        threading.Thread(target=worker, daemon=True).start()

    # ------------------------------------------------------------ helpers
    def confirm(self, title: str, message: str) -> bool:
        """Elke systeemwijziging eerst laten bevestigen."""
        return messagebox.askyesno(title, message, parent=self, icon="warning")

    def save_config(self) -> None:
        save_config(self.cfg)


def enable_dpi_awareness() -> None:
    if not IS_WINDOWS:
        return
    try:
        import ctypes
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        pass


def main() -> None:
    enable_dpi_awareness()
    app = App()
    app.mainloop()
