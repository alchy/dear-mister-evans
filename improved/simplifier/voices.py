"""voices -- rozdělení faktury na MELODII (top voice) a HARMONII (spodek).

Klíč k akordům (díky J.): na akord ber jen SPODEK, ne vršek. Vršek = melodie
(řeší se zvlášť pro lick), spodek = levá ruka + bas = harmonie. Navíc akord drží
většinou DÝL než průběžná melodie -> chroma se pak váží trváním.

Skyline: událostmi řízený průchod; v každém intervalu mezi onsety/offsety je
aktivní množina konstantní, nejvyšší znějící tón = melodie. Nota je melodie,
když je „nahoře" víc než půlku svého trvání.
"""


def skyline_split(notes, frac=0.5):
    """-> (melody, harmony): list Note. Melody = tóny, co jsou většinu času nahoře."""
    if not notes:
        return [], []
    evs = []
    for i, n in enumerate(notes):
        evs.append((n.onset, 1, i))
        evs.append((n.onset + n.dur, 0, i))
    evs.sort()
    active = set()
    top_time = [0.0] * len(notes)
    prev = evs[0][0]
    for t, typ, i in evs:
        dt = t - prev
        if dt > 0 and active:
            top = max(active, key=lambda k: notes[k].pitch)
            top_time[top] += dt
        if typ == 1:
            active.add(i)
        else:
            active.discard(i)
        prev = t
    melody, harmony = [], []
    for i, n in enumerate(notes):
        (melody if top_time[i] > frac * max(n.dur, 1e-6) else harmony).append(n)
    return melody, harmony


if __name__ == "__main__":
    import sys
    from . import io_midi
    notes = io_midi.load_notes(sys.argv[1])
    mel, har = skyline_split(notes)
    print(f"not={len(notes)} -> melodie={len(mel)} harmonie={len(har)}")
    if mel and har:
        print(f"  medián výšky: melodie={sorted(n.pitch for n in mel)[len(mel)//2]}  "
              f"harmonie={sorted(n.pitch for n in har)[len(har)//2]}")
