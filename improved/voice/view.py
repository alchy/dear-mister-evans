"""view -- anotovaný klaviaturní náhled (tabule), věrný port prototypu.

Per akord (řádek) DVĚ klaviatury:
  VLEVO  = levá ruka (bas + voicing) -- číslované body = řazení/stavba, + čáry
           voice-leadingu mezi akordy (jak se ruka přesouvá).
  VPRAVO = melodie -- kolečka s číslem (pořadí hraní), kreslená „dráhovým schodištěm"
           (patro výš při opakování tónu / změně směru; menší číslo nikdy nad větším).
Výukové anotace navíc: tóny stupnice (paleta, světle), guide tóny (3/7, zelený kroužek),
LANDING tón do dalšího akordu (▼). Zelená linka = indikace právě hraného řádku.
"""
import tkinter as tk

BLACK = {1, 3, 6, 8, 10}
WW, WH = 15, 48
LBL = 13
GAP = 16
ROW_H = LBL + WH + GAP
COL_GAP = 22
PAD = 6
DOTR = 7
BASS_LO, BASS_HI = 36, 64        # C2..E4 (bas + voicing)
MEL_LO, MEL_HI = 55, 88          # G3..E6 (melodie)
DOT_BASS = "#1f7ae0"
DOT_MEL = "#e8731e"
VL_LINE = "#1f7ae0"
BASS_LINE = "#bbbbbb"
_PC = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]


def whites(lo, m):
    return sum(1 for k in range(lo, m) if k % 12 not in BLACK)


def _mel_x0():
    return whites(BASS_LO, BASS_HI + 1) * WW + COL_GAP


def _kbd(cv, x0, ky, lo, hi):
    for m in range(lo, hi + 1):
        if m % 12 in BLACK:
            continue
        x = x0 + whites(lo, m) * WW
        cv.create_rectangle(x, ky, x + WW, ky + WH, fill="white", outline="#bbb")
        if m % 12 == 0:
            cv.create_text(x + WW / 2, ky + WH - 2, anchor="s", text=f"C{m//12-1}",
                           font=("Segoe UI", 6), fill="#ccc")
    for m in range(lo, hi + 1):
        if m % 12 not in BLACK:
            continue
        x = x0 + whites(lo, m) * WW - WW * 0.3
        cv.create_rectangle(x, ky, x + WW * 0.6, ky + WH * 0.6, fill="#333", outline="#000")


def _cx(x0, lo, hi, m):
    m = max(lo, min(hi, m))
    if m % 12 in BLACK:
        return x0 + whites(lo, m) * WW
    return x0 + whites(lo, m) * WW + WW / 2


def _dot(cv, x, y, r, **kw):
    cv.create_oval(x - r, y - r, x + r, y + r, **kw)


def _seq(cv, x0, ky, lo, hi, seq, color):
    """Číslovaná kolečka v pořadí hraní. Dráhové schodiště: drží patro během
    směrového běhu; při OPAKOVÁNÍ tónu nebo ZMĚNĚ SMĚRU patro výš (jen nahoru ->
    menší číslo není nikdy nad větším)."""
    STEP, MAXL = 12, 3
    base = ky + WH - 10
    level, prevdir = 0, 0
    for i, p in enumerate(seq):
        if i > 0:
            prev = seq[i - 1]
            d = (p > prev) - (p < prev)
            if p == prev or (d != 0 and prevdir != 0 and d != prevdir):
                level = min(MAXL, level + 1)
            if d != 0:
                prevdir = d
        cx = _cx(x0, lo, hi, p)
        cy = base - level * STEP
        _dot(cv, cx, cy, DOTR, fill=color, outline="#333")
        cv.create_text(cx, cy, text=str(i + 1), fill="white", font=("Segoe UI", 7, "bold"))


def _by_bar(line, n):
    out = [[] for _ in range(n)]
    for onset, dur, p in line:
        bi = int(onset // 4.0)
        if 0 <= bi < n:
            out[bi].append(p)
    return out


def _sym(bar):
    return _PC[bar.root % 12] + bar.quality


def draw(cv, harmony, landings, line=None):
    cv.delete("all")
    bars = harmony.bars
    mel = _by_bar(line, len(bars)) if line else None
    mx0 = _mel_x0()
    for i, bar in enumerate(bars):
        y0 = PAD + i * ROW_H
        ky = y0 + LBL
        cv.create_text(2, y0, anchor="nw", text=f"{_sym(bar)}  ·  {bar.scale_name}",
                       font=("Segoe UI", 8, "bold"), fill="#234")
        _kbd(cv, 0, ky, BASS_LO, BASS_HI)
        _kbd(cv, mx0, ky, MEL_LO, MEL_HI)
        baseM = ky + WH - 4
        for p in bar.scale:                                   # 2) tóny stupnice (paleta)
            if MEL_LO <= p <= MEL_HI:
                _dot(cv, _cx(mx0, MEL_LO, MEL_HI, p), baseM, 2.5, fill="#bfe3c0", outline="")
        for p in bar.guides:                                  # guide tóny (3/7)
            if MEL_LO <= p <= MEL_HI:
                _dot(cv, _cx(mx0, MEL_LO, MEL_HI, p), baseM, 5, outline="#2a9d3a", width=2, fill="")
        cv.create_text(_cx(mx0, MEL_LO, MEL_HI, landings[i]), ky - 1, text="▼",   # 3) landing
                       fill="#e23030", font=("Segoe UI", 10, "bold"))
    # 1) čáry voice-leadingu mezi sousedními voicingy (levá ruka)
    for i in range(len(bars) - 1):
        yb = PAD + i * ROW_H + LBL + WH
        yt = PAD + (i + 1) * ROW_H + LBL
        a = sorted([bars[i].bass] + list(bars[i].voicing))
        b = sorted([bars[i + 1].bass] + list(bars[i + 1].voicing))
        for ma, mb in zip(a, b):
            cv.create_line(_cx(0, BASS_LO, BASS_HI, ma), yb,
                           _cx(0, BASS_LO, BASS_HI, mb), yt, fill=VL_LINE, width=1)
    # číslovaná kolečka navrch: vlevo voicing (řazení), vpravo melodie
    for i, bar in enumerate(bars):
        ky = PAD + i * ROW_H + LBL
        _seq(cv, 0, ky, BASS_LO, BASS_HI, [bar.bass] + sorted(bar.voicing), DOT_BASS)
        if mel:
            _seq(cv, mx0, ky, MEL_LO, MEL_HI, mel[i], DOT_MEL)
    total_w = mx0 + whites(MEL_LO, MEL_HI + 1) * WW + 6
    cv.config(scrollregion=(0, 0, total_w, PAD + len(bars) * ROW_H + 6))


def set_playing(cv, row, n_bars):
    """Zelená linka pod právě hraným řádkem (obě klaviatury). row=None zhasne."""
    cv.delete("playline")
    if row is None or not (0 <= row < n_bars):
        return
    y = PAD + row * ROW_H + LBL + WH + 2
    x1 = _mel_x0() + whites(MEL_LO, MEL_HI + 1) * WW
    cv.create_line(0, y, x1, y, fill="#10c040", width=3, tags="playline")
