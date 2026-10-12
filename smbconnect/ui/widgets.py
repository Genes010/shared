"""Herbruikbare widgets: log-paneel, scrollbaar frame, statusbolletje."""

from __future__ import annotations

import datetime as dt
import tkinter as tk
from tkinter import filedialog, ttk

from . import theme


class StatusDot(tk.Canvas):
    def __init__(self, master, status: str = "pending", size: int = 14, bg: str = theme.SURFACE):
        super().__init__(master, width=size, height=size, bg=bg, highlightthickness=0, bd=0)
        self._size = size
        self._oval = self.create_oval(2, 2, size - 2, size - 2, outline="", fill=theme.GREY)
        self.set(status)

    def set(self, status: str) -> None:
        color = theme.STATUS_COLORS.get(status, theme.GREY)
        if status == "pending":
            self.itemconfigure(self._oval, fill="", outline=theme.GREY, width=2)
        else:
            self.itemconfigure(self._oval, fill=color, outline="", width=0)


class ScrollFrame(ttk.Frame):
    """Verticaal scrollbaar frame; plaats inhoud in ``self.inner``."""

    def __init__(self, master, bg: str = theme.BG, **kw):
        super().__init__(master, **kw)
        self.canvas = tk.Canvas(self, bg=bg, highlightthickness=0, bd=0)
        self.vsb = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.inner = ttk.Frame(self.canvas)
        self._win = self.canvas.create_window((0, 0), window=self.inner, anchor="nw")
        self.canvas.configure(yscrollcommand=self.vsb.set)
        self.canvas.pack(side="left", fill="both", expand=True)
        self.vsb.pack(side="right", fill="y")
        self.inner.bind("<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.bind("<Configure>", lambda e: self.canvas.itemconfigure(self._win, width=e.width))
        self.canvas.bind("<Enter>", lambda e: self.canvas.bind_all("<MouseWheel>", self._wheel))
        self.canvas.bind("<Leave>", lambda e: self.canvas.unbind_all("<MouseWheel>"))

    def _wheel(self, event):
        self.canvas.yview_scroll(int(-event.delta / 120), "units")

    def scroll_top(self):
        self.canvas.yview_moveto(0)


class LogPanel(ttk.Frame):
    """Log met alle uitgevoerde commando's en uitvoer."""

    def __init__(self, master):
        super().__init__(master)
        head = ttk.Frame(self)
        head.pack(fill="x", pady=(0, 4))
        ttk.Label(head, text="Log", style="H2.TLabel").pack(side="left")
        ttk.Label(head, text="alle uitgevoerde commando's en uitvoer", style="Muted.TLabel").pack(
            side="left", padx=8)
        ttk.Button(head, text="Opslaan…", command=self.save).pack(side="right")
        ttk.Button(head, text="Kopiëren", command=self.copy).pack(side="right", padx=4)
        ttk.Button(head, text="Wissen", command=self.clear).pack(side="right")

        body = ttk.Frame(self)
        body.pack(fill="both", expand=True)
        mono = getattr(self.winfo_toplevel(), "_mono_font", ("Consolas", 9))
        self.text = tk.Text(body, height=8, bg="#14161a", fg=theme.FG, insertbackground=theme.FG,
                            relief="flat", bd=0, wrap="word", font=mono, padx=8, pady=6,
                            highlightthickness=1, highlightbackground=theme.BORDER,
                            highlightcolor=theme.BORDER)
        vsb = ttk.Scrollbar(body, orient="vertical", command=self.text.yview)
        self.text.configure(yscrollcommand=vsb.set, state="disabled")
        self.text.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")
        self.text.tag_configure("time", foreground=theme.GREY)
        self.text.tag_configure("cmd", foreground="#8ab4ff")
        self.text.tag_configure("out", foreground="#c9cdd3")
        self.text.tag_configure("err", foreground="#ff9b94")
        self.text.tag_configure("info", foreground=theme.ORANGE)

    def append(self, kind: str, text: str) -> None:
        stamp = dt.datetime.now().strftime("%H:%M:%S")
        prefix = {"cmd": "$ ", "err": "! ", "info": "# "}.get(kind, "  ")
        lines = text.rstrip("\n").splitlines() or [""]
        self.text.configure(state="normal")
        for i, line in enumerate(lines):
            self.text.insert("end", f"{stamp} " if i == 0 else "         ", "time")
            self.text.insert("end", (prefix if i == 0 else "  ") + line + "\n", kind)
        # Log niet oneindig laten groeien.
        if int(self.text.index("end-1c").split(".")[0]) > 5000:
            self.text.delete("1.0", "1000.0")
        self.text.configure(state="disabled")
        self.text.see("end")

    def clear(self) -> None:
        self.text.configure(state="normal")
        self.text.delete("1.0", "end")
        self.text.configure(state="disabled")

    def copy(self) -> None:
        self.clipboard_clear()
        self.clipboard_append(self.text.get("1.0", "end-1c"))

    def save(self) -> None:
        path = filedialog.asksaveasfilename(
            parent=self, defaultextension=".txt", filetypes=[("Tekst", "*.txt")],
            initialfile=f"smbconnect-log-{dt.datetime.now():%Y%m%d-%H%M%S}.txt")
        if path:
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(self.text.get("1.0", "end-1c"))


def labeled_entry(master, label: str, var: tk.StringVar, row: int, show: str | None = None,
                  width: int = 28, hint: str = "") -> ttk.Entry:
    ttk.Label(master, text=label).grid(row=row, column=0, sticky="w", padx=(0, 10), pady=4)
    entry = ttk.Entry(master, textvariable=var, width=width, show=show or "")
    entry.grid(row=row, column=1, sticky="we", pady=4)
    if hint:
        ttk.Label(master, text=hint, style="Muted.TLabel").grid(row=row, column=2, sticky="w", padx=10)
    return entry
