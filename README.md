# dear-mister-evans

> Nástroje pro **učení jazzového piana** postavené na harmonii a vedení hlasů.
> *Tools for learning jazz piano, grounded in harmony and voice-leading.*

Repo má **dvě části**:

1. **`improved/voice/` — virtuální Mark Levine (AKTUÁLNÍ směr)** 🎓
   Interaktivní výukový software: koncept *vysvětli → předveď → A/B*, s anotovaným
   klaviaturním náhledem. Teorie (chord-scales, guide tóny, voice-leading, bebop
   devices) tě vede do rukou. **→ [improved/voice/README.md](improved/voice/README.md)**
   ```bash
   python improved/voice/gui.py
   ```
2. **Aranžér + syntezátor cvičení (prototyp, níže)** — z libovolného MIDI vyrob
   zjednodušenou Evansovskou aranž; generátor progresí a cvičebnice stupnic.

---

## Aranžér: o co jde

Cílem je vzít jakoukoliv skladbu (MIDI) a vyrobit z ní **zjednodušenou podobu
k učení** ve stylu Billa Evanse — ne virtuózní transkripci, ale čistou kostru:
souvislé harmonické přechody a zpívající melodii nahoře.

Klíčové poučení projektu (ověřené poslechem): *to, co u Evanse drží skladbu
pohromadě, není bravurní pravačka, ale **harmonie a vedení hlasů.*** Proto je
celá architektura postavená odspodu — nejdřív harmonie, teprve pak melodie.

## Jak to funguje (4 kroky)

```
   libovolné MIDI
        │
        ▼
  [1] přečti noty            jen holá fakta: výška, čas, hlasitost
        │
        ▼
  [2] detekuj akord/takt     chroma + bas → jeden akord na takt
        │                    (nejchytřejší i nejslabší místo)
        ▼
  [3] najdi opakování        stejné 4-taktové bloky → forma → návrat motivu
        │
        ▼
  [4] postav Evanse:
        ├─ levá ruka: rootless voicingy + voice-leading
        ├─ pravá ruka: melodie na vrchních tónech voicingů
        │              (+ odstranění střetů a opakovaných tónů)
        └─ motiv se vrací v opakovaném dílu formy
        │
        ▼
   outputs_arr/<jméno>__harmony.mid   (jen akordy)
   outputs_arr/<jméno>__full.mid      (akordy + melodie)
```

**Jednou větou:** poslechni → urči akord na každý takt → najdi, co se opakuje →
přehraj to jako Evans.

> ⚠️ Kvalita výstupu stojí na kroku [2]. Skladby s jasným harmonickým rytmem
> (akord na takt) vyjdou výborně; hustá sóla, kde je melodie i doprovod v jednom
> kanálu, detektor občas „tipne". Pro takové případy lze zadat akordy ručně.

## Instalace

Potřebuješ Python 3.12 (3.11 funguje taky; jen ne 3.13+ pokud chceš `python-rtmidi`
přehrávání bez kompilace).

```bash
python -m venv .venv
.venv\Scripts\activate           # Windows
pip install -r requirements.txt
```

## Použití

```bash
# vyrob aranž z libovolného MIDI (prvních 32 taktů)
python improved/arrange.py "cesta/k/skladbe.mid" --bars 32 --bpm 110

# přehraj výstup do MIDI portu (např. loopMIDI -> virtuální piano)
python improved/player.py "outputs_arr/skladba__full.mid"
```

Volby `arrange.py`:

| volba | význam |
|---|---|
| `--bars N` | kolik taktů zpracovat |
| `--bpm N` | tempo přehrávání |
| `--seed N` | jiná melodická varianta |
| `--no-melody` | jen harmonie (voicingy) |

`player.py --list` vypíše dostupné MIDI-out porty.

## Struktura

