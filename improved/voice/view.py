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
ROOT_YEL = "#f0c020"        # naznačený (vynechaný) root u rootless voicingu -- žlutě, bez čísla
_PC = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]


def whites(lo, m):
    return sum(1 for k in range(lo, m) if k % 12 not in BLACK)


def _bass_range(harmony):
    """Bas klaviatura: STATICKÁ základna [36, 72] (C2-C5) -> u běžných voicingů (root,
    root_vl, rootless, cluster) je klaviatura stále stejná. Roste JEN když se LH tóny
    nevejdou (extrémně široké drop2&4) -> klouže/roste jen v extrémech, jinak statická."""
    lh = [p for b in harmony.bars for p in [b.bass] + list(b.voicing)]
    if not lh:
        return 36, 72
    mn, mx = min(lh), max(lh)
    lo = 36 if mn >= 36 else mn - 1                # snap na 36; níž jen při přetečení
    hi = 72 if mx <= 72 else mx + 1                # snap na 72; výš jen při přetečení
    return max(24, lo), min(100, hi)


def _geom(width, bass_lo, bass_hi):
    """Rozměry kláves z dostupné šířky plátna (škálování oknem) + dynamický rozsah basu."""
    bw = whites(bass_lo, bass_hi + 1)
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
    g.bass_lo, g.bass_hi = bass_lo, bass_hi
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


def _seq_pos(g, x0, ky, lo, hi, seq):
    """Pozice (cx,cy) bublin v pořadí hraní -- dráhové schodiště. Řada (level) jde
    JEN NAHORU (monotónně): patro výš při opakování/změně směru A při přechodu
    BÍLÁ->ČERNÁ klapka (tón na černé tak sedí výš, na černé klapce). Černá->bílá
    zůstává na dosažené řadě. Vrací seznam pozic (kreslení dělá _dots)."""
    base = ky + g.WH - g.WW * 0.6
    level, prevdir = 0, 0
    prev_black = False                                 # "před začátkem" = bílá
    out = []
    for i, p in enumerate(seq):
        cur_black = (p % 12) in BLACK
        if i > 0:
            prev = seq[i - 1]
            d = (p > prev) - (p < prev)
            if p == prev or (d != 0 and prevdir != 0 and d != prevdir):
                level = min(MAXL, level + 1)
            if d != 0:
                prevdir = d
        if (not prev_black) and cur_black:             # bílá -> černá: o řadu výš (na černou)
            level = min(MAXL, level + 1)
        prev_black = cur_black
        out.append((_cx(g, x0, lo, hi, p), base - level * g.STEP))
    return out


