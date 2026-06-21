"""view -- anotovaný klaviaturní náhled (tabule), ŠKÁLOVATELNÝ podle šířky okna.

Per akord (řádek) DVĚ klaviatury:
  VLEVO  = levá ruka (bas + voicing) -- číslovaná kolečka (řazení/stavba) + čáry
           voice-leadingu mezi akordy.
  VPRAVO = melodie -- kolečka s číslem (pořadí), dráhové schodiště (patro výš při
           opakování/změně směru; menší číslo nikdy nad větším).
Anotace: tóny stupnice (paleta), guide tóny (3/7 kroužek), LANDING tón (▼).
Zelená linka = právě hraný řádek. Velikost kláves se počítá z šířky plátna -> škáluje.
"""
from types import SimpleNamespace

BLACK = {1, 3, 6, 8, 10}
PAD = 6
MAXL = 3
BASS_LO, BASS_HI = 36, 64        # C2..E4 (bas + voicing)
MEL_LO, MEL_HI = 55, 88          # G3..E6 (melodie)
DOT_BASS = "#1f7ae0"
DOT_MEL = "#e8731e"
VL_LINE = "#1f7ae0"
_PC = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]


def whites(lo, m):
    return sum(1 for k in range(lo, m) if k % 12 not in BLACK)


def _geom(width):
    """Spočti rozměry kláves z dostupné šířky plátna -> škálování oknem."""
    bw = whites(BASS_LO, BASS_HI + 1)
    mw = whites(MEL_LO, MEL_HI + 1)
    avail = max(420, width - 2 * PAD - 18)          # rezerva na scrollbar
    ww = min(34.0, max(10.0, avail / (bw + mw + 1.8)))   # 1.8 bílých na mezeru
    g = SimpleNamespace()
    g.WW = ww
    g.WH = ww * 3.05
    g.COL_GAP = ww * 1.8
    g.DOTR = max(6.0, ww * 0.46)
    g.STEP = ww * 0.74
    g.LBL = 16                                       # pevné pásmo popisku (font neškáluje)
    g.GAP = ww * 0.85
    g.ROW_H = g.LBL + g.WH + g.GAP
    g.mel_x0 = bw * ww + g.COL_GAP
    g.fnum = max(7, int(ww * 0.5))                   # čísla koleček škálují s klávesami
    g.flbl = 9                                       # popisek akord·stupnice = PEVNÝ font (nepřekrývá)
    return g


def _kbd(cv, g, x0, ky, lo, hi):
    for m in range(lo, hi + 1):
        if m % 12 in BLACK:
            continue
        x = x0 + whites(lo, m) * g.WW
        cv.create_rectangle(x, ky, x + g.WW, ky + g.WH, fill="white", outline="#bbb")
        if m % 12 == 0:
            cv.create_text(x + g.WW / 2, ky + g.WH - 2, anchor="s", text=f"C{m//12-1}",
                           font=("Segoe UI", 6), fill="#ccc")
    for m in range(lo, hi + 1):
        if m % 12 not in BLACK:
            continue
        x = x0 + whites(lo, m) * g.WW - g.WW * 0.3
        cv.create_rectangle(x, ky, x + g.WW * 0.6, ky + g.WH * 0.6, fill="#333", outline="#000")


def _cx(g, x0, lo, hi, m):
    m = max(lo, min(hi, m))
    if m % 12 in BLACK:
        return x0 + whites(lo, m) * g.WW
    return x0 + whites(lo, m) * g.WW + g.WW / 2


def _dot(cv, x, y, r, **kw):
    cv.create_oval(x - r, y - r, x + r, y + r, **kw)


def _seq(cv, g, x0, ky, lo, hi, seq, color):
    base = ky + g.WH - g.WW * 0.6
    level, prevdir = 0, 0
    for i, p in enumerate(seq):
        if i > 0:
            prev = seq[i - 1]
            d = (p > prev) - (p < prev)
            if p == prev or (d != 0 and prevdir != 0 and d != prevdir):
                level = min(MAXL, level + 1)
            if d != 0:
                prevdir = d
        cx = _cx(g, x0, lo, hi, p)
        cy = base - level * g.STEP
        _dot(cv, cx, cy, g.DOTR, fill=color, outline="#333")
        cv.create_text(cx, cy, text=str(i + 1), fill="white", font=("Segoe UI", g.fnum, "bold"))


