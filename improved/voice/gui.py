"""gui -- slim GUI nad čistým generátorem (voice).

Minimální první verze: výběr MIDI portu (kvůli zvuku!), akordy, hustota/bpm/seed,
Generuj & přehraj / Stop. Náhled a ~5 os dle SPECu přibudou. Hraje balík voice
(harmony + render + zatím triviální generate; fáze ③ vymění generátor za model).

Spuštění:  python improved/voice/gui.py
"""
import os, sys, threading, tempfile, traceback

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))   # improved/ na path
import tkinter as tk
from tkinter import ttk
import mido

from voice.harmony import Harmony, TEMPLATES
from voice.render import to_midi
from voice import build, view


def default_port(names):
    # GS Wavetable první = "vždy slyšet" jistota; loopMIDI/Vienna v rozbalovátku.
    for want in ("wavetable", "loopmidi port 1"):
        for n in names:
            if want in n.lower():
                return n
    return names[0] if names else ""


class App:
    def __init__(self, root):
        self.root = root
        root.title("voice — čistý generátor")
        root.resizable(False, False)
        self.stop = threading.Event()
        self.worker = None
        self.preview = os.path.join(tempfile.gettempdir(), "voice_preview.mid")
        self._build()

    def _build(self):
        # dvoupanelový layout: VLEVO settings, VPRAVO klaviatura/náhled
        outer = ttk.Frame(self.root, padding=10)
        outer.grid(sticky="nsew")
        left = ttk.Frame(outer)
        left.grid(row=0, column=0, sticky="n")
        ttk.Separator(outer, orient="vertical").grid(row=0, column=1, sticky="ns", padx=10)
        right = ttk.LabelFrame(
            outer, padding=4,
            text="Náhled: ● levá ruka (přesun) · ● tóny stupnice · ◯ guide (3/7) · ▼ landing · — co hraje")
        right.grid(row=0, column=2, sticky="n")
        self._controls(left)
        self._preview(right)

    def _controls(self, f):
        pad = {"padx": 5, "pady": 4}
        r = 0
        names = mido.get_output_names() or [""]
        ttk.Label(f, text="MIDI port:").grid(row=r, column=0, sticky="w", **pad)
        self.port = tk.StringVar(value=default_port(names))
        self.port_menu = ttk.OptionMenu(f, self.port, self.port.get(), *names)
        self.port_menu.grid(row=r, column=1, columnspan=2, sticky="we", **pad)
        ttk.Button(f, text="⟳", width=3, command=self.refresh_ports).grid(row=r, column=3, **pad)
        r += 1

        ttk.Label(f, text="Šablona:").grid(row=r, column=0, sticky="w", **pad)
        self.template = tk.StringVar(value="ii–V–I dur (C)")
        ttk.OptionMenu(f, self.template, self.template.get(), *TEMPLATES,
                       command=self._set_template).grid(row=r, column=1, columnspan=3, sticky="we", **pad)
        r += 1

        ttk.Label(f, text="Akordy:").grid(row=r, column=0, sticky="w", **pad)
        self.chords = tk.StringVar(value=TEMPLATES["ii–V–I dur (C)"])
        ttk.Entry(f, textvariable=self.chords, width=28).grid(row=r, column=1, columnspan=3, sticky="we", **pad)
        r += 1

        ttk.Label(f, text="Hustota:").grid(row=r, column=0, sticky="w", **pad)
        self.density = tk.IntVar(value=2)
        ttk.Spinbox(f, from_=1, to=4, textvariable=self.density, width=5).grid(row=r, column=1, sticky="w", **pad)
        ttk.Label(f, text="BPM:").grid(row=r, column=2, sticky="e", **pad)
        self.bpm = tk.IntVar(value=110)
        ttk.Spinbox(f, from_=40, to=240, textvariable=self.bpm, width=6).grid(row=r, column=3, sticky="w", **pad)
        r += 1

        ttk.Label(f, text="Seed:").grid(row=r, column=0, sticky="w", **pad)
        self.seed = tk.IntVar(value=1)
        ttk.Spinbox(f, from_=0, to=9999, textvariable=self.seed, width=6).grid(row=r, column=1, sticky="w", **pad)
        ttk.Label(f, text="Approach:").grid(row=r, column=2, sticky="e", **pad)
        self.approach = tk.DoubleVar(value=0.7)
        ttk.Spinbox(f, from_=0.0, to=1.0, increment=0.1, textvariable=self.approach, width=6).grid(
            row=r, column=3, sticky="w", **pad)
        r += 1

        ttk.Label(f, text="Barva (V→moll):").grid(row=r, column=0, sticky="w", **pad)
        self.color = tk.StringVar(value="inside")
        ttk.OptionMenu(f, self.color, self.color.get(), "inside", "outside").grid(
            row=r, column=1, sticky="w", **pad)
        r += 1

        btns = ttk.Frame(f)
        btns.grid(row=r, column=0, columnspan=4, sticky="we", pady=8)
        ttk.Button(btns, text="▶ Generuj a přehraj", command=self.on_play).pack(side="left", padx=3)
        ttk.Button(btns, text="■ Stop", command=self.on_stop).pack(side="left", padx=3)
        ttk.Button(btns, text="🎲 Seed", command=self.on_reseed).pack(side="left", padx=3)
        r += 1

        self.status = tk.StringVar(value="Připraveno. (builder cíl+spojka)")
        ttk.Label(f, textvariable=self.status, foreground="#246", width=34, anchor="w",
                  wraplength=260).grid(row=r, column=0, columnspan=4, sticky="w", **pad)

    def _preview(self, f):
        self.canvas = tk.Canvas(f, width=820, height=680, bg="#fafafa", highlightthickness=0)
        sb = ttk.Scrollbar(f, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=sb.set)
        self.canvas.grid(row=0, column=0, sticky="nsew")
        sb.grid(row=0, column=1, sticky="ns")

    def refresh_ports(self):
        names = mido.get_output_names() or [""]
        menu = self.port_menu["menu"]
        menu.delete(0, "end")
        for n in names:
            menu.add_command(label=n, command=lambda v=n: self.port.set(v))
        if self.port.get() not in names:
            self.port.set(default_port(names))
        self.status.set(f"Porty obnoveny ({len(names)}).")

    def _set_template(self, name):
        if name in TEMPLATES:
            self.chords.set(TEMPLATES[name])
            self.status.set(f"Šablona: {name}")

    def on_reseed(self):
        self.seed.set((self.seed.get() + 1) % 10000)
        self.status.set(f"Seed = {self.seed.get()}")

    def on_stop(self):
        self.stop.set()
        self.status.set("Stop.")

    def on_play(self):
        if self.worker and self.worker.is_alive():
            self.status.set("Už hraji — nejdřív Stop.")
            return
        self.stop.clear()
        self.worker = threading.Thread(target=self._gen_play, daemon=True)
        self.worker.start()

    def _gen_play(self):
        try:
            H = Harmony(self.chords.get(), color=self.color.get())
            line = build.generate(H, density=self.density.get(),
                                  seed=self.seed.get(), approach=self.approach.get())
            _, landings = build.guide_path(H)
            to_midi(H, line, self.preview, bpm=self.bpm.get(), density=self.density.get())
            self.root.after(0, lambda: view.draw(self.canvas, H, landings, line))   # tabule
            self.status.set(f"Hraji…  {len(H)} akordů, {len(line)} not")
            self._play_follow(self.preview, len(H))
            if not self.stop.is_set():
                self.status.set("Hotovo.")
        except Exception as e:
            traceback.print_exc()
            self.status.set(f"Chyba: {e}")
        finally:
            self.root.after(0, lambda: view.set_playing(self.canvas, None, 0))

    def _play_follow(self, path, n_bars):
        """Přehraje MIDI a z playheadu rozsvěcí zelenou linku u právě hraného akordu."""
        name = self.port.get()
        if not name:
            raise RuntimeError("Není vybraný MIDI port.")
        bar_s = 4 * 60.0 / max(1, self.bpm.get())
        cur = -1; t = 0.0
        with mido.open_output(name) as out:
            for msg in mido.MidiFile(path).play():
                if self.stop.is_set():
                    break
                t += msg.time
                bar = int(t / bar_s)
                if bar != cur and 0 <= bar < n_bars:
                    cur = bar
                    self.root.after(0, lambda b=bar: view.set_playing(self.canvas, b, n_bars))
                out.send(msg)
            for ch in range(16):
                out.send(mido.Message("control_change", channel=ch, control=123, value=0))


def main():
    root = tk.Tk()
    App(root)
    root.mainloop()


if __name__ == "__main__":
    main()
