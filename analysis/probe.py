"""Empirická prověrka tvrzení z evans_melody_gen/SPEC.md."""
import os, sys, glob
HERE = os.path.dirname(__file__)
ROOT = os.path.join(HERE, "..", "concept", "evans_melody_gen")
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, ROOT)

from chords import load_notes, detect_chords, lab
from line_extraction import extract_melody, chord_segments_with_time, align_to_chords

DATA = os.path.join(ROOT, "data")
files = sorted(glob.glob(os.path.join(DATA, "be-slice*.mid")))

print("="*70)
print("1) PŘEHLED SOUBORŮ: noty, melodie, rozsah, délka")
print("="*70)
mel_by_file = {}
for f in files:
    notes = load_notes(f)
    mel = extract_melody(notes)
    mel_by_file[os.path.basename(f)] = mel
    end = max(o+d for o,d,p,v in notes)
    pitches = [p for o,d,p in mel]
    rng = f"{min(pitches)}-{max(pitches)}" if pitches else "-"
    print(f"  {os.path.basename(f):16s}  not={len(notes):4d}  mel={len(mel):3d}  "
          f"délka={end:6.1f} dob  rozsah_mel={rng}")

print()
print("="*70)
print("2) JSOU 'DUPLIKÁTY' OPRAVDU TOTOŽNÉ? (shoda pitch-sekvence melodie)")
print("="*70)
groups = {
    "I Hear a Rhapsody": ["01","08"],
    "Nardis":            ["02","09","16"],
    "Emily":             ["03","10","17"],
    "Young and Foolish": ["04","11","18"],
    "Falling Grace":     ["05","12"],
    "Invitation":        ["06","13"],
    "Tenderly":          ["07","14","20"],
}
def pitchseq(mel): return [p for o,d,p in mel]
def overlap(a, b):
    # nejdelší shodný úsek jako hrubá míra: podíl shodných tonů v zarovnání od 0
    n = min(len(a), len(b))
    if n == 0: return 0.0
    same = sum(1 for i in range(n) if a[i] == b[i])
    return same / n
for song, ids in groups.items():
    names = [f"be-slice{i}.mid" for i in ids if f"be-slice{i}.mid" in mel_by_file]
    seqs = [pitchseq(mel_by_file[n]) for n in names]
    print(f"  {song:18s} verze={ids}  délky_mel={[len(s) for s in seqs]}")
    for i in range(len(seqs)):
        for j in range(i+1, len(seqs)):
            print(f"      {names[i]} vs {names[j]}: shoda od začátku = {overlap(seqs[i],seqs[j])*100:4.0f}%")

print()
print("="*70)
print("3) ZAROVNÁNÍ MELODIE K AKORDŮM: uniformní rozprostření vs realita")
print("="*70)
f = os.path.join(DATA, "be-slice03.mid")  # Emily
notes = load_notes(f)
merged = detect_chords(notes)
end = max(o+d for o,d,p,v in notes)
print(f"  Emily (be-slice03): {len(merged)} akordů, skladba {end:.1f} dob")
print(f"  detekovaná progrese: " + " -> ".join(lab(r,q) for r,q,pr in merged))
# co dělá chord_segments_with_time: rovnoměrné rozprostření
segs = chord_segments_with_time(notes)
print(f"  uniformní seglen = {end/len(merged):.2f} dob na akord (každý akord stejně dlouhý)")
print("  -> reálné akordy ale stejně dlouhé NEJSOU. Uniformní dělení = chybné labely.")

print()
print("="*70)
print("4) MÁ VYGENEROVANÁ LINKA RYTMUS? (analýza výstupního MIDI)")
print("="*70)
import mido
out = os.path.join(ROOT, "outputs", "demo_variation_2_t0.9.mid")
mid = mido.MidiFile(out)
for tr in mid.tracks:
    name = ""
    durs = []
    pitches = []
    t = 0; active = {}
    for m in tr:
        t += m.time
        if m.type == 'track_name': name = m.name
        if m.type == 'note_on' and m.velocity > 0:
            active[m.note] = t; pitches.append(m.note)
        elif m.type in ('note_off',) or (m.type=='note_on' and m.velocity==0):
            if m.note in active: durs.append(t - active.pop(m.note))
    if name == 'RH variation' and durs:
        uniq = sorted(set(durs))
        print(f"  RH: {len(pitches)} tónů, rozsah pitch {min(pitches)}-{max(pitches)}")
        print(f"  unikátní délky not (ticks): {uniq}  -> {len(uniq)} různá trvání")
        print(f"  unikátních pitchů: {len(set(pitches))}")
        # rozteče onsetů
        print("  pitch contour (prvních 24):", pitches[:24])
