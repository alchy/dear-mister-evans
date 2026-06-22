"""io_midi -- načtení živého MIDI do not v REÁLNÉM čase (sekundy).

Vstup je jednokanálové živé hraní. Nezajímá nás nominální tempo/mřížka MIDI
(je to flat default), zajímají nás přesné časy onsetů. mido při iteraci přes
MidiFile dává delty už v sekundách (s ohledem na set_tempo), takže akumulací
dostaneme absolutní čas každé noty.
"""
from collections import namedtuple
import mido

Note = namedtuple("Note", "onset dur pitch vel")   # vše v sekundách / MIDI 0-127


def load_notes(path):
    """MIDI -> seřazený list Note(onset_s, dur_s, pitch, vel). Páruje note_on/off."""
    mf = mido.MidiFile(path)
    notes = []
    pending = {}                     # pitch -> [(onset, vel), ...] (stack pro repeated notes)
    t = 0.0
    for msg in mf:                   # merge stop, delty v sekundách
        t += msg.time
        if msg.type == "note_on" and msg.velocity > 0:
            pending.setdefault(msg.note, []).append((t, msg.velocity))
        elif msg.type == "note_off" or (msg.type == "note_on" and msg.velocity == 0):
            stack = pending.get(msg.note)
            if stack:
                onset, vel = stack.pop(0)
                notes.append(Note(onset, max(t - onset, 0.0), msg.note, vel))
    # dohraj viset zůstavší (chybějící note_off) jako krátké
    for pitch, stack in pending.items():
        for onset, vel in stack:
            notes.append(Note(onset, 0.1, pitch, vel))
    notes.sort()
    return notes


def onset_events(notes, merge=0.035):
    """Seskup note_ony znějící ~současně (do `merge` s) do jednoho úderu.

    Vrací list (čas, síla, polyfonie): síla = součet velocities, polyfonie =
    kolik tónů naráz. V jazz piánu jsou silné údery (LH akord, bas) dobré
    indikátory dob -> proto vážíme silou i počtem.
    """
    if not notes:
        return []
    ons = sorted((n.onset, n.vel) for n in notes)
    events = []
    cluster_t, cluster_v, cluster_n = ons[0][0], ons[0][1], 1
    for t, v in ons[1:]:
        if t - cluster_t <= merge:
            cluster_v += v
            cluster_n += 1
        else:
            events.append((cluster_t, cluster_v, cluster_n))
            cluster_t, cluster_v, cluster_n = t, v, 1
    events.append((cluster_t, cluster_v, cluster_n))
    return events


if __name__ == "__main__":
    import sys
    notes = load_notes(sys.argv[1])
    ev = onset_events(notes)
    dur = max(n.onset + n.dur for n in notes)
    print(f"not={len(notes)}  úderů={len(ev)}  délka={dur:.1f}s  "
          f"rozsah={min(n.pitch for n in notes)}–{max(n.pitch for n in notes)}")
