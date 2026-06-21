"""build -- builder linky CÍL + SPOJKA (Levinovsky, teorií řízený).

Linka se STAVÍ: na doby se kladou CÍLE = akordové tóny (1. doba = guide tón,
voice-led), mezi ně přijdou SPOJKY (chromatický approach na offbeaty -> rozvod na
cíl na další době). Do dalšího taktu se přijde půltónovým approachem na jeho guide
tón. Slovník je TEORETICKÝ (nezávislý na datech); Evans 'taste' je volitelný (zatím
nepoužit -> nespoléháme na prior). Viz LINE_DEVICES.md.
"""
import random

BPC = 4.0          # dob na takt
BEATS = 4


def _nearest(pool, ref):
    return min(pool, key=lambda p: abs(p - ref)) if pool else ref


def _next_chord_tone(ctones, cur, direction, rng):
    """Další akordový tón ve směru (voice-leading kontura); fallback nejbližší."""
    side = [p for p in ctones if (p - cur) * direction > 0]
    if side:
        return min(side, key=lambda p: abs(p - cur))
    return _nearest([p for p in ctones if p != cur] or ctones, cur)


def _approach(target, frm, scale, rng, chrom=0.7):
    """Approach tón na offbeatu -> rozvod na 'target'. Půltón ze strany 'frm'
    (chrom) nebo diatonicky (krok stupnice). Hraje se PŘED cílem."""
    below = frm <= target
    if rng.random() < chrom:
        return target - 1 if below else target + 1     # chromatický náběh
    # diatonický: sousední tón stupnice ze správné strany
    idx = min(range(len(scale)), key=lambda k: abs(scale[k] - target))
    j = max(0, idx - 1) if below else min(len(scale) - 1, idx + 1)
    return scale[j]


def _enc_upper(scale, target):
    """Horní obklíčení: nejbližší tón stupnice STRIKTNĚ nad cílem (fallback +2)."""
    above = [s for s in scale if s > target]
    return min(above) if above else target + 2


def _scale_between(scale, a, b, frac):
    """Tón stupnice mezi a a b v poměru frac (krokové vyplnění)."""
    ia = min(range(len(scale)), key=lambda k: abs(scale[k] - a))
    ib = min(range(len(scale)), key=lambda k: abs(scale[k] - b))
    j = int(round(ia + (ib - ia) * frac))
    return scale[max(0, min(len(scale) - 1, j))]


def guide_path(harmony):
    """Voice-led cesta guide tónů (vstup každého taktu). landing do dalšího akordu
    = vstup taktu i+1. Pro náhled-tabuli i pro builder (1. doba)."""
    entries = []; prev = harmony.center
    for bar in harmony.bars:
        e = _nearest(bar.guides or bar.scale, prev)
        entries.append(e); prev = e
    n = len(entries)
    landings = [entries[(i + 1) % n] for i in range(n)]
    return entries, landings


