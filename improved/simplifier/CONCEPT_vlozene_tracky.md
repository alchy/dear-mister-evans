# Koncepční dokument: Simplifikace vložených tracků

> Handoff pro příští session. Cíl: zobecnit simplifikaci z Evans Jazz Jane na
> **libovolný vložený MIDI track** a zajistit robustní, kvalitní výstup.

## 1. Cíl
Vzít LIBOVOLNÉ vložené MIDI → vyrobit **zjednodušenou verzi**: akord + zpívající
melodie, ve výukových obtížnostech, **dvouruční formát** (RH melodie / LH comp+bas)
+ stopa akordů — připravené pro Synthesia / trénink modelu / případně výukové SW.

Tedy: aby si uživatel mohl vložit *jakoukoli* skladbu a dostal „simplified" verzi
ve stejné kvalitě, jakou teď máme na Evansovi.

## 2. Stav (co máme — funguje na sólo jazz piánu)
Balík `improved/simplifier/`:
- `io_midi` + `beats` — onsety v reálném čase + rubato beat-tracking (DP).
- `meter` — dynamické downbeaty z harmonického rytmu.
- `voices` — skyline split: melodie (vrch) vs harmonie (spodek).
- `chords` — Viterbi akordy na SPODKU (bas=kořen prior, funkční přechody, ne bass=root pro chroma).
- `melody` — čistý lead line (oktávové glitche pryč, ořez konce).
- `functional` — ii-V-I / ii-V / turnaround přes klesající kvinty.
- `simplify` — `render_simplified` / `LEVELS` (simplified1=beginner, simplified2=advanced) /
  `build_simplified` / `segment_progressions`.

**Zafixované parametry** (laděno poslechem): comp = R-3-5-7 voice-led (`root_vl`);
beginner = mel_keep 0.5, jednohlas; advanced = mel_keep 0.85 + funkční zdvojení reálnými
tóny ze zdroje (jen v chord-scale, podle funkce guide 3/7 > tenze, jen při jistotě ≥ 3.8).

## 3. Klíčová výzva: ROBUSTNOST na libovolný vstup
Test na cizích jazz transkripcích ukázal, že yield/kvalita kolísá. Příčiny:

| faktor | dopad |
|---|---|
| **Textura** | hustá sólo improvizace (Evans) → super; lead-sheet / cover / kvantované / monofonní → slabší |
| **Detekce akordů** | spolehlivá hlavně tam, kde je DRŽENÉ comping (spodek). Na tenké/jednohlasé faktuře nemá z čeho číst → šum → rozbité funkční celky |
| **Beat-tracking** | rubato OK; extrémní tempo změny / ad-lib intro bez metra → nutno označit „bez metra" a přeskočit |
| **Garbage-in** | špatný akord → i plynulá melodie zní špatně (garbage-out) |

Závěr z minula: *nástroj je laděný na Evansův typ; generalizace stojí hlavně na
robustnosti detekce akordů.*

## 4. Co je třeba ZAJISTIT (požadavky na příští session)

### 4.1 Klasifikace vstupu
Před analýzou rozpoznat **typ tracku** a podle toho volit strategii:
- sólo piano (hustá faktura) → současná pipeline,
- lead + comp (oddělené kanály/stopy) → využít existující split rukou,
- monofonní linka (melodie bez harmonie) → harmonii ODVODIT z linky,
- vícekanálové / aranž → vybrat relevantní stopy.
Detekce: počet kanálů/stop, polyfonie, rozsah, hustota, poměr spodek/vrch.

### 4.2 Robustní detekce akordů (hlavní páka)
- **Když je držené comping** → současný přístup (chroma ze spodku, Viterbi, funkční přechody).
- **Když je faktura tenká/monofonní** → fallback: odvodit harmonii z melodické linky
  (akordové tóny na těžkých dobách, kontury arpeggií, funkční prior).
- **Semi-automat**: umožnit **ruční zadání / opravu akordů** (lead sheet) — když je
  potřeba jistota; tool pak jen zarovná a simplifikuje.
- **Confidence**: skórovat detekci (vysvětlená hmota harmonie) a uživateli říct,
  kde si není jistá.

### 4.3 Využití struktury vstupu
- Pokud má MIDI **oddělené ruce/kanály** (RH/LH), použít to místo skyline splitu
  (přesnější melodie i harmonie).
- Respektovat **time-signature / tempo mapu** vstupu, pokud je validní (ne jen flat 120).

### 4.4 Validace kvality (důvěra ve výstup)
- Metriky bez ground truth: vysvětlená hmota harmonie, melody-fit do chord-scale,
  poměr funkčních (rozvazových) progresí.
- Výstup: per-track / per-úsek **skóre kvality** → „tahle skladba vyšla / nevyšla /
  vyžaduje ruční akordy".

### 4.5 Parametrizace (už máme základ)
- Obtížnosti (beginner/advanced) — `LEVELS`.
- Voicing styl (root_vl, drop, cluster…) — `kind`.
- Míra simplifikace melodie (`mel_keep`), zdvojení (`mel_voices`, `mel_conf`).
- Harmonický rytmus (hrubší/jemnější) — TODO regulátor.

## 5. Architektura (návrh toku)
```
vložený MIDI
   │
 [0] KLASIFIKACE vstupu (sólo / lead+comp / monofonní / aranž; kanály, polyfonie)
   │
 [1] ADAPTIVNÍ ANALÝZA
   │   beat-tracking (rubato / respekt k tempo mapě)
   │   melodie vs harmonie (skyline NEBO oddělené ruce, dle typu)
   │   akordy: chroma-ze-spodku  |  fallback z linky  |  ruční zadání
   │   -> + CONFIDENCE skóre
   │
 [2] SIMPLIFIKACE (LEVELS: beginner/advanced; voicing; mel_keep/voices/conf)
   │
 [3] EXPORT dvouruční MIDI (RH/LH) + chord markery (+ skóre kvality)
   │   volitelně: segmentace na progrese-chunky
```

## 6. Otevřené otázky
- Jak spolehlivě **automaticky klasifikovat** typ vstupu?
- Jak dobře jde **odvodit harmonii z monofonní linky** (a kdy raději chtít ruční akordy)?
- UX pro **ruční opravu akordů** (kde to vezme do appky / CLI)?
- Práh **confidence**, pod kterým track odmítnout / označit „vyžaduje zásah"?
- Batch processing složky vložených tracků + report kvality.

## 7. Konkrétní první kroky (příští session)
1. **Klasifikátor vstupu** (heuristika: kanály, polyfonie, hustota, rozsah) — vrátí typ + doporučenou strategii.
2. **Fallback detekce akordů z linky** pro monofonní/tenké vstupy; A/B vs současný detektor.
3. **Per-track confidence skóre** + odmítací práh; report při batchi.
4. (Volitelně) **ruční zadání akordů** jako vstupní parametr (`--chords`), tool zarovná + simplifikuje.
5. Otestovat na **různorodém setu** (ne jen jazz piano) a změřit yield/kvalitu.

## 8. Reference
- Stav projektu a rozhodnutí: viz paměť `dear-mister-evans-simplifier`.
- Hlavní deliverable zatím: simplified Evans korpus (`OneDrive/Jazz Learning/Evans Simplified/simplified1|2/`).
- Pozn.: výuka přes `voice/` se nedělá — uživatel vystačí se simplified MIDI + Synthesia.
  Tento dokument je o GENERALIZACI simplifikace na libovolné vstupy.
