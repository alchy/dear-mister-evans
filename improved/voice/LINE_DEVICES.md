# Stavba linky — zařízení (pro builder cíl+spojka)

Parafráze z jazzových lekcí (viz Zdroje), převedené na pravidla generátoru. Rámec:
linka = **CÍLE** (guide tóny 3/7 na silných dobách) spojené **SPOJKAMI** typu
`scalar / approach / enclosure / arpeggio`. Doplňuje [TIPS_WEB.md](TIPS_WEB.md).

## Approach (1 tón před cílem, na „and" před dobou)
4 druhy podle směru a chromatiky (cíl = T):
- chromaticky zdola (T−1 půltón), chromaticky shora (T+1 půltón),
- diatonicky zdola (krok stupnice pod T), diatonicky shora (krok nad T).
Pravidlo: **cíl na těžkou, approach na předchozí „and".**
→ spojka `approach` délky 1.

## Enclosure (obklíčení cíle, T je poslední a na dobu)
Časté vzorce (offset vůči T):
1. diatonicky-nad → chromaticky-zdola → T (klasický bebop wrap, 3 tóny),
2. chromaticky-nad → chromaticky-zdola → T (těsnější, „outside"),
3. nad → pod → T (obecný 2-obal), i pod → nad → T,
4. dvojitá chromatika zdola: T−2, T−1, T (i shora: T+2, T+1, T).
→ spojka `enclosure` = krátká šablona z malé knihovny, končí přesně na T.

## Guide-tone linka přes ii–V–I (páteř cílů)
Guide tóny = 3 a 7; vedou se **minimem pohybu**: 7 akordu klesne o půltón na 3
dalšího (řetěz 7→3→7, resp. 3→7→3), nebo společný tón drží.
Příklad C (Dm7–G7–Cmaj7): linka 3→7 = F (3 Dm7) → F (7 G7, společný) → E (3 Cmaj7).
→ kostra cílů: per akord vyber cíl ∈ {3, 7}, ten co je společný tón / půltón od
předchozího (preferuj krok dolů). Spojky vyplní mezery.

## Digitální vzory / buňky (jako spojky/arpeggia)
Ve stupních aktuálního akordu: `1-2-3-5` (vzestup na 5), `3-5-6-8`, `5-3-2-1`
(sestup na 1), `1-2-3-♭2` (na 3 s chromatickým náběhem); mistr-spojka =
**arpeggio nahoru (1-3-5-♭7) → sestup bebop stupnicí** na guide tón dalšího akordu
(přidaný bebop průchod drží chord-tóny na těžké). Nad dominantou: zmenšené arpeggio
od ♭9 (altered barva).
→ spojka `arpeggio`/`scalar` = šablona stupňů, začni u předchozího cíle, skonči na dalším.

**Sekvencované fragmenty** (motivický běh): opakuj krátký vzor posunutý o stupeň
(`CDEF-DEFG-EFGA`) místo lineárního běhu → melodický tvar. **Gradace**: dynamicky
stupňuj k vrcholovému tónu. Běh = **pojivo mezi cíli**, ne ozdoba — má rytmus, cíl a
mezi frázemi ticho.
→ `scalar` spojka: varianta „sequence" (posun fragmentu) + dynamická obálka; vždy končí na cíli.

## Targeting + anticipace
Na změně akordu miř na **3 nebo 7** nového akordu, dosedni na **silnou dobu (1, 3)**.
**Anticipace**: dosedni na guide tón dalšího akordu už na **„and" 4. doby** (přivázat
přes taktovou čáru) → „stane se" novým akordem dřív, swingový spád.
→ plánovač: per akord guide-tón cíl na silnou; flag `anticipation` posune cíl o osminu dřív.

## Skladba (souhrn pro generátor)
```
CÍLE      = guide-tone páteř (3/7, silné doby, půltón/společný tón, příp. anticipace)
SPOJKY mezi sousedními cíli, typ:
  scalar     – běh chord/bebop stupnice (průchod drží chord-tón na těžké)
  approach   – 1 tón (chromatika/diatonika, nad/pod) na „and" před cílem
  enclosure  – 2–4 tónová šablona obalu končící na cíli
  arpeggio   – digitální buňka (1235, 3568, 5321, arp→sestup-bebop, dim cell)
```
Výběr/tvar spojky váží naučený Evans vkus + osa inside↔outside + parametry lekce.

## Slovník = teoretická zařízení, NE (jen) Evans
Primární vokabulář builderu jsou **teoreticky odvozená zařízení** (approach/enclosure/
digitální buňky/bebop běhy, idiomy ii–V–I dur i moll), ne opsané licky ani závislost
na Evans prioru. Knihovna spojek je **seedovaná z teorie** (funguje i bez jakýchkoli
dat). **Evans prior = volitelná vrstva vkusu** (váží výběr/tvar), kterou lze vypnout
nebo nahradit feedbackem uživatele. Mistrovské licky se NEkopírují (copyright) — z nich
bereme jen *kategorie zařízení* (obklíčení 3, bebop sestup, 1235, altered arpeggio).

## Zdroje
- antonjazz.com — Approaches and Enclosures
- jazzlessonvideos.com — 15 Approach Note and Enclosure Exercises
- learnjazzstandards.com — Use Guide-Tones to Navigate Chord Changes
- pianowithjonny.com — Guide Tones: The Complete Guide
- fundamental-changes.com — Combining Arpeggios with the Bebop Scale; Chromatic Approach Notes
- pianogroove.com — Targeting the 3rds; jazzetudes.net — Targeting Chord Tones
- jefflewistrumpet.com — Jazz Licks in 12 Keys (jen kategorie zařízení ii–V–I dur/moll; licky nereprodukovány)
