# voice — virtuální Mark Levine (výukový software)

> Interaktivní výuka jazzové improvizace: koncept **vysvětli → předveď → A/B slyš
> rozdíl**, s **anotovaným klaviaturním náhledem** (tabule). Ne (jen) generátor —
> výukový program, kde tě teorie vede do rukou.
>
> *Interactive jazz-improvisation tutor built on music theory (chord-scales, guide
> tones, voice-leading, bebop devices), with an annotated piano "blackboard".*

Toto je **aktuální směr** projektu — čistý přepis postavený na poučení ze staršího
prototypu (viz kořenový [README](../../README.md)). Staví **na jazzové teorii**
(theory-grounded devices), ne na preferenci uživatele.

## Spuštění

```bash
python improved/voice/gui.py          # výukové GUI (hlavní)
python improved/voice/cli.py --chords "Dm7 G7 Cmaj7" --density 2 --play   # CLI generátor
```

Potřebuje `mido` (+ MIDI-out port; na Windows stačí *Microsoft GS Wavetable Synth*).

## Tři pilíře, které dostáváš „do ruky"

1. **Akord v levé ruce** + jeho optimální přesun (voice-leading).
2. **Tóny stupnice** dostupné nad každým akordem (chord-scale dle funkce).
3. **Korektní landing tón** do dalšího akordu (3/7 půltónem).

## Klaviaturní náhled (tabule) — legenda

Per akord dvě klaviatury: **vlevo levá ruka** (voicing + čáry voice-leadingu),
**vpravo melodie** (pořadová kolečka, dráhové schodiště).

| značka | význam |
|--------|--------|
| ● modrá (levá klav.) | tóny voicingu levé ruky; **žlutě bez čísla** = základní tón (bas) |
| modré čáry | vedení hlasů mezi akordy (k-tý hlas → k-tý hlas) |
| ● oranžová (pravá) | melodický tón **ze stupnice** (diatonický) |
| ● fialová (pravá) | **chromatický approach** (mimo stupnici i akord) — jen na slabé době |
| ◯ zelený kroužek | **guide tón** (3/7) |
| světle zelené tečky | paleta tónů stupnice akordu |
| ▼ + popisek `B (3·G7)` | **landing**: na který guide tón (3/7) dalšího akordu se míří |
| zelená linka | právě hraný řádek |

Výběr lekce **zvýrazní relevantní vrstvu a ztlumí zbytek** (izolace konceptu).

## Kurikulum (11 lekcí, sylabus po blocích)

| blok | lekce |
|------|-------|
| **A · Cíle** | 1 Guide tóny (3/7) · 2 Akord-tóny na těžké · 3 Landing do dalšího akordu |
| **B · Stupnice** | 4 Chord-scales dle funkce · 5 Inside vs outside dominanty |
| **C · Ozdoby** | 6 Approach tóny · 7 Enclosure (obklíčení) · 8 Bebop stupnice |
| **D · Levá ruka** | 9 Vedení levé ruky · 10 Voicing textury |
| **E · Moll** | 11 Mollové ii–V–i (altered / frygická dom.) |

Každá lekce = výklad + preset (izolace) + `focus` (zvýraznění) + volitelné **A/B**.

## Architektura (moduly)

```
voice/
  harmony.py      changes -> per-takt chord-scale dle FUNKCE (lydian/dorian/mixo/
                  altered/phrygian-dom/locrian♮2/bebop…), chord_tones, guides (3/7)
  voicings.py     9 typů LH: root/root_vl/drop2/3/24/rootless + cluster I/II/III;
                  pevné tvary centrované (bez driftu), voice-leading u rootless
  build.py        builder CÍL+SPOJKA: 1. doba=guide voice-led -> arpeggio cílů ->
                  offbeat stupnicový fill / approach / ENCLOSURE; chord-tón na těžkou
  view.py         anotovaný klaviaturní náhled (tabule), škáluje oknem; focus
  lessons.py      11 lekcí (text + preset + focus + A/B), bloky A–E
  progressions.py dur/moll postupy (ii–V–I, iiø–V–i, kvintové kruhy…)
  render.py       linka + harmonie -> MIDI
  gui.py          Tkinter tabule: sylabus + náhled + A/B + menu (port/tempo/zobrazení)
  cli.py          generátor z příkazové řádky
```

### Klíčové principy

- **CÍL + SPOJKA:** linka se *staví* (ne náhodný walk) — cíle = guide/akordové tóny
  voice-led na doby, mezi ně přijdou spojky (stupnice / chromatický approach /
  enclosure). Žádná chromatika na silnou dobu (ověřeno).
- **Chord-scale dle funkce** (Levine): maj7→lydická, m7→dórská, V→moll→altered/
  frygická dominanta, iiø→lokrická ♮2; bebop = 8-tónová varianta (chord-tóny na těžkou).
- **Voicing bez driftu:** pevné tvary se centrují do stálého rejstříku (klaviatura
  neutíká); rootless se vede k předchozímu akordu (Evans A/B).

## Pokročilé (skryté v menu Zobrazení)

Generativní páky (density, approach, enclose, bebop, color, voicing, seed, akordy)
nastaví **lekce**; pokročilý uživatel je může doladit. Student je běžně nevidí —
lekce izoluje jeden koncept.

## Stav

Funkční; ověřováno headless i poslechem. Plán dál: blok F (frázování — prostor,
swing, motiv), avoid-note značení, cvičení nad reálnými standardy.
