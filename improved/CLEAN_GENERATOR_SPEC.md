# Čistý generátor — SPEC (branch `feature/clean-generator`)

Cíl: na základě starého konceptu (prototyp v `improved/`) napsat **jeden koherentní
melodický hlas** místo zoo buněk + tří modelů + 14 přepínačů. Plná unifikace.
Tenhle dokument je k odsouhlasení PŘED kódem.

## 1. Filozofie (čeho se držet)
- **Jeden model, jeden zdroj pravdy o melodickém pohybu.** Žádný base+blend+overlay+bandit.
- **Harmonie je dodaná při generování** → linka je vždy harmonicky platná konstrukcí.
- **Co slyšíš = model.** Feedback přímo tvaruje ten jeden model (volný drift, dle volby).
- **Málo os, každá slyšitelná.** ~5 ovladačů místo 14.
- **Konec záplat.** Heuristiky (`limit_leaps`, `no_repeats`, anti-aba, snap…) se vtáhnou
  do definice generátoru, ne jako post-hoc průchody.

## 2. Co z prototypu zachovat (má duši)
- Voice-led harmonie: rootless voicingy + min. pohyb hlasů + bas.
- Guide-tone landing (akord. tón na těžké/při příchodu do dalšího akordu).
- Pozičně/registrově podmíněné učení (increment 2) — jádro nového modelu.
- Feedback smyčka jako interakce (regeneruj → označ dobrý/lepší).
- Naučený Evansův pohyb jako prior = ten hlas.

## 3. Architektura (moduly)
Nový balík `improved/voice/` (pracovní název), čistá rozhraní:

- **`harmony.py`** — `Harmony(progression)` → per-takt `{bass, voicing[], scale_pitches[],
  guide_tones[]}`. Jeden voicing styl (rootless Evans) + voice-leading. Chord-scale
  **auto** z kvality akordu (žádný scale-type knob).
- **`melody.py`** — JEDEN kontextově podmíněný generátor + model (viz §4).
- **`render.py`** — (linka + harmonie) → MIDI (jeden track LH, jeden RH).
- **`feedback.py`** — sklad událostí (better/worse + kontext) + jak tvarují model. Volný
  drift: kde feedback má data, vlastní rozdělení; jinak prior.
- **`app/`** — slim fasáda + slim GUI (viz §6) + `cli.py`.

## 4. Jádro: unifikovaný melodický model
**Prostor:** model pracuje v **krocích po chord-scale (scale-degree)**, ne v půltónech.
→ harmonie je v VÝSTUPNÍM prostoru (každý tón leží ve stupnici akordu konstrukcí),
transpozičně invariantní, snap odpadá.

**Stav (kontext) na každém kroku** — s multi-level backoffem (jako CondPref):
- `metric`: pozice v taktu = {těžká, vnitřek, příchod-do-dalšího-akordu}.
- `register`: pásmo (nízko/střed/vysoko) + vzdálenost od krajů rozsahu.
- `contour`: poslední 1–2 kroky (markovská paměť).
- `degree` (volitelně, backoff): akordová role aktuálního tónu (kořen/3/5/7/tenze).

**Výstup:** rozdělení nad `další krok ve stupnici` (např. −3..+3) [v1 pevný rytmus z
hustoty]. Landing = stav-podmíněný tah k akord. tónu na těžké/příchodu — model se ho
NAUČÍ z Evanse (na příchodu Evans míří na 3/7), ne přes zvláštní `land_into`.

**Trénink (Evansův prior):** z přepisů spočítej pro každý tón kontext a krok → counts.
Robustně: prior je primárně `metric+register+contour` (degree backoff), aby ho
nepotopila šumná detekce akordů (poučení z prototypu). 

**Feedback (volný drift):** události uživatele přičtou/odečtou counts ve STEJNÉM modelu
(B↑/A↓, podlaha 0). Kde má kontext data, model je vlastní; jinak prior. Žádný overlay.

**Vzorkování:** backoff (nejkonkrétnější kontext → obecnější), teplota = „dobrodružnost".
Drobné tvrdé pojistky (neopakuj tón 2×) zůstanou jako součást vzorkování, ne průchod.

## 5. Rytmus (v1)
Pevná mřížka z **hustoty** (1/2/3/4 noty/dobu) + **feel** (rovně/swing). Naučený rytmus
(model emituje i délku) = pozdější krok, ne v1. (V prototypu byl rytmus stejně skoro
pevný.)

## 6. Ovládání (~5 os, každá slyšitelná)
1. **Progrese** (akordy).
2. **Hustota** (noty/dobu).
3. **Dobrodružnost** (teplota modelu).
4. **Registr** (rozsah / střed).
5. **Zdroj stylu** (Evans prior ↔ ty: váha feedbacku vs prior).
   (+ volitelně **Feel**: rovně/swing.)

## 7. Co se ZAHODÍ (a proč)
- Typy buněk `run/scale/arpeggio/markov` + jejich slidery → jeden model.
- `alpha` + `partner` (duplicitní ovládání „stylu") → zdroj stylu = prior+feedback.
- `scale-type`, `voicing-type`, `in_four`, `count` → auto z akordu / jeden dobrý default.
- `MotionMarkov` + `BlendMarkov` + `CondPref` (tři modely) → JEDEN model (§4).
- Záplatové průchody → vtaženo do generátoru.

## 8. Co reálně přenést z `improved/` (port, ne přepis)
- voicingy + voice-leading + guide tóny + parse akordů (z `voicings.py`/`scale_drill`/
  `arrange_chords`).
- MIDI render (z `scale_drill.render_*`).
- vzor skladu feedbacku + perzistence (z `gui_backend`).
- nápad náhledového plátna a regeneruj/feedback interakce z `gui.py` (zeštíhlený).

## 9. Fáze stavby (po schválení SPEC)
1. **SPEC** (teď).
2. `harmony` + `render` + triviální generátor → slyšet harmonii.
3. **`melody`**: Evansův prior + generování v scale-degree → slyšet hlas.
4. `feedback`: tvarování modelu (volný drift) + interakce.
5. slim GUI nad slim fasádou (~5 os).

## 10. Rozhodnutí (ODSOUHLASENO)
- **A. Prostor modelu: scale-degree** (kroky ve stupnici). ✅
- **B. Harmonie pro prior: PŘIBLIŽNÁ DETEKCE akordů** i pro Evansův prior → prior je
  degree-podmíněný. Využít stávající detekci (`concept/.../harmony.py` Krumhansl+Viterbi).
  Šum ošetřit multi-level backoffem (degree → bez degree). ✅
- **C. Rytmus v1: pevná mřížka** z hustoty (+feel). Učený rytmus = pozdější. ✅
- **D. Balík: `improved/voice/`.** ✅
- **E. GUI náhled: zachovat klaviaturový** (ztenčit, ne nahradit). ✅

Pozn. k §4 dle B: stav modelu zahrnuje `degree` jako PLNÝ člen kontextu (ne jen
volitelný), s backoffem `(metric,register,degree,contour) → (metric,register,contour)
→ …` pro robustnost vůči šumu detekce.
