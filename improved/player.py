"""Prehravac MIDI na MIDI-out port (loopMIDI -> virtualni piano).

  python player.py soubor.mid           # prehraj jeden soubor
  python player.py slozka/              # prehraj vsechny *_full.mid ve slozce
  python player.py --list               # vypis MIDI-out porty
"""
import sys, os, glob
import mido

PORT_HINT = "loopMIDI Port 1"

def find_port():
    names = mido.get_output_names()
    for n in names:
        if PORT_HINT.lower() in n.lower():
            return n
    for n in names:
        if "loopmidi" in n.lower() or "port 1" in n.lower():
            return n
    return names[0] if names else None

def play_one(path, out):
    mid = mido.MidiFile(path)
    print(f"  hraji {os.path.basename(path)}  ({mid.length:.0f}s)", flush=True)
    for msg in mid.play():
        out.send(msg)
    for ch in range(16):
        out.send(mido.Message('control_change', channel=ch, control=123, value=0))

def play(paths, port_name=None):
    port_name = port_name or find_port()
    if not port_name:
        print("ZADNY MIDI-out port nenalezen."); return
    print(f"port: {port_name}", flush=True)
    with mido.open_output(port_name) as out:
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
    if args and args[0] == "--list":
        print("MIDI-out porty:")
        for n in mido.get_output_names():
            print("  -", n)
    elif args and os.path.isdir(args[0]):
        files = sorted(glob.glob(os.path.join(args[0], "*_full.mid")))
        print(f"playlist: {len(files)} skladeb ze '{args[0]}'")
        play(files)
    elif args:
        play([args[0]])
    else:
        print("pouziti: player.py <soubor.mid | slozka | --list>")
