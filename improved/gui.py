#!/usr/bin/env python3
"""
gui.py -- jednoduché Tkinter GUI pro syntezátor cvičení.

Pouze vrstva nad fasádou `gui_backend` (GUI nezná vnitřek enginu). Umožní:
  - naparametrizovat generátor klikáním (váhy buněk, prolnutí, tvar akordu, ...),
  - "Generuj a přehraj" pro poslech,
  - "Export MIDI..." pro uložení.

Spuštění:  python improved/gui.py
"""
import os, sys, threading, tempfile, traceback
HERE = os.path.dirname(__file__)
sys.path.insert(0, HERE)

import tkinter as tk
from tkinter import ttk, filedialog, messagebox

import gui_backend as be


class App:
    def __init__(self, root):
        root.title("Jazz cvičení — syntezátor")
        self.root = root
        self.stop_event = threading.Event()
        self.worker = None
        self.preview = os.path.join(tempfile.gettempdir(), "jazz_gui_preview.mid")
        self._build()

    # ---- UI ----
    def _build(self):
        pad = {"padx": 6, "pady": 3}
        frm = ttk.Frame(self.root, padding=10)
        frm.grid(sticky="nsew")
        r = 0

        ttk.Label(frm, text="Akordy (progrese):").grid(row=r, column=0, sticky="w", **pad)
        self.chords = tk.StringVar(value=be.DEFAULT_CHORDS)
        ttk.Entry(frm, textvariable=self.chords, width=52).grid(
            row=r, column=1, columnspan=3, sticky="we", **pad); r += 1

        # váhy typů buněk (slidery 0..1)
        ttk.Label(frm, text="Váhy patternů:").grid(row=r, column=0, sticky="w", **pad); r += 1
        self.cellvars = {}
        defaults = {"run": 0.45, "markov": 0.55, "scale": 0.0, "arpeggio": 0.0}
        labels = {"run": "běh (Peterson)", "markov": "markov (učené/prolnuté)",
                  "scale": "stupnice (dril)", "arpeggio": "arpeggio (triplets-in-4)"}
        for c in be.OPTIONS["cells"]:
            v = tk.DoubleVar(value=defaults.get(c, 0.0))
            self.cellvars[c] = v
            ttk.Label(frm, text=labels[c]).grid(row=r, column=0, sticky="w", **pad)
            ttk.Scale(frm, from_=0.0, to=1.0, variable=v, orient="horizontal",
                      length=240).grid(row=r, column=1, columnspan=2, sticky="we", **pad)
            ttk.Label(frm, textvariable=v_fmt(v)).grid(row=r, column=3, sticky="w", **pad)
            r += 1

        # prolnutí Evans<->Peterson
        ttk.Label(frm, text="Prolnutí (1=Evans · 0=Peterson):").grid(
            row=r, column=0, sticky="w", **pad)
        self.alpha = tk.DoubleVar(value=0.5)
        ttk.Scale(frm, from_=0.0, to=1.0, variable=self.alpha, orient="horizontal",
                  length=240).grid(row=r, column=1, columnspan=2, sticky="we", **pad)
        ttk.Label(frm, textvariable=v_fmt(self.alpha)).grid(row=r, column=3, sticky="w", **pad)
        r += 1

        # tvar akordu / stupnice / rytmus
        self.voicing = tk.StringVar(value="basic")
        self.scale = tk.StringVar(value="bebop")
        self.rhythm = tk.StringVar(value=be.OPTIONS["rhythms"][0])
        self.in_four = tk.BooleanVar(value=True)
        _drop(frm, r, "Tvar akordu:", self.voicing, be.OPTIONS["voicings"], pad); r += 1
        _drop(frm, r, "Stupnice:", self.scale, be.OPTIONS["scales"], pad); r += 1
        _drop(frm, r, "Rytmus:", self.rhythm, be.OPTIONS["rhythms"], pad)
        ttk.Checkbutton(frm, text="triplets in four (3:4)", variable=self.in_four).grid(
            row=r, column=2, sticky="w", **pad); r += 1

        # bpm / seed
        ttk.Label(frm, text="Tempo (BPM):").grid(row=r, column=0, sticky="w", **pad)
        self.bpm = tk.IntVar(value=108)
        ttk.Spinbox(frm, from_=40, to=300, textvariable=self.bpm, width=6).grid(
            row=r, column=1, sticky="w", **pad)
        ttk.Label(frm, text="Seed:").grid(row=r, column=2, sticky="e", **pad)
        self.seed = tk.IntVar(value=1)
        ttk.Spinbox(frm, from_=0, to=9999, textvariable=self.seed, width=6).grid(
            row=r, column=3, sticky="w", **pad); r += 1

        # port
        _drop(frm, r, "MIDI výstup:", None, [], pad)
        self.port = tk.StringVar(value=be.default_port())
        ports = be.list_ports() or [""]
        ttk.OptionMenu(frm, self.port, self.port.get(), *ports).grid(
            row=r, column=1, columnspan=3, sticky="we", **pad); r += 1

        # tlačítka
        btns = ttk.Frame(frm); btns.grid(row=r, column=0, columnspan=4, sticky="we", pady=8)
        ttk.Button(btns, text="▶ Generuj a přehraj", command=self.on_play).pack(side="left", padx=4)
        ttk.Button(btns, text="■ Stop", command=self.on_stop).pack(side="left", padx=4)
        ttk.Button(btns, text="💾 Export MIDI…", command=self.on_export).pack(side="left", padx=4)
        ttk.Button(btns, text="🎲 Nový seed", command=self.on_reseed).pack(side="left", padx=4)
        r += 1

        self.status = tk.StringVar(value="Připraveno.")
        ttk.Label(frm, textvariable=self.status, foreground="#246").grid(
            row=r, column=0, columnspan=4, sticky="w", **pad)

    # ---- params ----
    def params(self):
        return {
            "chords": self.chords.get(),
            "cells": {c: v.get() for c, v in self.cellvars.items()},
            "alpha": self.alpha.get(),
            "voicing": self.voicing.get(),
            "scale": self.scale.get(),
            "rhythm": self.rhythm.get(),
            "in_four": self.in_four.get(),
            "bpm": self.bpm.get(),
            "seed": self.seed.get(),
        }

    # ---- akce ----
    def on_reseed(self):
        self.seed.set((self.seed.get() + 1) % 10000)
        self.status.set(f"Seed = {self.seed.get()}")

    def on_stop(self):
        self.stop_event.set()
        self.status.set("Stop.")

    def on_play(self):
        if self.worker and self.worker.is_alive():
            self.status.set("Už hraji — nejdřív Stop.")
            return
        self.stop_event.clear()
        self.worker = threading.Thread(target=self._gen_and_play, daemon=True)
        self.worker.start()

    def _gen_and_play(self):
        try:
            self.status.set("Generuji…")
            _, used = be.generate(self.params(), self.preview)
            self.status.set("Hraji…  takty: " + " ".join(used))
            be.play(self.preview, port_name=self.port.get(), stop_event=self.stop_event)
            if not self.stop_event.is_set():
                self.status.set("Hotovo. (takty: " + " ".join(used) + ")")
        except Exception as e:
            traceback.print_exc()
            self.status.set(f"Chyba: {e}")

    def on_export(self):
        path = filedialog.asksaveasfilename(
            title="Uložit cvičení jako MIDI", defaultextension=".mid",
            filetypes=[("MIDI", "*.mid")], initialfile="cviceni.mid")
        if not path:
            return
        try:
            _, used = be.generate(self.params(), path)
            self.status.set(f"Uloženo: {path}")
            messagebox.showinfo("Export", f"Uloženo:\n{path}")
        except Exception as e:
            traceback.print_exc()
            messagebox.showerror("Chyba exportu", str(e))


def v_fmt(var):
    """Pomocný StringVar zrcadlící DoubleVar na 2 desetinná místa."""
    s = tk.StringVar(value=f"{var.get():.2f}")
    var.trace_add("write", lambda *_: s.set(f"{var.get():.2f}"))
    return s


def _drop(frm, row, label, var, values, pad):
    ttk.Label(frm, text=label).grid(row=row, column=0, sticky="w", **pad)
    if var is not None:
        ttk.OptionMenu(frm, var, var.get(), *values).grid(
            row=row, column=1, sticky="we", **pad)


def main():
    root = tk.Tk()
    App(root)
    root.mainloop()


if __name__ == "__main__":
    main()
