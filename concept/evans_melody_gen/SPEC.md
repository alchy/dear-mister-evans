# Generátor melodických variací nad akordovými progresemi — zadání

Koncept a postup pro nástroj, který nad danou akordovou progresí generuje **drobné
variace melodické linky** na základě poskytnutých dat (klavírní MIDI, typicky
piano2midi přepisy Billa Evanse). Vychází z experimentů a kódu, které už máme
hotové (`evans_drill.py`).

---

## 1. Kontext — odkud jdeme

V předchozí práci jsme postavili a vyladili **harmonickou vrstvu**, která funguje
dobře a je univerzální:

- detekce akordů z holého MIDI (chroma + Viterbi vyhlazení),
- řazení akordů do 4-akordových buněk,
- barevné septakordy / clustery pro levou ruku, vycentrované na C3,
- a **stupnicový dril pro pravou ruku** (bebopové stupnice, 8 osmin na takt,
  akordové tóny na dobách, bez skoků/opakování/oscilace).

Tohle všechno je v `evans_drill.py` a funguje. **Slabé místo** je pravá ruka:
je to *technický stupnicový dril*, ne melodie — nemá rytmus, frázování, motivy
ani cílené vedení do dalšího akordu. Cílem tohoto projektu je nahradit (nebo
doplnit) tu stupnicovou pravačku **naučenými melodickými variacemi**.

### Co jsme zkusili a co nefungovalo (důležité poučení)

- **Synteticky konstruovaná linka** (arpeggio + přístupový tón) → znělo uměle.
- **Verbatim výseky z nahrávky** → zněly dobře, ale náhodné snímky nemají smysl
  (chybí výběr/struktura).
- **Zjednodušená reálná melodie** → ztrácela charakter (septakordy/barvy).

Závěr: hodnota není v *řezání* ani v *čisté konstrukci*, ale ve **výběru a
zobecnění** — naučit se, *jak se melodie typicky hýbe nad danou harmonií*, a
generovat nové, drobně odlišné varianty ve stejném duchu. To je přesně úloha pro
pravděpodobnostní / učící se model.

---

## 2. Tvrdá realita dat (čti dřív, než sáhneš po neuronce)

- Reálně máme **7 různých skladeb**, ne 19 souborů. Zbytek jsou duplikáty
  (stejná skladba přepsaná víckrát kvůli různě řezanému piano2midi). Viz
  `data/` a tabulka v `SPEC.md` níže.
- To je na trénování neuronové sítě **od nuly velmi málo** (řádově tisíce
  melodických tónů). Hrozí memorizace místo zobecnění.
- Data jsou **zašuměná** (artefakty piano2midi) a melodie **není oddělená** od
  doprovodu — vše je v jednom kanálu.

**Z toho plyne pořadí kroků:** nejdřív čistá extrakce melodie, pak jednoduchý
model (Markov), teprve nakonec případně neuronka (a to nejlíp s augmentací nebo
předtrénovaným modelem).

### Mapa dat (7 skladeb × verze)

| skladba            | soubory             |
|--------------------|---------------------|
| I Hear a Rhapsody  | 01, 08              |
| Nardis             | 02, 09, 16          |
| Emily              | 03, 10, 17          |
| Young and Foolish  | 04, 11, 18          |
| Falling Grace      | 05, 12              |
| Invitation         | 06, 13              |
| Tenderly           | 07, 14, 20          |
| (špatně říznuté)   | 19  — nepoužívat     |

Verze téže skladby jsou ~98 % totožné (jen konstantní časový posun z řezu),
takže pro trénink ber **jednu verzi na skladbu**, ať nepřevážíš opakované fráze.

---

## 3. Cíl

Vstup: **akordová progrese** (buď z `detect_chords()` nad libovolným MIDI, nebo
zadaná ručně) + volitelně počáteční tón.

