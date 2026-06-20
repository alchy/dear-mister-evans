"""cli -- spustí čistý generátor (fáze ②): akordy -> harmonie -> (triviální) linka -> MIDI.

Použití:
  python improved/voice/cli.py --chords "Dm7 G7 Cmaj7" --density 2 --bpm 110
  (--play přehraje na MIDI-out port; jinak jen uloží MIDI)
"""
import os, sys, argparse

# přidej improved/ (root), NE voice/ -> 'voice' balík + sourozenci (scale_drill…) se
# najdou, ale voice.harmony nestíní prototypový top-level harmony (detekce akordů).
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from voice.harmony import Harmony
from voice.generate import trivial_line
from voice.render import to_midi


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--chords", default="Dm7 G7 Cmaj7 Cmaj7")
    ap.add_argument("--density", type=int, default=2, choices=[1, 2, 3, 4])
    ap.add_argument("--bpm", type=int, default=110)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--out", default=os.path.join("outputs_voice", "voice.mid"))
    ap.add_argument("--play", action="store_true")
    ap.add_argument("--port", default=None)
    a = ap.parse_args()

    H = Harmony(a.chords)
    line = trivial_line(H, density=a.density, seed=a.seed)
    to_midi(H, line, a.out, bpm=a.bpm, density=a.density)
    print(f"akordů={len(H)} not={len(line)} -> {a.out}")
    for i, b in enumerate(H):
        print(f"  takt {i}: bas={b.bass} voicing={b.voicing} guides={b.guides} |scale|={len(b.scale)}")

    if a.play:
        import mido
        name = a.port or _default_port()
        with mido.open_output(name) as outp:
            for msg in mido.MidiFile(a.out).play():
                outp.send(msg)


def _default_port():
    import mido
    names = mido.get_output_names()
    for want in ("wavetable", "loopmidi port 1"):     # Wavetable první = jistota zvuku
        for n in names:
            if want in n.lower():
                return n
    return names[0] if names else None


if __name__ == "__main__":
    main()
