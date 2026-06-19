#!/usr/bin/env python3
"""
evans_drill.py  --  generuje cvičný MIDI dril z klavírního MIDI souboru.

Z libovolného MIDI (sólový klavír v jednom kanálu, jako u piano2midi) vytáhne
akordy a vyrobí dvouruční dril:
  - LEVÁ RUKA  : barevné septakordy / clustery, vycentrované kolem C3
  - PRAVÁ RUKA : bebopové vodicí běhy (8 osmin na takt) od C4 výš,
                 akordové tóny na dobách, bez oktávových skoků,
                 bez opakovaných a bez oscilujících (a-b-a) tónů.

Vše je odvozené z hudební teorie (akordové / bebopové stupnice), ne z konkrétní
nahrávky, takže to funguje i na vlastních improvizacích bez známé skladby.

Použití:
    python evans_drill.py vstup.mid
    python evans_drill.py slozka/ -o vystup_slozka/
    python evans_drill.py vstup.mid --mode chords     # jen akordy (levá ruka)
    python evans_drill.py vstup.mid --tempo 100 --cell 4

Závislosti:  pip install mido numpy
"""
import argparse, os, glob, statistics
from collections import defaultdict

try:
    import mido
    import numpy as np
except ImportError:
    raise SystemExit("Chybí závislosti. Spusť:  pip install mido numpy")

PC = ['C','C#','D','D#','E','F','F#','G','G#','A','A#','B']
def nm(p): return f"{PC[p%12]}{p//12-1}"

# ---- akordové šablony (pro detekci) a kvality ----
TEMPL = {'maj':[0,4,7],'min':[0,3,7],'7':[0,4,7,10],'maj7':[0,4,7,11],'m7':[0,3,7,10],
         'm7b5':[0,3,6,10],'dim7':[0,3,6,9],'mMaj7':[0,3,7,11],'aug':[0,4,8],
         'sus':[0,5,7],'6':[0,4,7,9],'m6':[0,3,7,9]}
# čtyřhlasé septakordy (pro voicing levé ruky)
SEV = {'maj':[0,4,7,11],'min':[0,3,7,10],'7':[0,4,7,10],'maj7':[0,4,7,11],'m7':[0,3,7,10],
       'm7b5':[0,3,6,10],'dim7':[0,3,6,9],'mMaj7':[0,3,7,11],'aug':[0,4,8,11],
       'sus':[0,5,7,10],'6':[0,4,7,9],'m6':[0,3,7,9]}
# 8-tónové bebopové / akordové stupnice (pro pravou ruku)
BEBOP = {'maj':[0,2,4,5,7,8,9,11],'6':[0,2,4,5,7,8,9,11],'maj7':[0,2,4,5,7,8,9,11],
         'min':[0,2,3,4,5,7,9,10],'m7':[0,2,3,4,5,7,9,10],'m6':[0,2,3,4,5,7,9,11],
         '7':[0,2,4,5,7,9,10,11],'sus':[0,2,4,5,7,9,10,11],'m7b5':[0,2,3,5,6,8,10,11],
         'dim7':[0,2,3,5,6,8,9,11],'mMaj7':[0,2,3,4,5,7,9,11],'aug':[0,2,4,6,7,8,9,11]}
QNAME = {'maj':'maj7','min':'m7','sus':'7sus','aug':'augMaj7'}
def lab(r,q): return f"{PC[r]}{QNAME.get(q,q)}"


# ---------- 1. načtení MIDI ----------
def load_notes(path):
    mid = mido.MidiFile(path); tpb = mid.ticks_per_beat
    notes = []
    for tr in mid.tracks:
        t=0; active={}
        for m in tr:
            t += m.time
            if m.type=='note_on' and m.velocity>0:
                active.setdefault(m.note,[]).append((t,m.velocity))
            elif m.type=='note_off' or (m.type=='note_on' and m.velocity==0):
                if active.get(m.note):
                    st,v = active[m.note].pop(0)
                    notes.append((st/tpb,(t-st)/tpb,m.note,v))
    notes.sort()
    if not notes:
        raise ValueError("V souboru nejsou žádné noty.")
    return notes


# ---------- 2. detekce akordů (chroma + Viterbi) ----------
def _tvec(ints):
    v=np.zeros(12)
    for i in ints: v[i%12]=1
    return v/np.linalg.norm(v)
_CH = [(r,q) for q in TEMPL for r in range(12)]
_TV = np.array([np.roll(_tvec(TEMPL[q]),r) for (r,q) in _CH])