```
improved/
  arrange.py            # DIRIGENT: libovolné MIDI -> Evansovská aranž (kroky 1-4)
  arrange_chords.py     # aranž přímo ze zadaných akordů (--chords) / pro PianoChord
  harmony.py            # key-aware detekce akordů (tónina + diatonický prior + Viterbi)
  voicings.py           # rootless voicingy + voice-leading (levá ruka)
  melody_top.py         # melodie na harmonické kostře + rytmický comp + pojistky
  melody_markov.py      # naučená melodie (Markov: interval+rytmus z Evanse, band-aware)
  motif.py              # motivická návratnost (téma se vrátí)
  chord_markov.py       # generátor akordových PROGRESÍ (key-relativní Markov)
  standards.py          # kurátorský korpus changes jazzových standardů
  scale_drill.py        # stupnicový dril + "triplets in four" (cvičení stupnic)
  build_set.py          # učební sada aranží -> OneDrive
  build_drill_library.py# strukturovaná cvičebnice drilů -> OneDrive
  player.py             # přehrávání MIDI do portu
  extract_progression.py# příkaz MIDI->progrese (JSON) pro GUI (PianoChord)
concept/                # původní zadání + sdílené jádro (detekce akordů, evans_drill)
analysis/               # ověřovací skripty (probe, clash, survey, corpus...)
```

## Generátor progresí + cvičebnice stupnic

Kromě aranží umí projekt **generovat harmonii** a **cvičení stupnic**:

```bash
# vygeneruj novou akordovou progresi ve stylu sbírky (dur/moll) a přehraj v Evansově hávu
python improved/chord_markov.py --key C --mode maj --bars 16 --render out.mid

# vyrob strukturovanou cvičebnici stupnicových drilů do OneDrive
python improved/build_drill_library.py
```

**`chord_markov.py`** — key-relativní Markov naučený z kurátorského korpusu
standardů (`standards.py`); generuje nové funkční progrese (ii-V-I, kvintové
kruhy, mollové kadence).

**`scale_drill.py`** — cvičení stupnic nad progresí: bas + akord/takt v levé
ruce, pravá ruka = **stupnicový dril** (8 osmin/takt, střídavě vzestupně/sestupně
+ variace, swing feel, dosedání na guide tone dalšího akordu). Stupnice se mění
dle akordu (chord-scale teorie: bebop / pentatonika / *auto* paleta — dorská,
lydická, altered, lokrická, melodická moll, diminished...).

### "Triplets in four"

Speciální cvičení (`scale_drill.triplets_in_four`): hraje se **4-notová buňka**
(sestupné arpeggio v terciích) v **triolovém rytmu** (3 noty/dobu). Protože je
buňka 4-notová a doba má 3 trioly, **buňka se posouvá proti 4/4** (polyritmus
3:4) — přízvuk dosedá pokaždé na jiný tón buňky = sofistikovaný "plovoucí"
evansovský feel. Začátky buněk stoupají po terciích, na začátku akordu je
chromatický náběh a barvy z charakteristické jazzové stupnice (altered na
dominantě). Inspirováno reálnou ukázkou; přesné cvičení viz README ve složce
`triplets-in-four-evans`.

Cvičebnice (`build_drill_library.py`) vyrobí do OneDrive strukturované složky
(cíl × varianta stupnic), v každé MIDI na progresi + `README.md` s principem.

### Obecný pattern engine (princip = data)

`pattern_engine.py` zahraje libovolný cvičný princip zadaný jako **SPEC (dict)**
se 4 osami: `rhythm` (subdivize/grupování/swing), `cell` (tvar buňky: scale /
arpeggio / **markov** / …), `scale` (chord-scale paleta) a `target` (landing).
Nový princip, který skládá existující buňky = **nový spec (data), ne kód**;
markov-buňka generuje **variace ve stylu naučeného segmentu**.

```bash
# z MIDI segmentu vytáhni fakta a navrhni spec
python improved/analyze_segment.py "segment.mid"
# zahraj princip (spec) nad libovolnou progresí
python improved/pattern_engine.py --spec triplets_in_four --chords "Am7 D7 Gm7 Gm7"
```

Workflow: *dáš segment → `analyze_segment` vytáhne subdivizi/tvar buňky/chromatiku
→ spec → engine zahraje nad libovolnou progresí (+ markov variace) → cvičebnice.*
Dnešní dril i „triplets in four" jsou v enginu vyjádřené jako specy (`SPECS`).
Vzestupný bebopový běh ve stylu **Oscar Peterson** *Jazz Exercises* Ex.4 je spec
`oscar_dev` (`cell_run`: chromatické obklíčení cíle + změny směru + arpeggio vsuvky).

### Prolnutí stylů přes Markov (Evans × Peterson)