Výstup: **melodická linka** nad tou progresí, generovaná tak, že
- respektuje harmonii (tóny sedí na akord / akordovou stupnici),
- zní jako naučený styl (z poskytnutých dat),
- **při každém spuštění je trochu jiná** (drobné variace, ne jedna pevná linka),
- a dá se vyrobit více variant téhož přechodu vedle sebe k poslechu/výběru.

Tohle není „jedna správná melodie", ale **paleta variací** k harmonii — přesně
v duchu drilu, jen muzikálnější a naučená z dat.

---

## 4. Architektura (lešení už máme)

```
  MIDI vstup
     │
     ▼
[chords.py]  detekce akordů  ──►  akordová progrese  (root, kvalita, barvy)
     │                                   │
     ▼                                   │  (podmínka / kontext)
[line_extraction.py]                     │
  skyline + register split  ──►  ČISTÁ MELODICKÁ LINKA  (onset, dur, pitch)
     │                                   │
     ▼                                   ▼
  zarovnání melodie k akordům  ──►  TRÉNOVACÍ PÁRY  (kontext → tón)
                                         │
                          ┌──────────────┼──────────────┐
                          ▼              ▼              ▼
                   [markov.py]     [nn_baseline.py]   (fine-tuning
                   n-gram model    malý LSTM/TF        velkého modelu)
                          │              │              │
                          └──────────────┼──────────────┘
                                         ▼
                            GENEROVANÁ VARIACE  ──►  render MIDI
                                                     (LH akordy + RH variace)
```

Klíčové: **harmonii a stupnice už řešit nemusíš** — to dělá `evans_drill.py`.
Generátor jen vybírá, *které* tóny (z dovolených) a v jakém rytmu, uvnitř rámce,
co už máme. To úlohu hodně zužuje a zjednodušuje.

---

## 5. Postup po krocích

### Krok 1 — Extrakce a čištění melodie  (nutný základ)
Soubor: `src/line_extraction.py` (funkční příklad přiložen).

- **Skyline**: v jemné časové mřížce ber nejvyšší znějící tón nad registrovou
  hranicí (např. ≥ MIDI 59) → reálná horní linka. Pod hranicí je doprovod.
- Slož souvislé stejné výšky do **not** (onset, trvání, výška).
- Volitelně **proředit** (zahodit velmi krátké ozdoby) a/nebo kvantizovat na
  osminovou mřížku.
- Výstup: seznam `(onset_beats, dur_beats, pitch)` = trénovací materiál.

Pozn.: u Evanse je melodie občas v blocích obou rukou; skyline je rozumná
aproximace, ne dokonalá. Pro lepší výsledky lze později přidat oddělení hlasů.

### Krok 2 — Reprezentace (tokenizace)  (klíčové rozhodnutí)
Melodii **neukládej jako absolutní výšky**, ale relativně k harmonii, ať model
zobecní napříč tóninami:

- `degree` = stupeň tónu vůči **kořeni aktuálního akordu** (0–11), nebo index ve
  stupnici akordu (0–7) + příznak „mimo stupnici / chromatika".
- `interval` = pohyb od předchozího tónu (v půltónech), případně směr.
- `dur_class` = rytmická třída (osminka / čtvrtka / …), pokud chceš modelovat i rytmus.
- kontext = `(kvalita_akordu, degree, prev_interval)`.

Doporučení: **transpozičně nezávislá** reprezentace (degree/interval vůči kořeni)
je nejdůležitější trik — vynutí, že „ii–V do moll" se naučí jednou, ne 12×.

### Krok 3 — Baseline: Markovův / n-gramový model  (doporučený první krok)
Soubor: `src/markov.py` (funkční příklad přiložen).

- Nauč se počty `P(next_token | kontext)` z trénovacích párů.
- **Backoff**: když konkrétní kontext nemáš, ustup na obecnější (jen kvalita,
  pak globální).
- Generuj **vzorkováním** (s teplotou) → drobné variace, nepřetrénuje se,
  interpretovatelné, běží kdekoliv bez GPU.
