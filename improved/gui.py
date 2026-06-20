#!/usr/bin/env python3
"""
gui.py -- Tkinter GUI pro syntezátor cvičení (vrstva nad fasádou gui_backend).

Vlevo ovládání, vpravo NÁHLED progrese: pro každý akord (řádek) dvě stackované
klaviatury — vlevo BAS/AKORD (levá ruka), vpravo MELODIE (pravá ruka). Tóny jsou
zvýrazněné očíslovanými body v POŘADÍ stisku (1,2,3…); opakovaný tón má víc
koleček. Mezi sousedními akordy vedou čáry přesunu hlasů (min. pohyb). Kreslení
je DRY — stejná funkce pro bas i melodii. Layout je fixní (žádné přeskakování).

Spuštění:  python improved/gui.py
"""
import os, sys, threading, tempfile, traceback
HERE = os.path.dirname(__file__)
sys.path.insert(0, HERE)

import tkinter as tk
from tkinter import ttk, filedialog, messagebox

import gui_backend as be

BLACK_PC = {1, 3, 6, 8, 10}
WW, WH, BW, BH = 18, 55, 12, 35      # rozměry kláves (+30 %)
DOTR = 8                             # poloměr kolečka
GAP = 32                             # mezera mezi řádky (čáry voice-leadingu)
ROW_H = 16 + WH + GAP
COL_GAP = 30                         # mezera mezi bas a melodie klaviaturou
BASS_LO, BASS_HI = 36, 64            # C2..E4  (bas + voicing)
MEL_LO, MEL_HI = 55, 88             # G3..E6  (melodická linka)
DOT_BASS = "#1f7ae0"                 # modrá kolečka = levá ruka
DOT_MEL = "#e23030"                  # červená kolečka = melodie
VL_LINE = "#1f7ae0"                  # čára přesunu hlasu voicingu
BASS_LINE = "#bbbbbb"               # čára pohybu basu


def whites(lo, midi):
    """Počet bílých kláves v [lo, midi)."""
    return sum(1 for m in range(lo, midi) if m % 12 not in BLACK_PC)