def detect_chords(notes, hop=1.0, win=2.0, stay=0.55):
    end = max(o+d for o,d,p,v in notes); nwin=int(end/hop)+1
    chroma=np.zeros((nwin,12)); bass=[None]*nwin
    for w in range(nwin):
        ws,we=w*hop,w*hop+win; bw=defaultdict(float)
        for o,d,p,v in notes:
            ov=max(0,min(o+d,we)-max(o,ws))
            if ov>0: chroma[w,p%12]+=ov*(v/127.0); bw[p]+=ov
        if bw: bass[w]=min(bw)%12
        s=chroma[w].sum()
        if s>0: chroma[w]/=s
    E=chroma@_TV.T
    for w in range(nwin):
        if bass[w] is not None:
            for ci,(r,q) in enumerate(_CH):
                if r==bass[w]: E[w,ci]+=0.15
    N=len(_CH); dp=E.copy(); bp=np.zeros((nwin,N),int)
    for w in range(1,nwin):
        prev=dp[w-1]; bi=prev.argmax(); bv=prev[bi]
        for ci in range(N):
            if prev[ci]+stay>=bv: dp[w,ci]=prev[ci]+stay+E[w,ci]; bp[w,ci]=ci
            else: dp[w,ci]=bv+E[w,ci]; bp[w,ci]=bi
    path=[int(dp[-1].argmax())]
    for w in range(nwin-1,0,-1): path.append(int(bp[w,path[-1]]))
    path=path[::-1]; seq=[_CH[i] for i in path]
    segs=[]; cur=seq[0]; st=0
    for w in range(1,nwin):
        if seq[w]!=cur: segs.append((st,w,cur)); cur=seq[w]; st=w
    segs.append((st,nwin,cur))
    # akordy s reálnými pitch-classy (pro barvy) + sloučení opakování
    merged=[]
    for a,b,(r,q) in segs:
        if b-a<1: continue
        dur=defaultdict(float)
        for o,d,p,v in notes:
            ov=max(0,min(o+d,b)-max(o,a))
            if ov>0: dur[p%12]+=ov
        present=set(pc for pc in dur if dur[pc]>=0.3)
        if merged and merged[-1][0]==r and merged[-1][1]==q:
            merged[-1][2] |= present
        else:
            merged.append([r,q,set(present)])
    return merged


# ---------- 3. voicing levé ruky (septakord + barva, cluster, střed ~C3) ----------
def chord_pcs(r,q,present):
    ints=list(SEV.get(q,[0,4,7,10])); pcs=[(r+i)%12 for i in ints]; fifth=(r+7)%12
    for color in [(r+2)%12,(r+9)%12,(r+6)%12]:        # 9, 13, #11 pokud reálně zní
        if color in present and color not in pcs and fifth in pcs:
            pcs[pcs.index(fifth)]=color; break
    return pcs[:4]

def lh_voicing(pcs, center=48):
    pcs=sorted(set(pcs)); best=None; bk=1e9
    for rot in range(len(pcs)):
        order=pcs[rot:]+pcs[:rot]
        voic=[36+(order[0]%12)]
        for pc in order[1:]:
            nx=voic[-1]+((pc-voic[-1])%12); nx=nx+12 if nx==voic[-1] else nx; voic.append(nx)
        while statistics.mean(voic) < center-6: voic=[x+12 for x in voic]
        while statistics.mean(voic) > center+6: voic=[x-12 for x in voic]
        score=abs(statistics.mean(voic)-center)+0.1*(max(voic)-min(voic))
        if min(voic)>=36 and max(voic)<=58 and score<bk: bk=score; best=sorted(voic)
    if best is None:
        v=sorted(36+(pc%12) for pc in pcs)
        while statistics.mean(v)<center-6: v=[x+12 for x in v]
        best=v
    return best


# ---------- 4. bebopová linka pravé ruky ----------
def rh_line(qs, rh_lo=60, rh_hi=86):
    """qs = seznam (root,quality). Vrací seznam 8-tónových běhů (jeden na akord)."""
    def scale(r,q):
        pcs=set((r+o)%12 for o in BEBOP.get(q,[0,2,4,5,7,9,10,11]))
        return sorted(p for p in range(rh_lo,rh_hi+9) if p%12 in pcs)
    flat=[]; bar_of=[]; cur=None; d=1
    for i,(r,q) in enumerate(qs):
        sp=scale(r,q)
        for _ in range(8):
            if cur is None:
                cset=set((r+x)%12 for x in SEV.get(q,[0,4,7,10]))
                note=min([p for p in sp if p%12 in cset], key=lambda x:abs(x-(rh_lo+12)))
            else:
                ahead=[p for p in sp if (p>cur if d>0 else p<cur)]
                if not ahead: d=-d; ahead=[p for p in sp if (p>cur if d>0 else p<cur)]
                note=min(ahead,key=lambda x:abs(x-cur))
                if note>rh_hi or note<rh_lo:                       # otočka na kraji pásma
                    d=-d; ahead=[p for p in sp if (p>cur if d>0 else p<cur)]
                    note=min(ahead,key=lambda x:abs(x-cur)) if ahead else min(sp,key=lambda x:abs(x-cur))
                if len(flat)>=2 and note==flat[-2]:                # žádné a-b-a
                    ah2=[p for p in ahead if p!=flat[-2]]
                    if ah2: note=min(ah2,key=lambda x:abs(x-cur))
                if note==cur:                                      # žádné opakování
                    alt=[p for p in sp if (p>cur if d>0 else p<cur)]
                    note=min(alt,key=lambda x:abs(x-cur)) if alt else cur+(1 if d>0 else -1)
            flat.append(note); bar_of.append(i); cur=note
        if cur>=rh_hi-3: d=-1
        elif cur<=rh_lo+3: d=1
    return [[flat[k] for k in range(len(flat)) if bar_of[k]==i] for i in range(len(qs))]


