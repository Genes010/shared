"""Tab 2: Diagnose per server."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from .. import diagnose as dg
from . import theme
from .widgets import ScrollFrame, StatusDot

MANUAL = "— handmatig invoeren —"


class StepRow:
    def __init__(self, master, key: str, title: str):
        self.key = key
        self.frame = ttk.Frame(master, style="Card.TFrame", padding=(14, 10))
        self.frame.columnconfigure(1, weight=1)
        self.dot = StatusDot(self.frame, "pending")
        self.dot.grid(row=0, column=0, sticky="n", pady=(4, 0), padx=(0, 10))
        head = ttk.Frame(self.frame, style="Card.TFrame")
        head.grid(row=0, column=1, sticky="we")
        ttk.Label(head, text=title, style="CardH2.TLabel").pack(side="left")
        self.badge = ttk.Label(head, text="", style="CardMuted.TLabel")
        self.badge.pack(side="right")
        self.summary = ttk.Label(self.frame, text="Nog niet getest.", style="Card.TLabel", justify="left")
        self.summary.grid(row=1, column=1, sticky="we", pady=(2, 0))
        self.detail = ttk.Label(self.frame, text="", style="CardMuted.TLabel", justify="left")
        self.fix = tk.Label(self.frame, text="", bg=theme.SURFACE, fg=theme.FG, justify="left", anchor="w",
                            font=(theme.UI_FONT, 10))
        self.fix_title = tk.Label(self.frame, text="Voorgestelde oplossing", bg=theme.SURFACE,
                                  fg=theme.ORANGE, anchor="w", font=(theme.UI_FONT, 9, "bold"))

    def set_wrap(self, width: int) -> None:
        for w in (self.summary, self.detail, self.fix):
            w.configure(wraplength=max(200, width))

    def reset(self) -> None:
        self.dot.set("pending")
        self.badge.configure(text="")
        self.summary.configure(text="Wachten…")
        for w in (self.detail, self.fix, self.fix_title):
            w.grid_remove()

    def busy(self) -> None:
        self.badge.configure(text="bezig…")
        self.summary.configure(text="Bezig met testen…")

    def show(self, r: dg.CheckResult) -> None:
        labels = {"ok": "in orde", "warn": "let op", "fail": "probleem", "info": "info", "skip": "overgeslagen"}
        self.dot.set(r.status)
        self.badge.configure(text=labels.get(r.status, ""))
        self.summary.configure(text=r.summary)
        if r.detail:
            self.detail.configure(text=r.detail)
            self.detail.grid(row=2, column=1, sticky="we", pady=(4, 0))
        else:
            self.detail.grid_remove()
        if r.fix:
            color = theme.RED if r.status == "fail" else theme.ORANGE
            self.fix_title.configure(fg=color)
            self.fix.configure(text=r.fix)
            self.fix_title.grid(row=3, column=1, sticky="we", pady=(8, 0))
            self.fix.grid(row=4, column=1, sticky="we")
        else:
            self.fix_title.grid_remove()
            self.fix.grid_remove()


class DiagnoseTab(ttk.Frame):
    def __init__(self, master, app):
        super().__init__(master, padding=16)
        self.app = app
        self.results: list[dg.CheckResult] = []
        self.last_params: dg.DiagnoseParams | None = None

        self.v_profile = tk.StringVar(value=MANUAL)
        self.v_host = tk.StringVar()
        self.v_ip = tk.StringVar()
        self.v_share = tk.StringVar()
        self.v_user = tk.StringVar()
        self.v_pass = tk.StringVar()

        top = ttk.Frame(self)
        top.pack(fill="x")
        ttk.Label(top, text="Diagnose", style="Title.TLabel").pack(anchor="w")
        ttk.Label(top, text="Controleert stap voor stap waarom een gedeelde map wel of niet werkt.",
                  style="Muted.TLabel").pack(anchor="w", pady=(0, 10))

        form = ttk.Frame(self)
        form.pack(fill="x")
        form.columnconfigure(1, weight=1)
        form.columnconfigure(4, weight=1)

        ttk.Label(form, text="Profiel").grid(row=0, column=0, sticky="w", pady=4, padx=(0, 10))
        self.cb_profile = ttk.Combobox(form, textvariable=self.v_profile, state="readonly")
        self.cb_profile.grid(row=0, column=1, sticky="we", pady=4)
        self.cb_profile.bind("<<ComboboxSelected>>", self._profile_selected)

        def field(label, var, row, col, show=None, hint=None):
            ttk.Label(form, text=label).grid(row=row, column=col, sticky="w", pady=4,
                                             padx=(0 if col == 0 else 20, 10))
            e = ttk.Entry(form, textvariable=var, show=show or "")
            e.grid(row=row, column=col + 1, sticky="we", pady=4)
            return e

        self.e_host = field("Server (naam of IP)", self.v_host, 1, 0)
        field("Fallback-IP (optioneel)", self.v_ip, 1, 3)
        field("Share", self.v_share, 2, 0)
        field("Gebruikersnaam", self.v_user, 2, 3)
        field("Wachtwoord (optioneel)", self.v_pass, 3, 0, show="•")
        ttk.Label(form, text="Alleen voor deze test, wordt niet opgeslagen. Leeg = opgeslagen inloggegevens.",
                  style="Muted.TLabel").grid(row=3, column=3, columnspan=2, sticky="w", padx=(20, 0))

        bar = ttk.Frame(self)
        bar.pack(fill="x", pady=(10, 10))
        self.btn_run = ttk.Button(bar, text="Diagnose starten", style="Accent.TButton", command=self.start)
        self.btn_run.pack(side="left")
        self.btn_copy = ttk.Button(bar, text="Rapport kopiëren", command=self.copy_report, state="disabled")
        self.btn_copy.pack(side="left", padx=8)
        self.lbl_state = ttk.Label(bar, text="", style="Muted.TLabel")
        self.lbl_state.pack(side="left", padx=8)
        self.e_host.bind("<Return>", lambda e: self.start())

        self.scroll = ScrollFrame(self)
        self.scroll.pack(fill="both", expand=True)
        self.scroll.inner.columnconfigure(0, weight=1)
        self.rows: dict[str, StepRow] = {}
        for i, (key, title) in enumerate(dg.STEPS):
            row = StepRow(self.scroll.inner, key, title)
            row.frame.grid(row=i, column=0, sticky="we", pady=(0, 8), padx=(0, 6))
            self.rows[key] = row
        self.scroll.inner.bind("<Configure>", self._on_resize, add="+")
        self.refresh_profiles()

    # ------------------------------------------------------------------
    def _on_resize(self, event) -> None:
        for row in self.rows.values():
            row.set_wrap(event.width - 80)

    def refresh_profiles(self) -> None:
        names = [MANUAL] + [f"{s.name or s.host}  ({s.host}\\{s.share})" for s in self.app.cfg.servers]
        self.cb_profile.configure(values=names)

    def _profile_selected(self, _event=None) -> None:
        idx = self.cb_profile.current()
        if idx <= 0:
            return
        s = self.app.cfg.servers[idx - 1]
        self.v_host.set(s.host)
        self.v_ip.set(s.ip)
        self.v_share.set(s.share)
        self.v_user.set(s.username)
        self.v_pass.set("")

    def load_profile(self, profile) -> None:
        """Vanuit tab Koppelen: diagnose voor een bepaald profiel."""
        self.refresh_profiles()
        self.v_host.set(profile.host)
        self.v_ip.set(profile.ip)
        self.v_share.set(profile.share)
        self.v_user.set(profile.username)
        self.v_pass.set("")

    # ------------------------------------------------------------------
    def start(self) -> None:
        host = self.v_host.get().strip()
        if not host:
            self.lbl_state.configure(text="Vul eerst een servernaam of IP-adres in.")
            self.e_host.focus_set()
            return
        params = dg.DiagnoseParams(
            host=host, share=self.v_share.get().strip(), username=self.v_user.get().strip(),
            password=self.v_pass.get(), ip_fallback=self.v_ip.get().strip())
        self.last_params = params
        self.results = []
        for row in self.rows.values():
            row.reset()
        self.rows["resolve"].busy()
        self.btn_run.configure(state="disabled")
        self.btn_copy.configure(state="disabled")
        self.lbl_state.configure(text="Diagnose loopt…")
        self.scroll.scroll_top()

        order = [k for k, _ in dg.STEPS]

        def emit(result: dg.CheckResult) -> None:
            self.app.call_ui(self._show_result, result, order)

        self.app.run_task(lambda: dg.run_diagnosis(self.app.runner, params, emit), self._done)

    def _show_result(self, result: dg.CheckResult, order: list[str]) -> None:
        self.results.append(result)
        self.rows[result.key].show(result)
        i = order.index(result.key)
        if i + 1 < len(order) and not any(r.key == order[i + 1] for r in self.results):
            self.rows[order[i + 1]].busy()

    def _done(self, results, error=None) -> None:
        self.btn_run.configure(state="normal")
        self.v_pass.set("")  # wachtwoord niet langer dan nodig bewaren
        if error:
            self.lbl_state.configure(text=f"Diagnose afgebroken: {error}")
            return
        self.btn_copy.configure(state="normal")
        fails = sum(r.status == "fail" for r in results)
        warns = sum(r.status == "warn" for r in results)
        if fails:
            self.lbl_state.configure(text=f"Klaar: {fails} probleem/problemen, {warns} waarschuwing(en).")
        elif warns:
            self.lbl_state.configure(text=f"Klaar: geen fouten, {warns} waarschuwing(en).")
        else:
            self.lbl_state.configure(text="Klaar: alles in orde.")

    def copy_report(self) -> None:
        if not self.last_params:
            return
        self.clipboard_clear()
        self.clipboard_append(dg.format_report(self.last_params, self.results))
        self.lbl_state.configure(text="Rapport gekopieerd naar het klembord.")
