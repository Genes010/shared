"""Donker, strak ttk-thema."""

from __future__ import annotations

import tkinter as tk
from tkinter import font as tkfont
from tkinter import ttk

from ..runner import IS_WINDOWS

BG = "#1b1d21"        # venster
SURFACE = "#24272d"   # kaarten / panelen
SURFACE_2 = "#2d3139" # invoervelden, hover
BORDER = "#3a3f48"
FG = "#e7e9ec"
MUTED = "#9aa1ab"
ACCENT = "#4c8dff"
ACCENT_HOVER = "#6aa1ff"
GREEN = "#3fb950"
ORANGE = "#e3a008"
RED = "#f85149"
GREY = "#6b7280"

STATUS_COLORS = {"ok": GREEN, "warn": ORANGE, "fail": RED, "info": ACCENT, "skip": GREY, "pending": GREY}

UI_FONT = "Segoe UI" if IS_WINDOWS else "DejaVu Sans"
MONO_FONT = "Cascadia Mono" if IS_WINDOWS else "DejaVu Sans Mono"


def apply_theme(root: tk.Tk) -> None:
    root.configure(bg=BG)
    for name in ("TkDefaultFont", "TkTextFont", "TkMenuFont", "TkHeadingFont"):
        try:
            tkfont.nametofont(name).configure(family=UI_FONT, size=10)
        except tk.TclError:
            pass
    families = set(tkfont.families(root))
    mono = MONO_FONT if MONO_FONT in families else ("Consolas" if "Consolas" in families else "Courier New")
    root._mono_font = (mono, 9)  # type: ignore[attr-defined]

    # Kleuren voor tk-widgets (Listbox, Text, combobox-dropdown).
    root.option_add("*TCombobox*Listbox.background", SURFACE_2)
    root.option_add("*TCombobox*Listbox.foreground", FG)
    root.option_add("*TCombobox*Listbox.selectBackground", ACCENT)
    root.option_add("*TCombobox*Listbox.selectForeground", "#ffffff")

    s = ttk.Style(root)
    s.theme_use("clam")
    s.configure(".", background=BG, foreground=FG, fieldbackground=SURFACE_2, bordercolor=BORDER,
                lightcolor=BORDER, darkcolor=BORDER, troughcolor=SURFACE, focuscolor=ACCENT,
                selectbackground=ACCENT, selectforeground="#ffffff", insertcolor=FG, font=(UI_FONT, 10))
    s.configure("TFrame", background=BG)
    s.configure("Card.TFrame", background=SURFACE)
    s.configure("TLabel", background=BG, foreground=FG)
    s.configure("Card.TLabel", background=SURFACE)
    s.configure("Muted.TLabel", foreground=MUTED)
    s.configure("CardMuted.TLabel", background=SURFACE, foreground=MUTED)
    s.configure("Title.TLabel", font=(UI_FONT, 15, "bold"))
    s.configure("H2.TLabel", font=(UI_FONT, 11, "bold"))
    s.configure("CardH2.TLabel", background=SURFACE, font=(UI_FONT, 10, "bold"))

    s.configure("TButton", background=SURFACE_2, foreground=FG, borderwidth=1, padding=(12, 6),
                relief="flat")
    s.map("TButton", background=[("disabled", SURFACE), ("pressed", BORDER), ("active", BORDER)],
          foreground=[("disabled", GREY)])
    s.configure("Accent.TButton", background=ACCENT, foreground="#ffffff", bordercolor=ACCENT)
    s.map("Accent.TButton", background=[("disabled", SURFACE_2), ("pressed", ACCENT), ("active", ACCENT_HOVER)],
          foreground=[("disabled", GREY)])
    s.configure("Danger.TButton", background="#4a1f22", foreground="#ffd7d5", bordercolor="#6b2b2f")
    s.map("Danger.TButton", background=[("active", "#5c2529")])
    s.configure("Link.TButton", background=BG, foreground=ACCENT, borderwidth=0, padding=(2, 2))
    s.map("Link.TButton", background=[("active", BG)], foreground=[("active", ACCENT_HOVER)])

    s.configure("TEntry", fieldbackground=SURFACE_2, foreground=FG, insertcolor=FG, padding=5)
    s.map("TEntry", bordercolor=[("focus", ACCENT)], lightcolor=[("focus", ACCENT)])
    s.configure("TCombobox", fieldbackground=SURFACE_2, background=SURFACE_2, foreground=FG,
                arrowcolor=FG, padding=4)
    s.map("TCombobox", fieldbackground=[("readonly", SURFACE_2)], foreground=[("readonly", FG)],
          bordercolor=[("focus", ACCENT)])
    s.configure("TCheckbutton", background=BG, foreground=FG, indicatorbackground=SURFACE_2,
                indicatorforeground=FG)
    s.map("TCheckbutton", background=[("active", BG)], indicatorbackground=[("selected", ACCENT)])

    s.configure("TNotebook", background=BG, borderwidth=0, tabmargins=(0, 4, 0, 0),
                lightcolor=SURFACE, darkcolor=SURFACE, bordercolor=SURFACE)
    s.configure("TNotebook.Tab", background=BG, foreground=MUTED, padding=(16, 8), borderwidth=0,
                lightcolor=BG, bordercolor=BG)
    s.map("TNotebook.Tab", background=[("selected", SURFACE)], foreground=[("selected", FG), ("active", FG)])

    s.configure("Treeview", background=SURFACE, fieldbackground=SURFACE, foreground=FG, rowheight=26,
                borderwidth=0)
    s.map("Treeview", background=[("selected", "#2f4a7a")], foreground=[("selected", "#ffffff")])
    s.configure("Treeview.Heading", background=SURFACE_2, foreground=MUTED, relief="flat", padding=(6, 4))
    s.map("Treeview.Heading", background=[("active", BORDER)])

    s.configure("Vertical.TScrollbar", background=SURFACE_2, troughcolor=BG, arrowcolor=MUTED,
                bordercolor=BG, relief="flat")
    s.configure("TPanedwindow", background=BG)
    s.configure("Sash", sashthickness=6, gripcount=0, background=BG)
    s.configure("TSeparator", background=BORDER)