class App:
    def __init__(self, root):
        root.title("Jazz cvičení — syntezátor")
        root.resizable(False, False)
        try:
            ttk.Style().theme_use("vista")
        except Exception:
            pass
        self.root = root
        self.stop_event = threading.Event()
        self.worker = None
        self.preview = os.path.join(tempfile.gettempdir(), "jazz_gui_preview.mid")
        self._build()
        self.draw_progression()

    # ---------- UI skeleton ----------
    def _build(self):
        outer = ttk.Frame(self.root, padding=10)
        outer.grid(sticky="nsew")
        left = ttk.Frame(outer); left.grid(row=0, column=0, sticky="n")
        ttk.Separator(outer, orient="vertical").grid(row=0, column=1, sticky="ns", padx=10)
        right = ttk.LabelFrame(outer, text="Náhled — pořadí stisku (bas/akord · melodie)", padding=6)
        right.grid(row=0, column=2, sticky="n")
        self._build_left(left)
        self._build_right(right)

    def _build_left(self, frm):
        pad = {"padx": 5, "pady": 3}
        r = 0
        ttk.Label(frm, text="MIDI rozhraní:").grid(row=r, column=0, sticky="w", **pad)
        self.port = tk.StringVar(value=be.default_port())
        ports = be.list_ports() or [""]
        self.port_menu = ttk.OptionMenu(frm, self.port, self.port.get(), *ports)
        self.port_menu.grid(row=r, column=1, columnspan=2, sticky="we", **pad)
        ttk.Button(frm, text="⟳", width=3, command=self.on_refresh_ports).grid(
            row=r, column=3, sticky="w", **pad); r += 1

        ttk.Label(frm, text="Akordy:").grid(row=r, column=0, sticky="w", **pad)
        self.chords = tk.StringVar(value=be.DEFAULT_CHORDS)
        ttk.Entry(frm, textvariable=self.chords, width=46).grid(
            row=r, column=1, columnspan=2, sticky="we", **pad)
        ttk.Button(frm, text="Zobraz ▸", command=self.draw_progression).grid(
            row=r, column=3, sticky="we", **pad); r += 1

        ttk.Label(frm, text="Sestav z akordu:").grid(row=r, column=0, sticky="w", **pad)
        self.root_note = tk.StringVar(value="D"); self.start_q = tk.StringVar(value="m7")
        self.pattern = tk.StringVar(value="ii–V–I (dur)")
        bld = ttk.Frame(frm); bld.grid(row=r, column=1, columnspan=3, sticky="we", **pad)
        ttk.OptionMenu(bld, self.root_note, self.root_note.get(), *be.OPTIONS["roots"]).pack(side="left")
        ttk.OptionMenu(bld, self.start_q, self.start_q.get(), *be.OPTIONS["start_qualities"]).pack(side="left", padx=(4, 8))
        ttk.OptionMenu(bld, self.pattern, self.pattern.get(), *be.OPTIONS["patterns"]).pack(side="left")
        ttk.Button(bld, text="Sestav", command=self.on_build_prog).pack(side="left", padx=8); r += 1

        ttk.Label(frm, text="Váhy patternů:").grid(row=r, column=0, sticky="w", **pad); r += 1
        self.cellvars = {}
        defaults = {"run": 0.45, "markov": 0.55, "scale": 0.0, "arpeggio": 0.0}
        labels = {"run": "běh (Peterson)", "markov": "markov (učené/prolnuté)",
                  "scale": "stupnice (dril)", "arpeggio": "arpeggio (triplets-in-4)"}
        for c in be.OPTIONS["cells"]:
            v = tk.DoubleVar(value=defaults.get(c, 0.0)); self.cellvars[c] = v
            ttk.Label(frm, text=labels[c], width=22).grid(row=r, column=0, sticky="w", **pad)
            ttk.Scale(frm, from_=0.0, to=1.0, variable=v, orient="horizontal", length=200).grid(
                row=r, column=1, columnspan=2, sticky="we", **pad)
            ttk.Label(frm, textvariable=_v(v), width=4).grid(row=r, column=3, sticky="w", **pad); r += 1

        ttk.Label(frm, text="Prolnutí (1=Evans·0=part.):", width=22).grid(row=r, column=0, sticky="w", **pad)
        self.alpha = tk.DoubleVar(value=0.5)
        ttk.Scale(frm, from_=0.0, to=1.0, variable=self.alpha, orient="horizontal", length=200).grid(
            row=r, column=1, columnspan=2, sticky="we", **pad)
        ttk.Label(frm, textvariable=_v(self.alpha), width=4).grid(row=r, column=3, sticky="w", **pad); r += 1
        self.partner = tk.StringVar(value="peterson")
        self._drop(frm, r, "Partner (učený):", self.partner, be.OPTIONS["partners"], pad); r += 1

        self.voicing = tk.StringVar(value="basic"); self.count = tk.StringVar(value="vše")
        self.scale = tk.StringVar(value="bebop"); self.rhythm = tk.StringVar(value="trioly (12/takt)")
        self.in_four = tk.BooleanVar(value=True)
        for var in (self.voicing, self.count, self.rhythm):
            var.trace_add("write", lambda *_: self.draw_progression())
        self._drop(frm, r, "Tvar akordu:", self.voicing, be.OPTIONS["voicings"], pad)
        ttk.Label(frm, text="Akordů:").grid(row=r, column=2, sticky="e", **pad)
        ttk.OptionMenu(frm, self.count, self.count.get(), *be.OPTIONS["counts"]).grid(
            row=r, column=3, sticky="we", **pad); r += 1
        self._drop(frm, r, "Stupnice:", self.scale, be.OPTIONS["scales"], pad); r += 1
        self._drop(frm, r, "Rytmus:", self.rhythm, be.OPTIONS["rhythms"], pad)
        ttk.Checkbutton(frm, text="triplets in four (3:4)", variable=self.in_four).grid(
            row=r, column=2, columnspan=2, sticky="w", **pad); r += 1

        ttk.Label(frm, text="Tempo (BPM):").grid(row=r, column=0, sticky="w", **pad)
        self.bpm = tk.IntVar(value=108)
        ttk.Spinbox(frm, from_=40, to=300, textvariable=self.bpm, width=6).grid(row=r, column=1, sticky="w", **pad)
        ttk.Label(frm, text="Seed:").grid(row=r, column=2, sticky="e", **pad)
        self.seed = tk.IntVar(value=1)
        ttk.Spinbox(frm, from_=0, to=9999, textvariable=self.seed, width=6).grid(row=r, column=3, sticky="w", **pad); r += 1

        btns = ttk.Frame(frm); btns.grid(row=r, column=0, columnspan=4, sticky="we", pady=8)
        ttk.Button(btns, text="▶ Generuj a přehraj", command=self.on_play).pack(side="left", padx=3)
        ttk.Button(btns, text="■ Stop", command=self.on_stop).pack(side="left", padx=3)
        ttk.Button(btns, text="💾 Export…", command=self.on_export).pack(side="left", padx=3)
        ttk.Button(btns, text="🎲 Seed", command=self.on_reseed).pack(side="left", padx=3); r += 1

        self.status = tk.StringVar(value="Připraveno.")
        ttk.Label(frm, textvariable=self.status, foreground="#246", width=52, anchor="w").grid(
            row=r, column=0, columnspan=4, sticky="w", **pad)

    def _build_right(self, frm):
        self.bass_w = whites(BASS_LO, BASS_HI + 1) * WW
        self.mel_x0 = self.bass_w + COL_GAP
        total_w = self.mel_x0 + whites(MEL_LO, MEL_HI + 1) * WW
        nrows = max(4, len(be.DEFAULT_CHORDS.split()))
        self.kbd = tk.Canvas(frm, width=total_w + 6, height=min(8, nrows) * ROW_H + 10,
                             bg="#fafafa", highlightthickness=0)
        sb = ttk.Scrollbar(frm, orient="vertical", command=self.kbd.yview)
        self.kbd.configure(yscrollcommand=sb.set)
        self.kbd.grid(row=0, column=0, sticky="n")
        sb.grid(row=0, column=1, sticky="ns")
        ttk.Label(frm, foreground="#666",
                  text="● levá ruka (bas/akord)   ● melodie   čísla = pořadí stisku   — přesun hlasu"
                  ).grid(row=1, column=0, columnspan=2, sticky="w", pady=(4, 0))

    def _drop(self, frm, row, label, var, values, pad):
        ttk.Label(frm, text=label, width=22).grid(row=row, column=0, sticky="w", **pad)
        ttk.OptionMenu(frm, var, var.get(), *values).grid(row=row, column=1, sticky="we", **pad)

    # ---------- DRY kreslení klaviatury ----------
    def _keyboard(self, cv, x0, ky, lo, hi):
        for m in range(lo, hi + 1):                       # bílé
            if m % 12 in BLACK_PC:
                continue
            x = x0 + whites(lo, m) * WW
            cv.create_rectangle(x, ky, x + WW, ky + WH, fill="white", outline="#999")
            if m % 12 == 0:
                cv.create_text(x + WW / 2, ky + WH - 2, anchor="s",
                               text=f"C{m // 12 - 1}", font=("Segoe UI", 6), fill="#bbb")
        for m in range(lo, hi + 1):                       # černé
            if m % 12 not in BLACK_PC:
                continue
            x = x0 + whites(lo, m) * WW - BW / 2
            cv.create_rectangle(x, ky, x + BW, ky + BH, fill="#222", outline="#000")

    def _cx(self, x0, lo, hi, m):
        m = max(lo, min(hi, m))
        if m % 12 in BLACK_PC:
            return x0 + whites(lo, m) * WW
        return x0 + whites(lo, m) * WW + WW / 2

    def _seq(self, cv, x0, ky, lo, hi, seq, color):
        """DRY: posloupnost tónů jako očíslovaná kolečka v pořadí hraní.
        Drží výškovou dráhu po dobu jednoho směrového běhu; při OPAKOVÁNÍ tónu
        nebo ZMĚNĚ SMĚRU poskočí další kolečko o patro výš (po MAXL patrech se
        přetočí dolů, ať to nepřeteče)."""
        STEP, MAXL = 13, 3
        level, prevdir = 0, 0
        for i, p in enumerate(seq):
            if i > 0:
                prev = seq[i - 1]
                d = (p > prev) - (p < prev)
                if p == prev or (d != 0 and prevdir != 0 and d != prevdir):
                    level = level + 1 if level < MAXL else 0
                if d != 0:
                    prevdir = d
            cx = self._cx(x0, lo, hi, p)
            base = ky + (BH - 8 if p % 12 in BLACK_PC else WH - 11)
            cy = base - level * STEP
            cv.create_oval(cx - DOTR, cy - DOTR, cx + DOTR, cy + DOTR, fill=color, outline="#333")
            cv.create_text(cx, cy, text=str(i + 1), fill="white", font=("Segoe UI", 8, "bold"))

    # ---------- náhled progrese ----------
    def draw_progression(self):
        cv = getattr(self, "kbd", None)
        if cv is None:
            return
        cv.delete("all")
        try:
            rows = be.preview_sequences(self.params())
        except Exception as e:
            cv.create_text(8, 8, anchor="nw", text=f"(nelze zobrazit: {e})", fill="#a00")
            cv.config(scrollregion=(0, 0, 10, 10)); return
        for i, row in enumerate(rows):
            y0 = 8 + i * ROW_H; ky = y0 + 14
            cv.create_text(2, y0, anchor="nw", text=row["label"], font=("Segoe UI", 9, "bold"), fill="#234")
            self._keyboard(cv, 0, ky, BASS_LO, BASS_HI)
            self._keyboard(cv, self.mel_x0, ky, MEL_LO, MEL_HI)
        # čáry přesunu hlasů (bas/akord) mezi sousedními řádky
        for i in range(len(rows) - 1):
            yb = 8 + i * ROW_H + 14 + WH
            yt = 8 + (i + 1) * ROW_H + 14
            for ma, mb in zip(rows[i]["voicing"], rows[i + 1]["voicing"]):
                cv.create_line(self._cx(0, BASS_LO, BASS_HI, ma), yb,
                               self._cx(0, BASS_LO, BASS_HI, mb), yt, fill=VL_LINE, width=2)
            cv.create_line(self._cx(0, BASS_LO, BASS_HI, rows[i]["bass"]), yb,
                           self._cx(0, BASS_LO, BASS_HI, rows[i + 1]["bass"]), yt,
                           fill=BASS_LINE, width=1, dash=(3, 2))
        # očíslované body navrch (DRY: bas i melodie)
        for i, row in enumerate(rows):
            ky = 8 + i * ROW_H + 14
            self._seq(cv, 0, ky, BASS_LO, BASS_HI, [row["bass"]] + row["voicing"], DOT_BASS)
            self._seq(cv, self.mel_x0, ky, MEL_LO, MEL_HI, row["mel"], DOT_MEL)
        total_w = self.mel_x0 + whites(MEL_LO, MEL_HI + 1) * WW
        cv.config(scrollregion=(0, 0, total_w + 6, 8 + len(rows) * ROW_H + 6))

    # ---------- params ----------
    def params(self):
        return {
            "chords": self.chords.get(),
            "cells": {c: v.get() for c, v in self.cellvars.items()},
            "alpha": self.alpha.get(), "partner": self.partner.get(),
            "count": self.count.get(), "voicing": self.voicing.get(),
            "scale": self.scale.get(), "rhythm": self.rhythm.get(),
            "in_four": self.in_four.get(), "bpm": self.bpm.get(), "seed": self.seed.get(),
        }

    # ---------- akce ----------
    def on_build_prog(self):
        s = be.build_chords(self.root_note.get(), self.start_q.get(), self.pattern.get())
        self.chords.set(s); self.draw_progression(); self.status.set(f"Sestaveno: {s}")

    def on_refresh_ports(self):
        ports = be.list_ports() or [""]
        menu = self.port_menu["menu"]; menu.delete(0, "end")
        for p in ports:
            menu.add_command(label=p, command=lambda v=p: self.port.set(v))
        if self.port.get() not in ports:
            self.port.set(be.default_port() or (ports[0] if ports else ""))
        self.status.set(f"Porty obnoveny ({len(ports)}).")

    def on_reseed(self):
        self.seed.set((self.seed.get() + 1) % 10000)
        self.draw_progression(); self.status.set(f"Seed = {self.seed.get()}")

    def on_stop(self):
        self.stop_event.set(); self.status.set("Stop.")

    def on_play(self):
        if self.worker and self.worker.is_alive():
            self.status.set("Už hraji — nejdřív Stop."); return
        self.draw_progression()
        self.stop_event.clear()
        self.worker = threading.Thread(target=self._gen_and_play, daemon=True)
        self.worker.start()

    def _gen_and_play(self):
        try:
            self.status.set("Generuji…")
            _, used = be.generate(self.params(), self.preview)
            self.status.set("Hraji…  " + " ".join(used))
            be.play(self.preview, port_name=self.port.get(), stop_event=self.stop_event)
            if not self.stop_event.is_set():
                self.status.set("Hotovo.  takty: " + " ".join(used))
        except Exception as e:
            traceback.print_exc(); self.status.set(f"Chyba: {e}")

    def on_export(self):
        path = filedialog.asksaveasfilename(
            title="Uložit cvičení jako MIDI", defaultextension=".mid",
            filetypes=[("MIDI", "*.mid")], initialfile="cviceni.mid")
        if not path:
            return
        try:
            be.generate(self.params(), path)
            self.status.set(f"Uloženo: {path}")
            messagebox.showinfo("Export", f"Uloženo:\n{path}")
        except Exception as e:
            traceback.print_exc(); messagebox.showerror("Chyba exportu", str(e))


def _v(var):
    s = tk.StringVar(value=f"{var.get():.2f}")
    var.trace_add("write", lambda *_: s.set(f"{var.get():.2f}"))
    return s


def main():
    root = tk.Tk()
    App(root)
    root.mainloop()


if __name__ == "__main__":
    main()
