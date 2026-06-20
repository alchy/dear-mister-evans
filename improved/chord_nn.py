#!/usr/bin/env python3
"""
chord_nn.py -- malá LSTM neuronka pro akordové progrese (KROK 2, experiment).

Stejná key-relativní reprezentace jako chord_markov.py (aby byly srovnatelné),
ale model je rekurentní -> může zachytit DELŠÍ strukturu než Markov (n-gram vidí
jen pár předchozích akordů). Mód (dur/moll) je podmínka přes start-token.

POZOR: ~40 skladeb je MÁLO -> riziko memorizace. Proto: malý model, dropout,
early stopping na validaci. Bereme to jako experiment vedle Markova.

Závislost navíc:  pip install torch  (CPU stačí)

Použití:
    python improved/chord_nn.py --key C --mode maj --bars 16 --render out.mid
    python improved/chord_nn.py --key A --mode min --temp 1.1 --epochs 400
"""
import os, sys, argparse
HERE = os.path.dirname(__file__)
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "concept", "evans_melody_gen"))

import torch
import torch.nn as nn
import torch.nn.functional as F

import chord_markov as cm   # build_corpus, to_prog, to_symbols, roman, render, PC, DEG, DEFAULT_DATA

PAD, BOS_MAJ, BOS_MIN, EOS = 0, 1, 2, 3
SPECIALS = ['<pad>', '<bos_maj>', '<bos_min>', '<eos>']


def build_vocab(seqs):
    toks = set()
    for _, ts in seqs:
        toks.update(ts)
    vocab = SPECIALS + sorted(toks)
    return vocab, {t: i for i, t in enumerate(vocab)}


def encode(seqs, tok2id):
    out = []
    for mode, ts in seqs:
        bos = BOS_MAJ if mode == 'maj' else BOS_MIN
        out.append([bos] + [tok2id[t] for t in ts] + [EOS])
    return out


class ChordLSTM(nn.Module):
    def __init__(self, V, emb=48, hid=96, layers=1, dropout=0.3):
        super().__init__()
        self.emb = nn.Embedding(V, emb, padding_idx=PAD)
        self.drop = nn.Dropout(dropout)
        self.lstm = nn.LSTM(emb, hid, layers, batch_first=True,
                            dropout=dropout if layers > 1 else 0.0)
        self.out = nn.Linear(hid, V)

    def forward(self, x, h=None):
        e = self.drop(self.emb(x))
        y, h = self.lstm(e, h)
        return self.out(self.drop(y)), h


def train_model(encoded, V, epochs=400, seed=0, verbose=True):
    torch.manual_seed(seed)
    maxlen = max(len(s) for s in encoded)
    X = torch.full((len(encoded), maxlen), PAD, dtype=torch.long)
    for i, s in enumerate(encoded):
        X[i, :len(s)] = torch.tensor(s)
    # split train/val
    g = torch.Generator().manual_seed(seed)
    perm = torch.randperm(len(encoded), generator=g)
    nval = max(4, len(encoded) // 6)
    val_idx, tr_idx = perm[:nval], perm[nval:]
    model = ChordLSTM(V)
    opt = torch.optim.Adam(model.parameters(), lr=3e-3, weight_decay=1e-4)
    lossf = nn.CrossEntropyLoss(ignore_index=PAD)

    def run(idx, train):
        x = X[idx]
        inp, tgt = x[:, :-1], x[:, 1:]
        model.train(train)
        with torch.set_grad_enabled(train):
            logits, _ = model(inp)
            loss = lossf(logits.reshape(-1, V), tgt.reshape(-1))
            if train:
                opt.zero_grad(); loss.backward(); opt.step()
        return loss.item()

    best, best_state, patience, since = 1e9, None, 50, 0
    for ep in range(epochs):
        tr = run(tr_idx, True)
        vl = run(val_idx, False)
        if vl < best - 1e-3:
            best, best_state, since = vl, {k: v.clone() for k, v in model.state_dict().items()}, 0
        else:
            since += 1
        if verbose and ep % 50 == 0:
            print(f"  epoch {ep:4d}  train {tr:.3f}  val {vl:.3f}")
        if since >= patience:
            if verbose: print(f"  early stop @ {ep} (val {best:.3f})")
            break
    if best_state:
        model.load_state_dict(best_state)
    return model


@torch.no_grad()
def generate(model, vocab, mode, bars=16, temperature=1.0, seed=None):
    if seed is not None:
        torch.manual_seed(seed)
    model.eval()
    bos = BOS_MAJ if mode == 'maj' else BOS_MIN
    inp = torch.tensor([[bos]]); h = None
    toks = []
    for _ in range(bars):
        logits, h = model(inp, h)
        lg = logits[0, -1].clone()
        lg[PAD] = lg[BOS_MAJ] = lg[BOS_MIN] = -1e9     # zakázané tokeny
        probs = F.softmax(lg / max(1e-6, temperature), dim=-1)
        nxt = int(torch.multinomial(probs, 1))
        if nxt == EOS:
            break
        toks.append(vocab[nxt])
        inp = torch.tensor([[nxt]])
    return toks


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--key", default="C")
    ap.add_argument("--mode", default="maj", choices=["maj", "min"])
    ap.add_argument("--bars", type=int, default=16)
    ap.add_argument("--temp", type=float, default=1.0)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--epochs", type=int, default=400)
    ap.add_argument("--data", default=cm.DEFAULT_DATA)
    ap.add_argument("--render", default=None)
    ap.add_argument("--bpm", type=int, default=110)
    a = ap.parse_args()

    print("== korpus ==")
    seqs = cm.build_corpus(a.data)
    vocab, tok2id = build_vocab(seqs)
    print(f"  {len(seqs)} skladeb | slovník {len(vocab)} tokenů")
    print("== trénink LSTM ==")
    model = train_model(encode(seqs, tok2id), len(vocab), epochs=a.epochs, seed=a.seed)

    toks = generate(model, vocab, a.mode, bars=a.bars, temperature=a.temp, seed=a.seed + 1)
    if not toks:
        toks = [(0, 'maj7' if a.mode == 'maj' else 'm7')]
    toks[-1] = (0, 'maj7' if a.mode == 'maj' else 'm7')   # čistá kadence
    key_root = cm.PC.index(a.key) if a.key in cm.PC else 0
    prog = cm.to_prog(toks, key_root)
    print(f"\ntónina: {a.key} {a.mode} | teplota {a.temp}")
    print("stupně:  " + " ".join(f"{cm.DEG[r]}{q}" for r, q in toks))
    print("akordy:  " + " | ".join(cm.to_symbols(prog)))
    if a.render:
        cm.render(prog, a.render, bpm=a.bpm, seed=a.seed + 1)
        print(f"aranž -> {a.render}")