# ---------- 5. sestavení buněk a render ----------
def build_cells(merged, cell=4):
    groups=[merged[i:i+cell] for i in range(0,len(merged),cell)]
    if len(groups)>1 and len(groups[-1])<2:
        groups[-2]+=groups[-1]; groups.pop()
    out=[]
    for g in groups:
        out.append([(lab(r,q),(r,q),lh_voicing(chord_pcs(r,q,pr))) for r,q,pr in g])
    return out

def render(cells, path, mode='both', bpm=92, rh_lo=60, rh_hi=86):
    tpb=220; mid=mido.MidiFile(type=1); mid.ticks_per_beat=tpb
    meta=mido.MidiTrack(); mid.tracks.append(meta)
    meta.append(mido.MetaMessage('set_tempo',tempo=int(60000000/bpm),time=0))
    meta.append(mido.MetaMessage('time_signature',numerator=4,denominator=4,time=0))
    trL=mido.MidiTrack(); trL.append(mido.MetaMessage('track_name',name='LH chords',time=0))
    trR=mido.MidiTrack(); trR.append(mido.MetaMessage('track_name',name='RH line',time=0))
    mid.tracks += [trL,trR]
    evL=[]; evR=[]; t=0.0; BAR=4.0
    for cellnotes in cells:
        rh = rh_line([c[1] for c in cellnotes], rh_lo, rh_hi) if mode!='chords' else None
        for bi,(labl,(r,q),v) in enumerate(cellnotes):
            if mode!='line':
                for p in v: evL.append((t,1,p)); evL.append((t+BAR*0.96,0,p))
            if mode!='chords':
                for k,p in enumerate(rh[bi]): evR.append((t+k*0.5,1,p)); evR.append((t+k*0.5+0.45,0,p))
            t += BAR
        t += BAR     # prázdný takt mezi buňkami
    for tr,ev,vel in [(trL,evL,64),(trR,evR,88)]:
        ev.sort(key=lambda x:(x[0],x[1])); last=0
        for tt,typ,p in ev:
            dt=max(0,int(round((tt-last)*tpb))); last=tt
            tr.append(mido.Message('note_on' if typ else 'note_off',
                                   note=int(max(1,min(127,p))), velocity=vel if typ else 0, time=dt))
    mid.save(path)


def process_file(inp, outdir, args):
    notes = load_notes(inp)
    merged = detect_chords(notes)
    cells = build_cells(merged, cell=args.cell)
    base = os.path.splitext(os.path.basename(inp))[0]
    out = os.path.join(outdir, f"{base}_drill.mid")
    render(cells, out, mode=args.mode, bpm=args.tempo, rh_lo=args.rh_low, rh_hi=args.rh_high)
    print(f"  {os.path.basename(inp)}  ->  {out}   ({len(merged)} akordů, {len(cells)} buněk)")
    return out


def main():
    ap=argparse.ArgumentParser(description="Generuje cvičný MIDI dril (akordy + bebopová pravačka) z klavírního MIDI.")
    ap.add_argument("input", help="MIDI soubor nebo složka s MIDI soubory")
    ap.add_argument("-o","--out", default="drill_out", help="výstupní složka (default: drill_out)")
    ap.add_argument("--mode", choices=["both","chords","line"], default="both",
                    help="both=obě ruce, chords=jen akordy, line=jen pravačka")
    ap.add_argument("--tempo", type=int, default=92, help="tempo v BPM (default 92)")
    ap.add_argument("--cell", type=int, default=4, help="kolik akordů na buňku (default 4)")
    ap.add_argument("--rh-low", type=int, default=60, help="spodní hranice pravačky (MIDI, default 60 = C4)")
    ap.add_argument("--rh-high", type=int, default=86, help="horní hranice pravačky (MIDI, default 86)")
    args=ap.parse_args()

    os.makedirs(args.out, exist_ok=True)
    if os.path.isdir(args.input):
        files=sorted(glob.glob(os.path.join(args.input,"*.mid"))+glob.glob(os.path.join(args.input,"*.midi")))
        if not files: raise SystemExit("Ve složce nejsou žádné .mid soubory.")
    else:
        files=[args.input]
    print(f"Zpracovávám {len(files)} soubor(ů), výstup do '{args.out}/':")
    for f in files:
        try: process_file(f, args.out, args)
        except Exception as e: print(f"  CHYBA u {f}: {e}")
    print("Hotovo.")

if __name__=="__main__":
    main()
