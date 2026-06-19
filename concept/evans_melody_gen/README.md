# evans_melody_gen

Generátor **melodických variací nad akordovými progresemi**, postavený na naší
předchozí práci (detekce akordů + stupnicový dril). Cíl: nad danou harmonií
generovat drobné, naučené variace melodické linky.

**Začni přečtením [`SPEC.md`](SPEC.md)** — je tam celý koncept, postup a poučení
z toho, co fungovalo a nefungovalo.

## Instalace
```bash
pip install -r requirements.txt
```
(Markov baseline potřebuje jen `mido` a `numpy`. `torch` je volitelný, jen pro
experimentální neuronku.)

## Rychlý start
```bash
# kompletní ukázka: natrénuje Markov model na data/ a vygeneruje variace
python examples/run_markov_demo.py
# výstup: outputs/demo_variation_*.mid
```

## Co je hotové vs. k dopracování
- `evans_drill.py` — **HOTOVÉ** lešení: detekce akordů + stupnicový dril (LH+RH).
  Funguje samostatně: `python evans_drill.py data/be-slice09.mid`
- `src/chords.py` — tenká vrstva (detekce akordů, voicingy, akordové stupnice).
- `src/line_extraction.py` — **FUNKČNÍ příklad**: extrakce melodie (skyline).
- `src/markov.py` — **FUNKČNÍ příklad**: Markovův generátor variací. *Začni tady.*
- `src/nn_baseline.py` — **SKELETON** malé LSTM neuronky (k dopracování, volitelné).

## Doporučené pořadí práce
1. Pusť `run_markov_demo.py`, poslechni variace, ověř, že to vůbec zní.
2. Vylaď `src/markov.py` — tokenizace, rytmus, víc kontextu (n-gram délka).
3. Teprve když Markov dává slibné výsledky, otevři `src/nn_baseline.py`.

## Data
`data/be-slice*.mid` jsou tvoje piano2midi přepisy. Reálně je to **7 skladeb**
(zbytek duplikáty); mapa a varování jsou v `SPEC.md`. Modely berou 1 verzi na
skladbu, ať nepřeváží opakované fráze.

## Známá omezení
- Melodie je vytažená skyline metodou (není dokonalé oddělení rukou).
- Málo dat → Markov je vhodnější než neuronka od nuly.
- Generování je omezené na akordovou stupnici, takže harmonicky vždy sedí.
