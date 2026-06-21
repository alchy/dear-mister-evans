"""gui -- slim GUI nad čistým generátorem (voice).

Minimální první verze: výběr MIDI portu (kvůli zvuku!), akordy, hustota/bpm/seed,
Generuj & přehraj / Stop. Náhled a ~5 os dle SPECu přibudou. Hraje balík voice
(harmony + render + zatím triviální generate; fáze ③ vymění generátor za model).

Spuštění:  python improved/voice/gui.py
"""
import os, sys, json, threading, tempfile, traceback

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))   # improved/ na path
import tkinter as tk
from tkinter import ttk
import mido

from voice.harmony import Harmony
from voice.render import to_midi
from voice import build, view, progressions as prog, voicings as voi, lessons


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
        self._focus = lessons.LESSONS[0].get("focus")   # fokus aktuální lekce (zvýraznění vrstvy)
        self._motion = lessons.LESSONS[0].get("motion", "arp")   # pohyb linky (arp/scale) dle lekce
        self._bass_range = (36, 64)                # dynamický rozsah bas klaviatury (z draw)
        self._resize_job = None
        self._loading = False
        self._save_job = None
        self.state_path = os.path.join(os.getcwd(), "voice_gui_state.json")
        self._build()
        self._load_state()                         # obnov nastavení z minula
        self._register_traces()                    # ulož při změně
        root.protocol("WM_DELETE_WINDOW", self._on_close)

    def _build(self):
        # VLEVO sdílený panel (sylabus + kontext + přehrávání), VPRAVO tabule: hlavička lekce + náhled.
        self.root.rowconfigure(0, weight=1); self.root.columnconfigure(0, weight=1)
        outer = ttk.Frame(self.root, padding=8)
        outer.grid(row=0, column=0, sticky="nsew")
        outer.rowconfigure(0, weight=1); outer.columnconfigure(2, weight=1)
        left = ttk.Frame(outer); left.grid(row=0, column=0, sticky="n")
        ttk.Separator(outer, orient="vertical").grid(row=0, column=1, sticky="ns", padx=8)
        right = ttk.Frame(outer); right.grid(row=0, column=2, sticky="nsew")
        right.rowconfigure(1, weight=1); right.columnconfigure(0, weight=1)
        self._lesson_header(right)                         # row 0 = výklad lekce + A/B
        prev = ttk.LabelFrame(
            right, padding=4,
            text="Náhled: ● levá ruka · ● melodie (stupnice) · ● chromatický approach · ◯ guide (3/7) · ▼ landing · — co hraje")
        prev.grid(row=1, column=0, sticky="nsew")
        prev.rowconfigure(0, weight=1); prev.columnconfigure(0, weight=1)
        self._controls(left)
        self._preview(prev)
        self._menubar()                                    # port/tempo/flip/pokročilé do menu

    def _lesson_header(self, parent):
        """Tabule: titul lekce + výklad + A/B (vpravo nahoře nad náhledem)."""
        les0 = lessons.LESSONS[0]
        band = ttk.Frame(parent); band.grid(row=0, column=0, sticky="we", pady=(0, 6))
        band.columnconfigure(0, weight=1)
        self.lesson_title = tk.StringVar(value=les0["title"])
        ttk.Label(band, textvariable=self.lesson_title, font=("Segoe UI", 13, "bold"),
                  foreground="#234").grid(row=0, column=0, sticky="w")
        ttk.Button(band, text="▶ A/B (slyš rozdíl)", command=self.on_ab).grid(row=0, column=1, sticky="e", padx=4)
        self.explain = tk.StringVar(value=les0["explain"])
        ttk.Label(band, textvariable=self.explain, foreground="#345", anchor="w", justify="left",
                  wraplength=760).grid(row=1, column=0, columnspan=2, sticky="we", pady=(2, 0))

    def _controls(self, f):
        pad = {"padx": 4, "pady": 3}
        # === KURZ — sylabus lekcí (po blocích) ===
        gk = ttk.LabelFrame(f, text="KURZ — lekce", padding=4)
        gk.grid(row=0, column=0, sticky="we", pady=(0, 8))
        self.lesson = tk.StringVar(value=lessons.titles()[0])
        r = 0
        for name, les_list in lessons.blocks():
            ttk.Label(gk, text=name, font=("Segoe UI", 9, "bold"), foreground="#777").grid(
                row=r, column=0, sticky="w", padx=2, pady=(4, 0)); r += 1
            for les in les_list:
                ttk.Radiobutton(gk, text=les["title"], value=les["title"], variable=self.lesson,
                                command=self.apply_lesson).grid(row=r, column=0, sticky="w", padx=(14, 2)); r += 1

        # === Progrese (sdílený kontext cvičení) ===
        g = ttk.LabelFrame(f, text="Progrese", padding=6)
        g.grid(row=1, column=0, sticky="we", pady=(0, 8))
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
        ttk.Label(g, text="Vedení akordu (LH):").grid(row=2, column=0, sticky="w", **pad)
        self.voicing = tk.StringVar(value=voi.LABELS["rootless"])      # vždy volitelné (pilíř: akord v levé)
        ttk.OptionMenu(g, self.voicing, self.voicing.get(), *voi.LABELS.values()).grid(
            row=2, column=1, columnspan=3, sticky="we", **pad)

        # === Transport (akce -- sdílené; nastavení portu/tempa je v menu Přehrávání) ===
        btns = ttk.Frame(f); btns.grid(row=2, column=0, sticky="we", pady=(0, 6))
        ttk.Button(btns, text="▶ Generuj a přehraj", command=self.on_play).pack(side="left", padx=2)
        ttk.Button(btns, text="■ Stop", command=self.on_stop).pack(side="left", padx=2)
        ttk.Button(btns, text="🎲 jiný příklad", command=self.on_reseed).pack(side="left", padx=2)

        self._advanced(f)        # skrytý panel; zapíná menu Zobrazení -> Pokročilé

        self.status = tk.StringVar(value="Připraveno. (klik na klávesy = přehraj: vlevo akord, vpravo linka)")
        ttk.Label(f, textvariable=self.status, foreground="#246", anchor="w",
                  wraplength=300).grid(row=4, column=0, sticky="we", pady=(6, 0))

    def _advanced(self, f):
        """Skrytý panel generativních os -- lekce je nastaví, pokročilý uživatel ladí."""
        pad = {"padx": 4, "pady": 3}
        a = ttk.LabelFrame(f, text="Pokročilé — nastaví je lekce, můžeš doladit", padding=6)
        a.grid(row=3, column=0, sticky="we", pady=(0, 4)); a.grid_remove()
        self.adv_frame = a
        ttk.Label(a, text="Hustota:").grid(row=0, column=0, sticky="w", **pad)
        self.density = tk.IntVar(value=2)
        ttk.Spinbox(a, from_=1, to=4, textvariable=self.density, width=5).grid(row=0, column=1, sticky="w", **pad)
        ttk.Label(a, text="Approach:").grid(row=0, column=2, sticky="e", **pad)
        self.approach = tk.DoubleVar(value=0.7)
        ttk.Spinbox(a, from_=0.0, to=1.0, increment=0.1, textvariable=self.approach, width=5).grid(
            row=0, column=3, sticky="w", **pad)
        ttk.Label(a, text="Obklíčení:").grid(row=1, column=0, sticky="w", **pad)
        self.enclose = tk.DoubleVar(value=0.0)
        ttk.Spinbox(a, from_=0.0, to=1.0, increment=0.1, textvariable=self.enclose, width=5).grid(
            row=1, column=1, sticky="w", **pad)
        self.bebop = tk.BooleanVar(value=False)
        ttk.Checkbutton(a, text="Bebop stupnice", variable=self.bebop).grid(
            row=1, column=2, columnspan=2, sticky="w", **pad)
        ttk.Label(a, text="Barva (V→moll):").grid(row=2, column=0, sticky="w", **pad)
        self.color = tk.StringVar(value="inside")
        ttk.OptionMenu(a, self.color, "inside", "inside", "outside", "dim").grid(row=2, column=1, sticky="w", **pad)
        ttk.Label(a, text="Seed:").grid(row=2, column=2, sticky="e", **pad)
        self.seed = tk.IntVar(value=1)
        ttk.Spinbox(a, from_=0, to=9999, textvariable=self.seed, width=6).grid(row=2, column=3, sticky="w", **pad)
        ttk.Label(a, text="Akordy:").grid(row=4, column=0, sticky="w", **pad)
        self.chords = tk.StringVar(value=prog.build_changes(self.root_note.get(), self.mode.get(), self.pattern.get()))
        ttk.Entry(a, textvariable=self.chords, width=30).grid(row=4, column=1, columnspan=3, sticky="we", **pad)

    def _toggle_adv(self):
        (self.adv_frame.grid if self.adv_on.get() else self.adv_frame.grid_remove)()

    def _preview(self, f):
        self.canvas = tk.Canvas(f, width=820, height=680, bg="#fafafa", highlightthickness=0)
        sb = ttk.Scrollbar(f, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=sb.set)
        self.canvas.grid(row=0, column=0, sticky="nsew")
        sb.grid(row=0, column=1, sticky="ns")
        self.canvas.configure(cursor="hand2")
        self.canvas.bind("<Configure>", self._on_canvas_resize)
        self.canvas.bind("<Button-1>", self.on_kbd_click)    # klik na klávesy = přehraj blok

    def _refresh_patterns(self):
        pats = prog.patterns(self.mode.get())                 # nabídka postupů dle tonality
        m = self.pattern_menu["menu"]; m.delete(0, "end")
        for p in pats:
            m.add_command(label=p, command=lambda v=p: (self.pattern.set(v), self._rebuild()))
        if self.pattern.get() not in pats:
            self.pattern.set(pats[0])

    def _on_mode(self):
        self._refresh_patterns()
        self._rebuild()

    def _rebuild(self):
        self.chords.set(prog.build_changes(self.root_note.get(), self.mode.get(), self.pattern.get()))
        self.status.set(f"Postup: {self.root_note.get()} {self.mode.get()} · {self.pattern.get()}")

    # ---------- lekce (preset + výklad + A/B) ----------
    def apply_lesson(self, _title=None):
        les = lessons.by_title(self.lesson.get())
        p = les.get("preset", {})
        # VŽDY nastav všechny generativní páky (preset NEBO default) -> lekce je soběstačná,
        # nic neprosakuje z předchozí lekce (color/enclose/density/...).
        self.density.set(p.get("density", 2))
        self.approach.set(p.get("approach", 0.5))
        self.enclose.set(p.get("enclose", 0.0))
        self.bebop.set(bool(p.get("bebop", False)))
        self.color.set(p.get("color", "inside"))
        self.voicing.set(voi.LABELS.get(p.get("voicing", "rootless"), voi.LABELS["rootless"]))
        if "root" in p: self.root_note.set(p["root"])
        if "mode" in p:
            self.mode.set(p["mode"]); self._refresh_patterns()
        if "pattern" in p: self.pattern.set(p["pattern"])
        self._focus = les.get("focus")               # zvýrazni vrstvu lekce v náhledu
        self._motion = les.get("motion", "arp")      # arp (drill) vs scale (běh po stupnici)
        if "chords" in p:
            self.chords.set(p["chords"])             # explicitní progrese (přebije stavebnici)
        else:
            self._rebuild()
        self.lesson_title.set(les["title"])
        self.explain.set(les["explain"])
        self.status.set(f"Lekce: {les['title']}")

    def on_ab(self):
        les = lessons.by_title(self.lesson.get())
        if not les.get("ab"):
            self.status.set("Tato lekce nemá A/B."); return
        self._start(lambda: self._work_ab(les["ab"]))

    def _work_ab(self, ab):
        import time
        try:
            for tag in ("A", "B"):
                if self.stop.is_set():
                    break
                H, landings, line, density = self._gen(**ab[tag])
                to_midi(H, line, self.preview, bpm=self.bpm.get(), density=density)
                self._draw_state = (H, landings, line)
                self.root.after(0, self._redraw)
                self.status.set(f"A/B — {tag}: {ab[tag]}")
                self._with_port(lambda out: self._send_follow(out, self.preview, len(H)))
                time.sleep(0.5)
        except Exception as e:
            traceback.print_exc(); self.status.set(f"Chyba: {e}")
        finally:
            self.root.after(0, lambda: self._set_playing(None))

    def _kind(self):
        return {v: k for k, v in voi.LABELS.items()}.get(self.voicing.get(), "rootless")

    def _gen(self, **over):
        """Vygeneruj s případnými přepisy parametrů (pro A/B) -> (H, landings, line, density)."""
        density = int(over.get("density", self.density.get()))
        approach = float(over.get("approach", self.approach.get()))
        enclose = float(over.get("enclose", self.enclose.get()))
        bebop = bool(over.get("bebop", self.bebop.get()))
        color = over.get("color", self.color.get())
        kind = over.get("voicing", self._kind())
        motion = over.get("motion", self._motion)
        H = Harmony(self.chords.get(), color=color, voicing=kind, bebop=bebop)
        line = build.generate(H, density=density, seed=self.seed.get(), approach=approach,
                              enclose=enclose, motion=motion)
        _, landings = build.guide_path(H)
        return H, landings, line, density

    # ---------- serializace nastavení do JSON (jako prototyp) ----------
    PERSIST = ["lesson", "root_note", "mode", "pattern", "chords", "density", "approach",
               "enclose", "bebop", "color", "bpm", "seed", "voicing", "port", "flip"]

    def _state_dict(self):
        return {k: getattr(self, k).get() for k in self.PERSIST if hasattr(self, k)}

    def _save_state(self):
        self._save_job = None
        try:
            with open(self.state_path, "w", encoding="utf-8") as fh:
                json.dump(self._state_dict(), fh, ensure_ascii=False, indent=2)
        except Exception:
            traceback.print_exc()

    def _load_state(self):
        try:
            with open(self.state_path, encoding="utf-8") as fh:
                d = json.load(fh)
        except Exception:
            return
        self._loading = True
        try:
            def setv(k):
                if k in d and hasattr(self, k):
                    try:
                        getattr(self, k).set(d[k])
                    except Exception:
                        pass
            setv("root_note"); setv("mode")
            self._refresh_patterns()                  # nabídka postupů dle načtené tonality
            for k in ("pattern", "chords", "density", "approach", "enclose", "bebop",
                      "color", "bpm", "seed", "voicing", "port", "flip", "lesson"):
                setv(k)
            if "lesson" in d:
                les = lessons.by_title(self.lesson.get())
                self.lesson.set(les["title"])          # normalizuj (po přečíslování titulů)
                self.lesson_title.set(les["title"])
                self.explain.set(les["explain"])
                self._focus = les.get("focus")
                self._motion = les.get("motion", "arp")
            self.status.set("Obnoveno z minula.")
        finally:
            self._loading = False
        self._draw_only()                             # ukaž obnovenou progresi v náhledu

    def _draw_only(self):
        """Vygeneruj + vykresli náhled BEZ přehrání (po startu / změně lekce)."""
        try:
            H, landings, line, _ = self._gen()
            self._draw_state = (H, landings, line)
            self.root.after(0, self._redraw)
        except Exception:
            traceback.print_exc()

    def _register_traces(self):
        for k in self.PERSIST:
            if hasattr(self, k):
                getattr(self, k).trace_add("write", lambda *_: self._schedule_change())

    def _schedule_change(self):
        """Při změně nastavení: debounce -> ulož + OBNOV NÁHLED (general refresh)."""
        if self._loading:
            return
        if self._save_job:
            try:
                self.root.after_cancel(self._save_job)
            except Exception:
                pass
        self._save_job = self.root.after(250, self._on_change)

    def _on_change(self):
        self._save_job = None
        self._save_state()
        self._draw_only()                              # každá změna -> přegeneruj + překresli

    def _on_close(self):
        if self._save_job:                            # zruš čekající debounce save
            try:
                self.root.after_cancel(self._save_job)
            except Exception:
                pass
        self._save_state()
        self.root.destroy()

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
            self._bass_range = view.draw(self.canvas, H, land, line,
                                         width=self.canvas.winfo_width(), flip=self.flip.get(),
                                         focus=self._focus)

    # ---- klik na klaviaturu = přehraj zobrazený blok (vlevo akord, vpravo linka) ----
    # ---------- JEDEN model přehrávání (DRY pro všechny komponenty) ----------
    def _start(self, work):
        """Přeruš případné předchozí přehrávání a spusť nový worker. Společné pro
        plné přehrání i klik na klávesy."""
        if self.worker and self.worker.is_alive():
            self.stop.set(); self.worker.join(timeout=0.3)
        self.stop.clear()
        self.worker = threading.Thread(target=work, daemon=True)
        self.worker.start()

    def _with_port(self, body):
        """Otevři port, spusť body(out), na konci VŽDY zhasni všechny tóny."""
        name = self.port.get()
        if not name:
            self.status.set("Není vybraný MIDI port."); return
        with mido.open_output(name) as out:
            try:
                body(out)
            finally:
                for ch in range(16):
                    out.send(mido.Message("control_change", channel=ch, control=123, value=0))

    def _set_playing(self, row, n_bars=0):
        view.set_playing(self.canvas, row, n_bars, self._bass_range, flip=self.flip.get())

    def on_kbd_click(self, event):
        if self._draw_state is None:
            return
        H, land, line = self._draw_state
        x = self.canvas.canvasx(event.x); y = self.canvas.canvasy(event.y)
        h = view.hit(self.canvas, x, y, len(H), self._bass_range,
                     width=self.canvas.winfo_width(), flip=self.flip.get())
        if not h:
            return
        row, side = h; bar = H.bars[row]
        if side == "chord":
            notes, what = [bar.bass] + list(bar.voicing), f"akord {view._sym(bar)}"
        else:
            notes, what = (view._by_bar(line, len(H))[row] if line else []), f"linka {view._sym(bar)}"
        self._start(lambda: self._work_block(side, notes, what))

    def _work_block(self, side, notes, what):
        notes = [int(n) for n in notes if n]
        if not notes:
            return
        self.status.set(f"Hraji {what}…")
        self._with_port(lambda out: self._send_block(out, side, notes))
        if not self.stop.is_set():
            self.status.set(f"Hotovo ({what}).")

    def _send_block(self, out, side, notes):
        import time
        if side == "chord":                                   # akord = vše naráz, drž
            for nn in notes:
                out.send(mido.Message("note_on", note=nn, velocity=76))
            time.sleep(1.6)
            for nn in notes:
                out.send(mido.Message("note_off", note=nn, velocity=0))
        else:                                                 # linka = tóny v pořadí
            d = 60.0 / max(1, self.bpm.get()) / 2
            for nn in notes:
                if self.stop.is_set():
                    break
                out.send(mido.Message("note_on", note=nn, velocity=92)); time.sleep(d * 0.9)
                out.send(mido.Message("note_off", note=nn, velocity=0)); time.sleep(d * 0.1)

    def _menubar(self):
        """Horní menu programu: Přehrávání (port, tempo) + Zobrazení (flip, Pokročilé)."""
        names = mido.get_output_names() or [""]
        self.port = tk.StringVar(value=default_port(names))
        self.bpm = tk.IntVar(value=110)
        self.flip = tk.BooleanVar(value=False)
        self.adv_on = tk.BooleanVar(value=False)
        m = tk.Menu(self.root)
        play = tk.Menu(m, tearoff=0)
        self.port_menu = tk.Menu(play, tearoff=0)
        self._fill_ports()
        play.add_cascade(label="MIDI port", menu=self.port_menu)
        bpm_menu = tk.Menu(play, tearoff=0)
        for t in (60, 80, 90, 100, 110, 120, 140, 160, 180):
            bpm_menu.add_radiobutton(label=str(t), value=t, variable=self.bpm)
        play.add_cascade(label="Tempo (BPM)", menu=bpm_menu)
        m.add_cascade(label="Přehrávání", menu=play)
        vw = tk.Menu(m, tearoff=0)
        vw.add_checkbutton(label="Obrátit pořadí náhledu (zdola nahoru)", variable=self.flip,
                           command=self._redraw)
        vw.add_checkbutton(label="Pokročilé: generativní páky", variable=self.adv_on,
                           command=self._toggle_adv)
        m.add_cascade(label="Zobrazení", menu=vw)
        self.root.config(menu=m)

    def _fill_ports(self):
        self.port_menu.delete(0, "end")
        names = mido.get_output_names() or [""]
        for n in names:
            self.port_menu.add_radiobutton(label=n, value=n, variable=self.port)
        if self.port.get() not in names:
            self.port.set(default_port(names))
        self.port_menu.add_separator()
        self.port_menu.add_command(label="Obnovit porty", command=self._fill_ports)

    def on_reseed(self):
        self.seed.set((self.seed.get() + 1) % 10000)
        self.status.set(f"Seed = {self.seed.get()}")

    def on_stop(self):
        self.stop.set()
        self._set_playing(None)
        self.status.set("Stop.")

    def on_play(self):
        self._start(self._work_generate)                      # stejný model jako klik

    def _work_generate(self):
        try:
            self.status.set("Generuji…")
            H, landings, line, density = self._gen()
            to_midi(H, line, self.preview, bpm=self.bpm.get(), density=density)
            self._draw_state = (H, landings, line)             # ulož pro responzivní překreslení
            self.root.after(0, self._redraw)
            self.status.set(f"Hraji…  {len(H)} akordů, {len(line)} not")
            self._with_port(lambda out: self._send_follow(out, self.preview, len(H)))
            if not self.stop.is_set():
                self.status.set("Hotovo.")
        except Exception as e:
            traceback.print_exc()
            self.status.set(f"Chyba: {e}")
        finally:
            self.root.after(0, lambda: self._set_playing(None))

    def _send_follow(self, out, path, n_bars):
        """Plné přehrání: z playheadu rozsvěcí zelenou linku u právě hraného akordu."""
        bar_s = 4 * 60.0 / max(1, self.bpm.get())
        cur = -1; t = 0.0
        for msg in mido.MidiFile(path).play():
            if self.stop.is_set():
                break
            t += msg.time
            bar = int(t / bar_s)
            if bar != cur and 0 <= bar < n_bars:
                cur = bar
                self.root.after(0, lambda b=bar: self._set_playing(b, n_bars))
            out.send(msg)


def main():
    root = tk.Tk()
    App(root)
    root.mainloop()


if __name__ == "__main__":
    main()
