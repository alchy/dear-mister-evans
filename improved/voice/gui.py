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

from voice.harmony import Harmony
from voice.render import to_midi
from voice import build, view, progressions as prog


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
        root.resizable(True, True)                 # okno zvětšitelné -> klávesnice škáluje
        self.stop = threading.Event()
        self.worker = None
        self.preview = os.path.join(tempfile.gettempdir(), "voice_preview.mid")
        self._draw_state = None                    # (harmony, landings, line) pro překreslení
        self._resize_job = None
        self._build()

    def _build(self):
        # dvoupanelový layout: VLEVO stavebnice cvičení, VPRAVO klaviatura/náhled (škáluje)
        self.root.rowconfigure(0, weight=1); self.root.columnconfigure(0, weight=1)
        outer = ttk.Frame(self.root, padding=8)
        outer.grid(row=0, column=0, sticky="nsew")
        outer.rowconfigure(0, weight=1); outer.columnconfigure(2, weight=1)
        left = ttk.Frame(outer); left.grid(row=0, column=0, sticky="n")
        ttk.Separator(outer, orient="vertical").grid(row=0, column=1, sticky="ns", padx=8)
        right = ttk.LabelFrame(
            outer, padding=4,
            text="Náhled: ● levá ruka (přesun) · ● tóny stupnice · ◯ guide (3/7) · ▼ landing · — co hraje")
        right.grid(row=0, column=2, sticky="nsew")
        right.rowconfigure(0, weight=1); right.columnconfigure(0, weight=1)
        self._controls(left)
        self._preview(right)

    def _controls(self, f):
        pad = {"padx": 4, "pady": 3}
        # === Progrese — stavebnice cvičení ===
        g = ttk.LabelFrame(f, text="Progrese — stavebnice cvičení", padding=6)
        g.grid(row=0, column=0, sticky="we", pady=(0, 8))
        ttk.Label(g, text="Tónika:").grid(row=0, column=0, sticky="w", **pad)
        self.root_note = tk.StringVar(value="C")
        ttk.OptionMenu(g, self.root_note, "C", *prog.NAMES,
                       command=lambda *_: self._rebuild()).grid(row=0, column=1, sticky="we", **pad)
        ttk.Label(g, text="Tonalita:").grid(row=0, column=2, sticky="e", **pad)
        self.mode = tk.StringVar(value="dur")
        ttk.OptionMenu(g, self.mode, "dur", "dur", "moll",
                       command=lambda *_: self._on_mode()).grid(row=0, column=3, sticky="we", **pad)
        ttk.Label(g, text="Postup:").grid(row=1, column=0, sticky="w", **pad)
        self.pattern = tk.StringVar(value=prog.patterns("dur")[0])
        self.pattern_menu = ttk.OptionMenu(g, self.pattern, self.pattern.get(), *prog.patterns("dur"),
                                           command=lambda *_: self._rebuild())
        self.pattern_menu.grid(row=1, column=1, columnspan=3, sticky="we", **pad)
        ttk.Label(g, text="Akordy:").grid(row=2, column=0, sticky="w", **pad)
        self.chords = tk.StringVar(value=prog.build_changes("C", "dur", self.pattern.get()))
        ttk.Entry(g, textvariable=self.chords, width=34).grid(row=2, column=1, columnspan=3, sticky="we", **pad)

        # === Cvičení (generování) ===
        g2 = ttk.LabelFrame(f, text="Cvičení", padding=6)
        g2.grid(row=1, column=0, sticky="we", pady=(0, 8))
        ttk.Label(g2, text="Hustota:").grid(row=0, column=0, sticky="w", **pad)
        self.density = tk.IntVar(value=2)
        ttk.Spinbox(g2, from_=1, to=4, textvariable=self.density, width=5).grid(row=0, column=1, sticky="w", **pad)
        ttk.Label(g2, text="Approach:").grid(row=0, column=2, sticky="e", **pad)
        self.approach = tk.DoubleVar(value=0.7)
        ttk.Spinbox(g2, from_=0.0, to=1.0, increment=0.1, textvariable=self.approach, width=5).grid(
            row=0, column=3, sticky="w", **pad)
        ttk.Label(g2, text="Barva (V→moll):").grid(row=1, column=0, sticky="w", **pad)
        self.color = tk.StringVar(value="inside")
        ttk.OptionMenu(g2, self.color, "inside", "inside", "outside").grid(row=1, column=1, sticky="w", **pad)
        ttk.Label(g2, text="BPM:").grid(row=1, column=2, sticky="e", **pad)
        self.bpm = tk.IntVar(value=110)
        ttk.Spinbox(g2, from_=40, to=240, textvariable=self.bpm, width=5).grid(row=1, column=3, sticky="w", **pad)
        ttk.Label(g2, text="Seed:").grid(row=2, column=0, sticky="w", **pad)
        self.seed = tk.IntVar(value=1)
        ttk.Spinbox(g2, from_=0, to=9999, textvariable=self.seed, width=6).grid(row=2, column=1, sticky="w", **pad)

        # === Přehrávání ===
        g3 = ttk.LabelFrame(f, text="Přehrávání", padding=6)
        g3.grid(row=2, column=0, sticky="we")
        ttk.Label(g3, text="MIDI port:").grid(row=0, column=0, sticky="w", **pad)
        names = mido.get_output_names() or [""]
        self.port = tk.StringVar(value=default_port(names))
        self.port_menu = ttk.OptionMenu(g3, self.port, self.port.get(), *names)
        self.port_menu.grid(row=0, column=1, columnspan=2, sticky="we", **pad)
        ttk.Button(g3, text="⟳", width=3, command=self.refresh_ports).grid(row=0, column=3, **pad)
        btns = ttk.Frame(g3); btns.grid(row=1, column=0, columnspan=4, sticky="we", pady=6)
        ttk.Button(btns, text="▶ Generuj a přehraj", command=self.on_play).pack(side="left", padx=2)
        ttk.Button(btns, text="■ Stop", command=self.on_stop).pack(side="left", padx=2)
        ttk.Button(btns, text="🎲", width=3, command=self.on_reseed).pack(side="left", padx=2)

        self.status = tk.StringVar(value="Připraveno. (stavebnice cíl+spojka)")
        ttk.Label(f, textvariable=self.status, foreground="#246", anchor="w",
                  wraplength=300).grid(row=3, column=0, sticky="we", pady=(8, 0))

    def _preview(self, f):
        self.canvas = tk.Canvas(f, width=820, height=680, bg="#fafafa", highlightthickness=0)
        sb = ttk.Scrollbar(f, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=sb.set)
        self.canvas.grid(row=0, column=0, sticky="nsew")
        sb.grid(row=0, column=1, sticky="ns")
        self.canvas.bind("<Configure>", self._on_canvas_resize)

    def _on_mode(self):
        pats = prog.patterns(self.mode.get())                 # přepiš nabídku postupů dle tonality
        m = self.pattern_menu["menu"]; m.delete(0, "end")
        for p in pats:
            m.add_command(label=p, command=lambda v=p: (self.pattern.set(v), self._rebuild()))
        if self.pattern.get() not in pats:
            self.pattern.set(pats[0])
        self._rebuild()

    def _rebuild(self):
        self.chords.set(prog.build_changes(self.root_note.get(), self.mode.get(), self.pattern.get()))
        self.status.set(f"Postup: {self.root_note.get()} {self.mode.get()} · {self.pattern.get()}")

    def _on_canvas_resize(self, event):
        if self._draw_state is None:
            return
        if self._resize_job:
            try:
                self.root.after_cancel(self._resize_job)
            except Exception:
                pass
        self._resize_job = self.root.after(120, self._redraw)

    def _redraw(self):
        self._resize_job = None
        if self._draw_state:
            H, land, line = self._draw_state
            view.draw(self.canvas, H, land, line, width=self.canvas.winfo_width())

    def refresh_ports(self):
        names = mido.get_output_names() or [""]
        menu = self.port_menu["menu"]
        menu.delete(0, "end")
        for n in names:
            menu.add_command(label=n, command=lambda v=n: self.port.set(v))
        if self.port.get() not in names:
            self.port.set(default_port(names))
        self.status.set(f"Porty obnoveny ({len(names)}).")

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
            self._draw_state = (H, landings, line)             # ulož pro responzivní překreslení
            self.root.after(0, self._redraw)
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
