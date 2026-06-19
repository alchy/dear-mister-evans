"""Prehravac MIDI souboru na MIDI-out port (loopMIDI -> virtualni piano)."""
import sys, time
import mido

PORT_HINT = "loopMIDI Port 1"

def find_port():
    names = mido.get_output_names()
    for n in names:
        if PORT_HINT.lower() in n.lower():
            return n
    # zkus "loopMIDI" / "Port 1"
    for n in names:
        if "loopmidi" in n.lower() or "port 1" in n.lower():
            return n
    return names[0] if names else None

def play(path, port_name=None):
    port_name = port_name or find_port()
    if not port_name:
        print("ZADNY MIDI-out port nenalezen."); return
    mid = mido.MidiFile(path)
    print(f"hraji {path}  ->  '{port_name}'  ({mid.length:.1f}s)")
    with mido.open_output(port_name) as out:
        try:
            for msg in mid.play():
                out.send(msg)
        finally:
            for ch in range(16):
                out.send(mido.Message('control_change', channel=ch, control=123, value=0))
    print("hotovo.")

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--list":
        print("MIDI-out porty:")
        for n in mido.get_output_names():
            print("  -", n)
    else:
        play(sys.argv[1] if len(sys.argv) > 1 else None)
