# Pedagogika a muzikálnost — pro výukový program (virtuální Levine)

Parafráze z jazzových zdrojů (viz Zdroje). Dva účely: (a) jak generovat *muzikální*
příklady (frázování, rytmus, motiv), (b) jak **strukturovat výuku** (kurikulum +
tutor smyčka + hodnocení). Doplňuje [LEVINE_DESIGN.md](LEVINE_DESIGN.md).

## Muzikálnost → parametry generátoru
**Frázování & prostor:** ticho je nota; fráze ~ „na jeden nádech" (1–2 takty), pak
pauza; začínej mimo těžkou (na „and"/předtaktí); fráze přes taktovou čáru;
otázka↔odpověď (otázka končí napětím, odpověď rozvodem); asymetrie (krátká fráze,
delší ticho); měň délky not.
→ délka fráze ~ geom. (mean ~1–2 takty) + úměrná pauza; vnitřní pauza s prav. *p*;
start na „and" s prav. *q*; střídej režim otázka(konec na napětí)/odpověď(rozvod na chord-tón).

**Rytmus & feel:** swingové osminy na triolové mřížce (long-short ~2:1 pomalu →
téměř rovné rychle); synkopa = akcent na „and"; **anticipace** = cíl o osminu dřív
(přivázat); rytmické posunutí (stejný rytmus, jiná doba); micro-timing (za/na/před dobou).
→ swing ratio dle tempa; akcent „and" s *p*; anticipace posun o osminu s *p*; globální
± offset (za beatem = uvolněně) + jitter.

**Motivický vývoj:** řekni motiv (2–3 tóny) → opakuj přesně přes jiné akordy →
sekvencuj (diatonicky/chromaticky) → transformuj (augmentace/diminuce, inverze,
retrográd, fragmentace, přidej chromatické soused. tóny) → otázka/odpověď.
→ *motif buffer*; per slot losuj akci: opakuj / sekvencuj o interval / transformuj /
odpověz (zrcadli a rozveď na chord-tón) / nový motiv. Landing na chord-tón na těžké.

## Kurikulum (pořadí konceptů, ověřeno)
1. Poslech (sound do ucha). 2. Melodie tématu uchem (zpívej zpaměti). 3. 4 kvality
7-akordů + changes. 4. Sluch/audiace. 5. Improvizace **jen chord-tóny**, landing na
silné doby. 6. **Guide-tone linky** (3/7). 7. Stupnice/mody ukotvené k harmonii.
8. ii–V–I pomalu ze všech stupňů, postupně rychleji. 9. Transkripce krátkých frází
(zpívej → hraj → analyzuj → transponuj). 10. Jazyk/licky (abstrahuj koncept).
11. **Prostor a zdrženlivost** (dril: 1 takt hraj, 3 ticho). 12. Celé skladby.
Zásada „less is more": začátečníci přehrávají; cvič i pauzy.

## Tutor smyčka (jedna lekce)
1. **VYSVĚTLI** krátce: jeden koncept + jeden měřitelný cíl.
2. **PŘEDVEĎ** („já"): zahraj 2–4 takty nad trackem + jednovětý think-aloud.
3. **OMEZ prostředí**: pevné pomalé tempo, malá množina tónů, krátká délka, klik na 2 a 4.
4. **ZKUS** („spolu" → „ty"): nejdřív echo/asistovaně, pak samostatně.
5. **ZPĚTNÁ VAZBA**: konkrétní, k cíli — (a) co fungovalo, (b) jedna oprava s „proč",
   (c) další krok. Nikdy jen „dobrý".
6. **POSUN** až po prahu (~80 % / N úspěchů za sebou); pak povol **jednu** osu
   (přidej tón / zrychli / prodluž frázi / přidej akord). Občas vrať starší cíl.
Princip „I do / we do / you do"; call-and-response (tutor zahraje, ty odpověz, pak role prohoď).

## Hodnocení pokusu (MIDI)
- **Time/feel** (priorita): průměrná |odchylka nástupu| od mřížky + konzistentní za/před.
- **Množina tónů**: % not v povolené paletě / chord-tóny vs avoid notes.
- **Prostor/hustota**: not/takt + podíl ticha vs cílové pásmo (varuj přehrávání).
- **Landing**: dosedl tón na požadovanou dobu? (binárně per takt).
- **Call-response**: edit distance intervalů + kvantovaného rytmu vůči výzvě.
- **Skoky**: velké skoky, když lekce cílí krok (mapuje na engine `limit_leaps`).
- **Brána**: složené pass/fail, N úspěchů za sebou pro posun; nejhorší dílčí skóre →
  do další zpětné vazby (ať je konkrétní).

## Časté chyby učícího se (na co upozorňovat)
Přehrávání (hustě, rychle, bez ticha); ignorování času/feelu; teorie bez ucha;
neposlouchání kapely (monolog); bez melodického záměru; cvičení moc rychle;
neinternalizovaná skladba / rozptýlení na moc věcí.

## Zdroje (výběr)
- learnjazzstandards.com — Phrasing & space; Jazz improvisation made simple
- jazzadvice.com — Exploring space; Musical phrasing; Rhythmic principles of Charlie Parker;
  Jazz improvisation ultimate guide; 15 mistakes beginners make; Transcribing tips; Sing every day
- pianogroove.com — Question & answer / call & response
- learnjazzstandards.com (podcast) — Motivic development
- jazzpianoschool.com / Open Music Theory — Swing feel
- learn2playjazz.com — Rhythmic displacement; mypianoriffs.com — Anticipations
- structural-learning.com — I do/we do/you do; Deliberate practice; ASCD — Feedback