`blend_markov.py` postaví Markov model z Petersonova cvičení a **interpoluje jeho
přechodová rozdělení s naučeným Evansovým modelem**:

```
P_mix(token | kontext) = alpha · P_Evans + (1 − alpha) · P_Peterson
```

`alpha = 1.0` → čistý Evans, `0.0` → čistý partner, `0.5` → vyvážené (default).
Generuje se Evansovým pipeline (kostra + frázování), ale lokální pohyb i rytmus
táhne z mixu obou stylů. **Partner** (`--partner`) je učený protějšek:
`peterson` (cvičení) nebo `lines` (reálné „Daily jazz line" pasáže).

```bash
python improved/blend_markov.py --chords "Cm7 F7 Bbmaj7 ..." --alpha 0.5 --partner lines
```

Materiál pro partnery (gitignored, lokálně): Petersonova cvičení do
`data_external/peterson/`, jazzové linky do `data_external/daily_lines/` —
korpus se rozšíří automaticky. Linky jsou husté/jednokanálové (linka + bas);
`lines_corpus.clean_line` vytáhne čistou melodii (registrové hradlo + sledování
nejbližšího tónu, basové údery = pauza) → model má jen ~6 % oktávových skoků.

### Syntezátor cvičení (`synth.py`)

Cvičení se **skládá z vah** — kombinuje pravidlové patterny a naučený Markov do
jedné linky. Vše je recept (data):

| osa | volby |
|---|---|
| **typy buněk** (`--cells`) | `scale`, `arpeggio`, `run` (pravidla) + `markov` (naučené/prolnuté) — váhy, losuje se po taktech |
| **prolnutí** (`--alpha`) | `1`=Evans … `0`=Peterson (pro `markov` buňku) |
| **tvar akordu** (`--voicing`) | `basic` (R-3-5-7) · `rootless` (Evans) · `color` (alterace) |
| **stupnice** (`--scale`) | `auto` · `bebop` · `pentatonic` · `jazz_color` |
| **rytmus** | `sub` (2/3), swing, „triplets in four" fázování |

Voice-leading (nejúspornější přesun 4 hlasů, drží společné tóny) jede ve všech
třech tvarech akordu — `basic` začne v základním sedmičkovém tvaru a do dalšího
akordu přejde nejmenším pohybem.

```bash
# základní 7-akordy + půl Peterson běh / půl prolnutý markov, bebop, in-four
python improved/synth.py --voicing basic --cells "run=0.5,markov=0.5" --alpha 0.5

# barevné voicingy + čistě prolnutý markov blíž Petersonovi
python improved/synth.py --voicing color --cells "markov=1.0" --alpha 0.35
```

Tím se cvičení **syntetizuje** z os: *tvar akordu × typy buněk × Evans/Peterson
mix × stupnice × rytmus* — bez zásahu do enginu (nový recept = data v `RECIPES`).

### GUI (`gui.py`)

Jednoduché okno (Tkinter, žádné závislosti navíc) pro běžného uživatele — vše se
naklikává, není potřeba příkazová řádka:

```bash
python improved/gui.py
```

- slidery **vah patternů** (běh / markov / stupnice / arpeggio) a **prolnutí**
  (Evans↔Peterson), výběr **tvaru akordu / stupnice / rytmu**, tempo, seed, port,
- **▶ Generuj a přehraj** (poslech), **■ Stop**, **💾 Export MIDI…**, **🎲 Nový seed**.

GUI mluví výhradně přes fasádu `gui_backend` (nezná vnitřek enginu) — backend lze
vyměnit beze změny GUI.

## Pozadí / teorie

- **Rootless voicings** (A/B formy) — Bill Evans / Mark Levine, *The Jazz Piano Book*.
- **Voice-leading** — každý další akord se posune od předchozího co nejmíň
  (společné tóny se drží), což vytváří souvislost.
- Vrchní tóny dobře vedených voicingů samy tvoří melodickou linku.

## Stav

Funkční prototyp ověřovaný poslechem. Trénovací data (přepisy B. Evanse) nejsou
součástí repa kvůli autorským právům — nástroj je funguje na vlastních MIDI.

## Licence

Kód: zatím bez explicitní licence (TODO). Hudební vstupy si dodává uživatel.

---
🤖 Vytvořeno s pomocí [Claude Code](https://claude.com/claude-code).
