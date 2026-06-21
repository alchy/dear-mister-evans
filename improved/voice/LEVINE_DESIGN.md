# Virtuální Mark Levine — interaktivní výukový software

**Co to je:** ne (jen) generátor, ale **výukový program**, kde *virtuální Mark Levine
učí jazzovou improvizaci interaktivně* — ne výkladem z knihy, ale tak, že koncept
**vysvětlí, předvede (zahraje + ukáže), necháš si to zkusit a dostaneš zpětnou vazbu**.
Generátor (naše kostra `voice/`) je **demonstrační motor**: umí vyrobit linku, která
daný koncept *izoluje a zvýrazní*. Naučený Evans = vkus/styl příkladů.

Tohle je blueprint k odsouhlasení; pak to naimplementujeme na `voice/`.

## 1. Pedagogická smyčka (jádro)
Každý koncept se učí stejnou interaktivní smyčkou:

1. **VYSVĚTLI** — Levine řekne princip krátce a konkrétně (text v okně).
2. **PŘEDVEĎ** — program vygeneruje příklad, který koncept *izoluje*, **přehraje** ho
   a v **klaviaturovém náhledu ho ANOTUJE** (guide tóny zvýrazní, approach/enclosure
   označí, chord-tóny na těžké zvýrazní).
3. **A/B SLYŠ ROZDÍL** — toggle koncept ON/OFF a přehraj obojí (např. „s approach tóny"
   vs „bez"), ať uši samy slyší, co koncept dělá.
4. **ZKUS** — interaguj: regeneruj, změň parametr, nebo *call-and-response* (Levine
   zahraje 2 takty, ty odpovíš / vybereš lepší pokračování).
5. **ZPĚTNÁ VAZBA** — Levine okomentuje (pravidla: chord-tón na těžké? landing na 3/7?
   leap rozveden?) a tvůj výběr **tvaruje vkus modelu** (volný drift) i tvůj postup.

## 2. Kurikulum (Levinovy koncepty, v pořadí = lekce)
Každá lekce = výše uvedená smyčka nad jedním konceptem:

1. **Guide tones (3 a 7)** — definující tóny; guide-tone linka přes changes.
2. **Chord-scales** — jaká stupnice ke které kvalitě/funkci.
3. **Bebop stupnice** — přidaný průchod → *chord-tóny padnou na těžkou* (motor osmin).
4. **Chord-tóny na těžké** — proč to „zní jako akord".
5. **Approach notes** — půltónové přiblížení na cíl.
6. **Enclosure (obklíčení)** — obklop cíl shora+zdola.
7. **ii–V–I** — cílení 3/7, voice-leading přes spoj.
8. **Rootless voicingy (A/B)** — levá ruka, voice-leading, tenze.
9. **Avoid notes** — kam na těžkou nedosedat.
10. **Altered dominanta** — V→i moll, napětí a rozvod.
11. **Anticipace & prostor** — nech to dýchat, tón před dobou.
12. **Motiv** — řekni téma, zopakuj, rozviň.

## 3. Demonstrační motor = gramatika CÍL + SPOJKA (řízená lekcí)
Linka se **staví** (ne náhodný walk), aby šla koncept izolovat:
- **Cíle:** guide tóny (3/7) na změnách/silných dobách, voice-led = páteř.
- **Spojky mezi cíli:** `scalar(bebop) | chromatic approach | enclosure | arpeggio` —
  výběr/tvar **váží Evans vkus** + parametry lekce.
- **Lekce nastavuje parametry generování** = „izolace konceptu":
  - lekce *guide tones* → jen cíle, minimum spojek;
  - lekce *approach* → vždy chromatický náběh na cíl (a ON/OFF pro A/B);
  - lekce *enclosure* → obklíčení zapnuté; *bebop* → zdůrazni průchod na těžké; atd.
- **Tvrdé constraints (Levine):** chord-tón na těžké, avoid-note jen průchod,
  leap→krok, do dalšího akordu přijď na 3/7 půltónem.

## 4. Harmonie — kontextově (Levine)
Chord-scale podle FUNKCE: maj7→Lydická; m7→Dórská; 7→Mixo/bebop-dominant (→dur) nebo
**Altered** (→moll); m7b5→Lokrická ♮2; dim7→zmenšená. **Bebop** stupnice = chord-tóny
na těžkou. **Rootless A/B voicingy** + tenze (alterace na dominantě). **Avoid notes**
značené (nelandovat na těžkou).

## 5. Klaviaturový náhled = TABULE
Zachovaný klaviaturový náhled, ale **anotovaný pro výuku**:
- guide tóny (3/7) zvýrazněné jinou barvou,
- approach/enclosure tóny označené (šipka/kroužek),
- chord-tóny na těžké zvýrazněné,
- avoid-note varovně.
Plus **textový výklad Levina** vedle a tlačítka A/B přehrání.

## 6. Interaktivita (Levine učí, ne přednáší)
- **Koncept toggle** (ON/OFF + přehraj rozdíl).
- **„Proč?"** — Levine vysvětlí, co v příkladu zaznělo.
- **Call-and-response** — Levine 2 takty, ty odpověz (regeneruj / vyber).
- **Feedback** = i výuka: tvůj výběr „lepší/dobrý" tvaruje vkus a posune lekci.
- **Postup kurikulem** (další koncept staví na předchozím).

## 7. Mapování na kostru `voice/`
- `harmony.py` — changes → voicingy + **kontextové** chord-scales + guide + avoid (rozšíření).
- `melody.py` — **builder cíl+spojka** řízený parametry lekce; Evans = vkus výběru.
- `render.py` — beze změny (linka+harmonie → MIDI).
- `lessons.py` (nové) — obsah lekcí: text výkladu + parametry generování (izolace konceptu)
  + anotační pravidla (co v náhledu zvýraznit).
- `gui.py` — **třída/tabule**: výběr lekce, výklad, anotovaný náhled, A/B přehrání,
  koncept toggly, call-and-response, feedback. (~5 generativních os zůstává jako „pokročilé".)

## 8. Fáze implementace (na kostře)
② harmonie kontextově (chord-scales dle funkce, guide). ✅
③ builder cíl+spojka (skeleton guide tónů → fill connectory) + anotace. ✅ (Evans vkus zatím ne)
④ `lessons.py`: lekce = text + izolační parametry + anotace. ✅ **11 lekcí** (bloky A–E)
⑤ GUI-tabule: výklad + anotovaný náhled + A/B + focus. ✅ (feedback OPUŠTĚN — teorie-first)

**Stav 2026-06-21 (mergeno do main):** harmonie+voicingy (9 typů vč. cluster I/II/III),
builder s enclosure + bebop stupnicí (žádná chromatika na těžkou), 11 lekcí + focus
zvýraznění, landing popisek 3/7, fialová chromatika. GUI: sylabus po blocích, port/tempo/
flip/pokročilé v menu. **Dál:** blok F (prostor/swing/motiv), avoid-note, reálné standardy.

## 9. Co zůstává z dohod
Jeden koherentní hlas, málo os, feedback = volný drift (teď i jako *výuka*). Scale-degree
prostor pro spojky; chromatika/approach se vrací **principiálně** (Levinova výtka #1).
