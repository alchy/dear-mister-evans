# dear-mister-evans

> Z libovolného MIDI vyrob zjednodušenou **Evansovskou** verzi skladby —
> barevné rootless voicingy s vedením hlasů + melodie postavená na harmonii.
> Nástroj pro **učení jazzového piana**.
>
> *Turn any MIDI into a simplified Bill-Evans-style arrangement: rootless
> voicings with voice-leading + a melody built on top of the harmony.*

---

## O co jde

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
  arrange.py       # DIRIGENT: libovolné MIDI -> Evansovská aranž (kroky 1-4)
  voicings.py      # rootless voicingy + voice-leading (levá ruka)
  melody_top.py    # melodie na harmonické kostře + pojistky (pravá ruka)
  motif.py         # motivická návratnost (téma se vrátí)
  melody_v2.py     # starší: Markov na (interval+rytmus) — z čeho jsme vyšli
  phrases_v3.py    # starší: frázový přístup
  player.py        # přehrávání MIDI do portu
concept/           # původní zadání + sdílené jádro (detekce akordů, evans_drill)
analysis/          # ověřovací skripty (probe, clash)
```

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
