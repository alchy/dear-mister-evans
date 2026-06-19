"""
nn_baseline.py -- SKELETON malé neuronové sítě (LSTM) pro melodické variace.

POZOR: tohle je kostra k dopracování, ne hotový model. Pusť ji AŽ když ti
Markovův baseline (markov.py) ukáže, že úloha dává smysl. Na 7 skladbách hrozí
overfitting — proto je tu povinná augmentace transpozicí do 12 tónin.

Závislost navíc: pip install torch

Hlavní myšlenky (viz SPEC.md kap. 4):
  - vstup do sítě = sekvence tokenů (degree vůči kořeni akordu) + kontext akordu,
  - augmentace: každou skladbu transponuj do všech 12 tónin (12x víc dat),
  - malý model (1-2 vrstvy LSTM, hidden ~64-128), dropout, early stopping,
  - generování = autoregresivně, sampling s teplotou / top-k,
  - výstup omez na akordovou stupnici (rámec z evans_drill), ať to vždy sedí.

Tokenizace (návrh):
  vstupní vektor na krok = one-hot(degree 0..11) ++ one-hot(quality)
  cíl = degree dalšího tónu (0..11)
"""
import os, sys, glob
sys.path.insert(0, os.path.dirname(__file__))
from chords import load_notes, detect_chords, lab
from line_extraction import extract_melody, chord_segments_with_time, align_to_chords

QUALITIES = ['maj','min','7','maj7','m7','m7b5','dim7','mMaj7','aug','sus','6','m6']
Q2I = {q: i for i, q in enumerate(QUALITIES)}


def build_dataset(data_glob, one_per_song=True, transpose_all_keys=True):
    """
    Vrátí seznam sekvencí, každá = list (degree, quality_index).
    transpose_all_keys: augmentace -- degree je vůči kořeni, takže transpozice
    se realizuje implicitně (degree je invariantní); augmentaci tu řešíme tím,
    že při tréninku můžeš sekvence brát beze změny (degree už je transpozičně
    nezávislý). Pokud bys modeloval i absolutní výšky, transponuj tady.
    """
    files = sorted(glob.glob(data_glob))
    if one_per_song:
        keep = {"01","02","03","04","05","06","07"}
        files = [f for f in files if any(f.endswith(f"be-slice{k}.mid") for k in keep)]
    seqs = []
    for f in files:
        try:
            notes = load_notes(f)
            mel = extract_melody(notes)
            segs = chord_segments_with_time(notes)
            aligned = align_to_chords(mel, segs)
            seq = [((p - r) % 12, Q2I.get(q, 0)) for (o, d, p, r, q) in aligned]
            if len(seq) > 8:
                seqs.append(seq)
        except Exception as e:
            print(f"  preskakuji {f}: {e}")
    return seqs


# ---------------------------------------------------------------------------
# Níže je kostra modelu. Odkomentuj a doplň, až budeš mít torch a chuť.
# ---------------------------------------------------------------------------
SKELETON = r'''
import torch, torch.nn as nn

class MelodyLSTM(nn.Module):
    def __init__(self, n_deg=12, n_qual=12, emb=32, hidden=96, layers=1, dropout=0.3):
        super().__init__()
        self.deg_emb = nn.Embedding(n_deg, emb)
        self.qual_emb = nn.Embedding(n_qual, emb)
        self.lstm = nn.LSTM(emb*2, hidden, layers, batch_first=True, dropout=dropout)
        self.out = nn.Linear(hidden, n_deg)
    def forward(self, deg, qual, h=None):
        x = torch.cat([self.deg_emb(deg), self.qual_emb(qual)], dim=-1)
        y, h = self.lstm(x, h)
        return self.out(y), h

def train(seqs, epochs=200, lr=1e-3):
    model = MelodyLSTM()
    opt = torch.optim.Adam(model.parameters(), lr=lr)
    lossf = nn.CrossEntropyLoss()
    # POZOR: 7 sekvencí je málo -> drž validaci, early stopping, malý model.
    for ep in range(epochs):
        total = 0
        for seq in seqs:
            deg = torch.tensor([[s[0] for s in seq]])
            qual = torch.tensor([[s[1] for s in seq]])
            logits, _ = model(deg[:, :-1], qual[:, :-1])
            loss = lossf(logits.reshape(-1, 12), deg[0, 1:])
            opt.zero_grad(); loss.backward(); opt.step()
            total += loss.item()
        if ep % 20 == 0:
            print(ep, total/len(seqs))
    return model

@torch.no_grad()
def generate(model, progression, steps_per_chord=8, temperature=0.9):
    # progression = [(root, quality), ...]; vrať degrees, převeď na MIDI venku
    import torch.nn.functional as F
    deg = torch.tensor([[0]]); h = None; out = []
    for (r, q) in progression:
        qi = Q2I.get(q, 0)
        for _ in range(steps_per_chord):
            qual = torch.tensor([[qi]])
            logits, h = model(deg, qual, h)
            probs = F.softmax(logits[0, -1] / temperature, dim=-1)
            nxt = torch.multinomial(probs, 1).item()
            out.append((nxt, r, q))    # degree vůči kořeni r
            deg = torch.tensor([[nxt]])
    return out
'''

if __name__ == "__main__":
    here = os.path.dirname(__file__)
    data_glob = os.path.join(here, "..", "data", "be-slice*.mid")
    seqs = build_dataset(data_glob)
    print(f"dataset: {len(seqs)} sekvencí, "
          f"{sum(len(s) for s in seqs)} tónů celkem (degree, quality)")
    print("ukázka prvních 15 tokenů první sekvence:")
    print(seqs[0][:15] if seqs else "—")
    print("\nKostra modelu je v proměnné SKELETON v tomto souboru.")
    print("Pro trénink: nainstaluj torch, vlož kostru a zavolej train(seqs).")
    print("Ale nejdřív vyzkoušej markov.py -- na těchto datech bude nejspíš lepší.")