def generate(harmony, density=2, seed=1, approach=0.5, enclose=0.0, motion="arp", taste=None):
    """harmony = Harmony, density = not/dobu. Vrať [(onset, délka, MIDI)].
    DRILL se zaměřením na LANDING tóny: 1. doba = guide tón (voice-led), pak akordové
    arpeggio v JEDNOM směru přes takt (takty střídají klesající/stoupající -> jasný
    tvar, žádné bloudění), offbeaty = stupnicové spojení, poslední offbeat = approach
    do dalšího akordu. approach = jak často je to chromatický náběh (0..1).
    enclose = pravděpodobnost OBKLÍČENÍ cíle (horní soused stupnice + spodní půltón ->
    cíl); aktivní jen při density >= 3 (potřebuje 2 sloty před cílem).
    motion = 'arp' (akordové arpeggio, default) | 'scale' (BĚH PO STUPNICI -> ukáže celou
    chord-scale; pro stupnicové lekce: bebop/diminished/chord-scales).
    taste = volitelný (Evans) model; None = čistě teoretický drill."""
    rng = random.Random(seed)
    npb = density * BEATS
    bars = harmony.bars
    line = []
    prev_exit = harmony.center
    for i, bar in enumerate(bars):
        sc = bar.scale
        ct = bar.chord_tones or sc                           # arpeggiujeme akordové tóny
        nxt = bars[(i + 1) % len(bars)]
        entry = _nearest(bar.guides or ct, prev_exit)        # 1. doba = guide tón, voice-led
        nxt_entry = _nearest(nxt.guides or nxt.scale, entry)
        # SMĚR: střídej takt po taktu (klesat/stoupat); na kraji rejstříku obrať dovnitř
        d = -1 if i % 2 == 0 else 1
        if entry <= harmony.lo + 7:
            d = 1
        elif entry >= harmony.hi - 7:
            d = -1
        if motion == "scale":
            # BĚH PO STUPNICI OD KOŘENE vzhůru -> ukáže pattern stupnice (H-W-...) od toniky;
            # při density 2 je to přesně jedna oktáva (8-tónové dim/bebop = celá stupnice).
            root_pc = bar.root % 12
            roots = [k for k, s in enumerate(sc) if s % 12 == root_pc]
            fit = [k for k in roots if k + npb - 1 < len(sc)]   # vzestupný běh se vejde (bez odrazu)
            si = (fit[0] if fit else (roots[0] if roots
                  else min(range(len(sc)), key=lambda k: abs(sc[k] - entry))))
            fallback = sc[si]
            pos, cur, dd = {}, si, 1                            # vždy vzhůru (čitelný pattern)
            for n in range(npb):
                cur = max(0, min(len(sc) - 1, cur))
                pos[n] = sc[cur]
                nx = cur + dd
                if nx < 0 or nx >= len(sc):                    # odraz dovnitř stupnice
                    dd = -dd; nx = cur + dd
                cur = nx
        elif motion == "thirds_down":
            # SESTUPNÉ TERCIE: restart VYSOKO u každého akordu, klesej po terciích (-2 indexy
            # ve stupnici). Nad dominantou s barvou 'wt' vyjdou augmentované (celotónové) tercie.
            ceiling = harmony.center + 3
            cand = [k for k in range(len(sc)) if sc[k] <= ceiling]
            si = cand[-1] if cand else len(sc) - 1
            fallback = sc[si]
            pos, cur, dd = {}, si, -2
            for n in range(npb):
                cur = max(0, min(len(sc) - 1, cur))
                pos[n] = sc[cur]
                nx = cur + dd
                if nx < 0:                                     # u dna obrať nahoru (stoupavá varianta)
                    dd = -dd; nx = cur + dd
                cur = nx
        elif motion == "thirds":
            # PATTERN PO MALÝCH TERCIÍCH: 4-tónová vzestupná buňka, sekvencovaná o m3 níž
            # (= 2 indexy v symetrické stupnici) -> typický diminished pattern (ukáže symetrii).
            cell = 4
            groups = max(1, npb // cell)
            root_pc = bar.root % 12
            roots = [k for k, s in enumerate(sc) if s % 12 == root_pc]
            fit = [k for k in roots if k - (groups - 1) * 2 >= 0 and k + cell - 1 < len(sc)]
            si = (fit[-1] if fit else (roots[-1] if roots
                  else min(range(len(sc)), key=lambda k: abs(sc[k] - entry))))
            fallback = sc[si]
            pos, n = {}, 0
            for gp in range(groups):                            # každá buňka o m3 níž
                base = si - gp * 2
                for j in range(cell):
                    if n < npb:
                        pos[n] = sc[max(0, min(len(sc) - 1, base + j))]; n += 1
            while n < npb:
                pos[n] = fallback; n += 1
        else:
            # CÍLE na doby = akordové arpeggio v jednom směru (odraz od kraje, bez duplikace)
            ci = min(range(len(ct)), key=lambda k: abs(ct[k] - entry))
            targets = [ct[ci]]
            for b in range(1, BEATS):
                ni = ci + d
                if ni < 0 or ni >= len(ct):                   # odraz dovnitř rejstříku
                    d = -d; ni = ci + d
                ni = max(0, min(len(ct) - 1, ni))
                targets.append(ct[ni]); ci = ni
            fallback = targets[0]
            # POZICE: arpeggio na doby; offbeaty stupnicově spojí / approachnou / OBKLÍČÍ další cíl
            pos = {b * density: targets[b] for b in range(BEATS)}
            last_enc = False
            for b in range(BEATS):
                a = targets[b]
                bnext = targets[b + 1] if b + 1 < BEATS else nxt_entry
                enc = density >= 3 and rng.random() < enclose  # obklíčení cíle bnext (2 sloty před ním)
                if b == BEATS - 1:
                    last_enc = enc
                for j in range(1, density):
                    slot = b * density + j
                    if enc and j == density - 2:               # horní soused stupnice
                        pos[slot] = _enc_upper(sc, bnext)
                    elif enc and j == density - 1:             # spodní půltón (chromaticky) -> cíl
                        pos[slot] = bnext - 1
                    elif j == density - 1:                      # jednoduchý approach na cíl
                        pos[slot] = _approach(bnext, a, sc, rng, approach)
                    else:                                       # stupnicové vyplnění
                        pos[slot] = _scale_between(sc, a, bnext, j / density)
            if npb >= 2 and not last_enc:
                pos[npb - 1] = _approach(nxt_entry, pos.get(npb - 2, targets[-1]), sc, rng, approach)
        prev = None
        for n in range(npb):
            p = pos.get(n, fallback)
            if p == prev:                                     # nikdy neopakuj tentýž tón
                on_beat = (n % density == 0)                  # silná doba -> jiný CHORD tón (zní jako akord);
                pool = [q for q in (ct if on_beat else sc) if q != p]   # slabá -> jiný tón stupnice (ne chromatika)
                if pool:
                    fwd = [q for q in pool if (q - p) * d > 0]
                    p = min(fwd or pool, key=lambda q: abs(q - p))
            line.append((i * BPC + n / density, (1.0 / density) * 0.9, p))
            prev = p
        prev_exit = prev
    return line


def annotate(harmony, line, density=2):
    """Pro náhled-tabuli: role každého tónu = 'guide'|'chord'|'approach'|'scale'.
    (guide = 3/7 na 1. době; chord = akord. tón na těžké; approach = mimo akord/stupnici)."""
    npb = density * BEATS
    roles = []
    for onset, dur, p in line:
        bi = int(onset // BPC); n = int(round((onset - bi * BPC) * density))
        bar = harmony.bars[bi] if 0 <= bi < len(harmony.bars) else None
        if bar is None:
            roles.append("scale"); continue
        on_beat = (n % density == 0)
        if on_beat and n == 0 and p in bar.guides:
            roles.append("guide")
        elif on_beat and p in bar.chord_tones:
            roles.append("chord")
        elif p not in bar.scale:
            roles.append("approach")
        else:
            roles.append("scale")
    return roles