def _dots(cv, g, pos, color):
    for i, (cx, cy) in enumerate(pos):
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
    blo, bhi = _bass_range(harmony)                          # bas klaviatura dle dat
    g = _geom(width if width is not None else cv.winfo_width(), blo, bhi)
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
        _kbd(cv, g, 0, ky, g.bass_lo, g.bass_hi)
        _kbd(cv, g, g.mel_x0, ky, MEL_LO, MEL_HI)
        baseM = ky + g.WH - 4
        for p in bar.scale:                                   # 2) tóny stupnice (paleta)
            if MEL_LO <= p <= MEL_HI:
                _dot(cv, _cx(g, g.mel_x0, MEL_LO, MEL_HI, p), baseM, g.DOTR * 0.4, fill="#bfe3c0", outline="")
        for p in bar.guides:                                  # guide tóny (3/7)
            if MEL_LO <= p <= MEL_HI:
                _dot(cv, _cx(g, g.mel_x0, MEL_LO, MEL_HI, p), baseM, g.DOTR * 0.7,
                     outline="#2a9d3a", width=2, fill="")
        lx = _cx(g, g.mel_x0, MEL_LO, MEL_HI, landings[i])               # 3) landing značka
        af = max(10, g.fnum + 2)
        cv.create_text(lx, ky - 1, text=("▲" if flip else "▼"),  # ukazuje k řádku dalšího akordu
                       fill="#e23030", font=("Segoe UI", af, "bold"))
        nxt = bars[(i + 1) % n]                                           # akord, do kterého se míří
        iv = (landings[i] - nxt.root) % 12                               # guide tón = 3 nebo 7 cíle
        deg = "3" if iv in (3, 4) else "7" if iv in (9, 10, 11) else "?"
        cv.create_text(lx, ky - 1 - af, anchor="s",                     # popisek NAD šipkou (mimo klávesy)
                       text=f"{_PC[landings[i] % 12]} ({deg}·{_sym(nxt)})",
                       fill="#e23030", font=("Segoe UI", g.flbl, "bold"))
    # 1) levá ruka (DRY): BAS (root) VŽDY žlutě BEZ čísla; číslují se jen tóny voicingu.
    lh = [_seq_pos(g, 0, y0_of(i) + g.LBL, g.bass_lo, g.bass_hi, sorted(bar.voicing))
          for i, bar in enumerate(bars)]
    # čáry voice-leadingu MEZI BUBLINAMI voicingu (k-tý hlas akordu i -> k-tý hlas i+1)
    for i in range(n - 1):
        a, b = lh[i], lh[i + 1]
        for k in range(min(len(a), len(b))):
            cv.create_line(a[k][0], a[k][1], b[k][0], b[k][1], fill=VL_LINE, width=2)
    # melodie: pozice koleček (spočti jednou -> pro spojnici i kreslení)
    mel_pos = [_seq_pos(g, g.mel_x0, y0_of(i) + g.LBL, MEL_LO, MEL_HI, mel[i]) if mel else []
               for i in range(n)]
    # LANDING-šipka: POSLEDNÍ (approach) tón taktu i -> PRVNÍ (landing) tón taktu i+1.
    # Krátká, v mezeře mezi řádky; hrot u landing noty -> jasně směrová a otáčí se s flipem.
    if mel:
        for i in range(n - 1):
            if mel_pos[i] and mel_pos[i + 1]:
                fx, fy = mel_pos[i][-1]
                tx, ty = mel_pos[i + 1][0]
                cv.create_line(fx, fy, tx, ty, fill="#e23030", width=1, dash=(3, 2),
                               arrow="last")
    # kolečka navrch: žlutý naznačený bas/root (bez čísla) + číslované tóny voicingu + melodie
    for i, bar in enumerate(bars):
        bx, by = _seq_pos(g, 0, y0_of(i) + g.LBL, g.bass_lo, g.bass_hi, [bar.bass])[0]
        _dot(cv, bx, by, g.DOTR, fill=ROOT_YEL, outline="#a80")
        _dots(cv, g, lh[i], DOT_BASS)
        if mel_pos[i]:
            _dots(cv, g, mel_pos[i], DOT_MEL)
    total_w = g.mel_x0 + whites(MEL_LO, MEL_HI + 1) * g.WW + 6
    cv.config(scrollregion=(0, 0, total_w, PAD + n * g.ROW_H + 6))
    return (blo, bhi)                                        # bas-rozsah pro hit/set_playing


def set_playing(cv, row, n_bars, bass_range, width=None, flip=False):
    """Zelená linka pod právě hraným řádkem (respektuje flip). row=None zhasne."""
    cv.delete("playline")
    if row is None or not (0 <= row < n_bars):
        return
    g = _geom(width if width is not None else cv.winfo_width(), *bass_range)
    s = (n_bars - 1 - row) if flip else row
    y = PAD + s * g.ROW_H + g.LBL + g.WH + 2
    x1 = g.mel_x0 + whites(MEL_LO, MEL_HI + 1) * g.WW
    cv.create_line(0, y, x1, y, fill="#10c040", width=3, tags="playline")


def hit(cv, x, y, n_bars, bass_range, width=None, flip=False):
    """Klik (canvas coords) -> (data_row, side) kde side='chord' (levá klávesnice)
    nebo 'line' (pravá). Mimo klávesy vrátí None. Respektuje flip."""
    g = _geom(width if width is not None else cv.winfo_width(), *bass_range)
    slot = int((y - PAD) // g.ROW_H)
    if not (0 <= slot < n_bars):
        return None
    ky = PAD + slot * g.ROW_H + g.LBL
    if not (ky <= y <= ky + g.WH):
        return None
    row = (n_bars - 1 - slot) if flip else slot
    bass_w = whites(g.bass_lo, g.bass_hi + 1) * g.WW
    mel_w = whites(MEL_LO, MEL_HI + 1) * g.WW
    if x <= bass_w:
        return (row, "chord")
    if g.mel_x0 <= x <= g.mel_x0 + mel_w:
        return (row, "line")
    return None
