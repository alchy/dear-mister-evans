"""Prehravac MIDI na MIDI-out port (loopMIDI -> virtualni piano, nebo primy synth).

  python player.py soubor.mid                 # prehraj jeden soubor
  python player.py slozka/                     # prehraj vsechny *_full.mid ve slozce
  python player.py soubor.mid --port wavetable # vyber vystupni port (substring)
  python player.py --list                      # vypis MIDI-out porty
"""
import sys, os, glob
import mido

PORT_HINT = "loopMIDI Port 1"

def pick_port(hint=None):
    names = mido.get_output_names()
    if hint:                                   # uzivatelem zadany substring
        for n in names:
            if hint.lower() in n.lower():
                return n
        return None
    for n in names:                            # default: loopMIDI Port 1 (presne)
        if n.lower() == PORT_HINT.lower():
            return n
    for n in names:
        if "loopmidi" in n.lower():
            return n
    return names[0] if names else None

def play_one(path, out):
    mid = mido.MidiFile(path)
    print(f"  hraji {os.path.basename(path)}  ({mid.length:.0f}s)", flush=True)
    for msg in mid.play():
        out.send(msg)
    for ch in range(16):
        out.send(mido.Message('control_change', channel=ch, control=123, value=0))

def play(paths, port_hint=None):
    name = pick_port(port_hint)
    if not name:
        print(f"MIDI-out port nenalezen (hint={port_hint!r}). Dostupne:")
        for n in mido.get_output_names():
            print("  -", n)
        return
    print(f"port: {name}", flush=True)
    with mido.open_output(name) as out:
        try:
            for p in paths:
                play_one(p, out)
        except KeyboardInterrupt:
            print("\nzastaveno.")
        finally:
            for ch in range(16):
                out.send(mido.Message('control_change', channel=ch, control=123, value=0))
    print("hotovo.")

if __name__ == "__main__":
    args = sys.argv[1:]
    port_hint = None
    if "--port" in args:
        i = args.index("--port")
        port_hint = args[i + 1] if i + 1 < len(args) else None
        del args[i:i + 2]
    if args and args[0] == "--list":
        print("MIDI-out porty:")
        for n in mido.get_output_names():
            print("  -", n)
    elif args and os.path.isdir(args[0]):
        files = sorted(glob.glob(os.path.join(args[0], "*_full.mid")))
        print(f"playlist: {len(files)} skladeb ze '{args[0]}'")
        play(files, port_hint)
    elif args:
        play([args[0]], port_hint)
    else:
        print("pouziti: player.py <soubor.mid | slozka | --list> [--port <substring>]")