- Vyber dovolené tóny z akordové stupnice (rámec z `evans_drill`), ať to vždy
  sedí harmonicky.

Tohle je nejlepší poměr „funguje na malých datech / úsilí". Začni tady.

### Krok 4 — Malá neuronka  (až když Markov ukáže, že to dává smysl)
Soubor: `src/nn_baseline.py` (skeleton + komentáře).

- Malý **LSTM** nebo mrňavý **transformer** předpovídající další token
  podmíněně akordem.
- **Augmentace transpozicí do všech 12 tónin** → 12× víc dat (klíčové při málu dat).
- Pozor na overfitting: dropout, early stopping, malý model (1–2 vrstvy).
- Sampling s teplotou / top-k pro variace.

### Krok 5 (volitelně) — Fine-tuning velkého modelu
Vzít předtrénovaný hudební model (na velkém jazz MIDI korpusu, např. typu
Music Transformer / REMI) a jen ho doladit na Evansovi + podmínit akordy. Tady
neuronka opravdu zazáří, protože „jak se hýbe melodie" se naučila jinde a tvoje
data jen dodají styl. Samostatný projekt (GPU, data).

---

## 6. Vyhodnocení (jak poznat, že to je dobré)

Kvantitativně to nepoznáš — je to hudba. Postup:
1. **Poslech**: generuj 3–5 variant téhož přechodu vedle sebe (jako jsme dělali
   s clustery) a vybírej, co zní dobře. Nech si to kurátorovat člověkem.
2. **Sanity checky** (automaticky, jako v `evans_drill`): žádné oktávové skoky,
   žádné opakované/oscilující tóny, tóny sedí na akord/stupnici, rozsah v pásmu.
3. **Variabilita**: změř, jak moc se varianty liší (ať to není pořád totéž ani
   úplný chaos) — laditelné teplotou samplingu.

---

## 7. Mapa souborů v balíčku

```
evans_melody_gen/
  SPEC.md                 ← tento dokument (zadání)
  README.md               ← jak spustit
  requirements.txt
  evans_drill.py          ← HOTOVÉ lešení: akordy + stupnicový dril (funguje)
  src/
    chords.py             ← tenká vrstva nad evans_drill (detekce akordů, voicingy)
    line_extraction.py    ← PŘÍKLAD: extrakce a čištění melodie (funguje)
    markov.py             ← PŘÍKLAD: Markovův generátor variací (funguje)
    nn_baseline.py        ← SKELETON: malá LSTM neuronka (k dopracování)
  examples/
    run_markov_demo.py    ← end-to-end ukázka: data → model → generovaná variace MIDI
  data/                   ← tvoje MIDI (be-slice*.mid)
  outputs/                ← sem padají vygenerovaná MIDI
```

---

## 8. Známé pasti (ať nešlapeš do stejných)

- **Neoddělená melodie** → nejdřív `line_extraction`, jinak učíš model na kompu.
- **Duplikáty v datech** → ber 1 verzi na skladbu (viz tabulka), jinak převážíš.
- **Absolutní výšky** → vždy reprezentuj relativně k akordu (transpoziční invariance).
- **Příliš velká neuronka na malá data** → memorizace. Začni Markovem.
- **Generování bez harmonického rámce** → omez tóny na akordovou stupnici, ať to
  vždy sedí; rámec máš zdarma z `evans_drill`.

---

## 9. První konkrétní krok na localhostu

1. `pip install -r requirements.txt`
2. `python examples/run_markov_demo.py` — proběhne celý řetězec na přiložených
   datech a vygeneruje ukázkovou variaci do `outputs/`.
3. Pak si hraj: uprav tokenizaci v `markov.py`, přidej rytmus, zkus víc kontextu,
   a teprve když to zní slibně, otevři `nn_baseline.py`.

Hodně štěstí — harmonii máš hotovou, teď jde o tu melodii. 🙂