def _by_bar(line, n):
    out = [[] for _ in range(n)]
    for onset, dur, p in line:
        bi = int(onset // 4.0)
        if 0 <= bi < n:
            out[bi].append(p)
    return out


def _sym(bar):
    return _PC[bar.root % 12] + bar.quality


def draw(cv, harmony, landings, line=None, width=None, flip=False):
    cv.delete("all")
    g = _geom(width if width is not None else cv.winfo_width())
    bars = harmony.bars
    n = len(bars)
    mel = _by_bar(line, n) if line else None

    def y0_of(i):                                             # vrch řádku datového akordu i
        s = (n - 1 - i) if flip else i                        # flip = zdola nahoru
        return PAD + s * g.ROW_H

    for i, bar in enumerate(bars):
        y0 = y0_of(i)
        ky = y0 + g.LBL
        cv.create_text(2, y0, anchor="nw", text=f"{_sym(bar)}  ·  {bar.scale_name}",
                       font=("Segoe UI", g.flbl, "bold"), fill="#234")
        _kbd(cv, g, 0, ky, BASS_LO, BASS_HI)
        _kbd(cv, g, g.mel_x0, ky, MEL_LO, MEL_HI)
        baseM = ky + g.WH - 4
        for p in bar.scale:                                   # 2) tóny stupnice (paleta)
            if MEL_LO <= p <= MEL_HI:
                _dot(cv, _cx(g, g.mel_x0, MEL_LO, MEL_HI, p), baseM, g.DOTR * 0.4, fill="#bfe3c0", outline="")
        for p in bar.guides:                                  # guide tóny (3/7)
            if MEL_LO <= p <= MEL_HI:
                _dot(cv, _cx(g, g.mel_x0, MEL_LO, MEL_HI, p), baseM, g.DOTR * 0.7,
                     outline="#2a9d3a", width=2, fill="")
        cv.create_text(_cx(g, g.mel_x0, MEL_LO, MEL_HI, landings[i]), ky - 1, text="▼",   # 3) landing
                       fill="#e23030", font=("Segoe UI", max(10, g.fnum + 2), "bold"))
    # 1) čáry voice-leadingu mezi sousedními voicingy (dle skutečných slotů)
    for i in range(n - 1):
        kyi = y0_of(i) + g.LBL
        kyj = y0_of(i + 1) + g.LBL
        yb, yt = (kyi + g.WH, kyj) if kyj > kyi else (kyi, kyj + g.WH)   # hrana blíž sousedovi
        a = sorted([bars[i].bass] + list(bars[i].voicing))
        b = sorted([bars[i + 1].bass] + list(bars[i + 1].voicing))
        for ma, mb in zip(a, b):
            cv.create_line(_cx(g, 0, BASS_LO, BASS_HI, ma), yb,
                           _cx(g, 0, BASS_LO, BASS_HI, mb), yt, fill=VL_LINE, width=1)
    # číslovaná kolečka navrch
    for i, bar in enumerate(bars):
        ky = y0_of(i) + g.LBL
        _seq(cv, g, 0, ky, BASS_LO, BASS_HI, [bar.bass] + sorted(bar.voicing), DOT_BASS)
        if mel:
            _seq(cv, g, g.mel_x0, ky, MEL_LO, MEL_HI, mel[i], DOT_MEL)
    total_w = g.mel_x0 + whites(MEL_LO, MEL_HI + 1) * g.WW + 6
    cv.config(scrollregion=(0, 0, total_w, PAD + n * g.ROW_H + 6))


def set_playing(cv, row, n_bars, width=None, flip=False):
    """Zelená linka pod právě hraným řádkem (respektuje flip). row=None zhasne."""
    cv.delete("playline")
    if row is None or not (0 <= row < n_bars):
        return
    g = _geom(width if width is not None else cv.winfo_width())
    s = (n_bars - 1 - row) if flip else row
    y = PAD + s * g.ROW_H + g.LBL + g.WH + 2
    x1 = g.mel_x0 + whites(MEL_LO, MEL_HI + 1) * g.WW
    cv.create_line(0, y, x1, y, fill="#10c040", width=3, tags="playline")


def hit(cv, x, y, n_bars, width=None, flip=False):
    """Klik (canvas coords) -> (data_row, side) kde side='chord' (levá klávesnice)
    nebo 'line' (pravá). Mimo klávesy vrátí None. Respektuje flip."""
    g = _geom(width if width is not None else cv.winfo_width())
    slot = int((y - PAD) // g.ROW_H)
    if not (0 <= slot < n_bars):
        return None
    ky = PAD + slot * g.ROW_H + g.LBL
    if not (ky <= y <= ky + g.WH):
        return None
    row = (n_bars - 1 - slot) if flip else slot
    bass_w = whites(BASS_LO, BASS_HI + 1) * g.WW
    mel_w = whites(MEL_LO, MEL_HI + 1) * g.WW
    if x <= bass_w:
        return (row, "chord")
    if g.mel_x0 <= x <= g.mel_x0 + mel_w:
        return (row, "line")
    return None
