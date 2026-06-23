# Design: Levine → výuková osnova (orchestrovaná lokální extrakce)

> Datum: 2026-06-23. Etapa 2 navazující na OCR korpus
> ([[2026-06-23-levine-ocr-corpus-design]]). Cíl: z textového korpusu vyrobit
> **strukturovanou výukovou osnovu** (graf konceptů) jako podklad pro interaktivní
> výukový SW. Veškerá jazyková práce běží **lokálně přes Ollama**; Claude (Claude
> Code) jen **orchestruje** a deterministicky skládá — žádné Claude kredity na objem.

## 1. Cíl
Z Levinova korpusu odvodit **co se učit a v jakém pořadí**: graf konceptů s
prerekvizitami, obtížností a odkazem na zdroj. Výstup je **naše původní formulace
a struktura** (fakta/metoda), ne Levinův text — software má jinou, interaktivní formu
než kniha. Osnova je páteř pro libovolný výukový SW (mapování na cvičení = další etapa).

## 2. Vstup
- Korpus: `~/OneDrive/Jazz Learning/Levine Corpus/` (čistý text z OCR pipeline, etapa 1).
- Rozsah knihy (ověřeno ze skenu — kanonická jazz-piano osnova, **24 oddílů**):
  Introduction; 1 Intervals & Triads; 2 Major Modes & II-V-I; 3 Three-Note Voicings;
  4 Sus/Phrygian Chords; 5 (II-V-I rozšíření)*; 6 Tritone Substitution; 7 *; 8 Altering
  Notes in LH Voicings; 9 Scale Theory; 10 Putting Scales to Work; 11 *; 12 So What
  Chords; 13 Fourth Chords; 14 Upper Structures; 15 Pentatonic Scales; 16 Voicings×3;
  17 Stride & Bud Powell Voicings; 18 *; 19 Block Chords; 20 Salsa & Latin Jazz;
  21 Comping; 22 Loose Ends; 23 Practice. (*titul z OCR neúplný — doplní se při běhu z textu.)
- OCR kvalita: ~80 % slovníkové shody (zbytek = jazzová terminologie); próza čitelná.

## 3. Rozsah
**V rozsahu:** chunking korpusu → per-okno extrakce konceptů (Ollama) → deterministické
sloučení/dedup → kritik pass (Ollama) → výstup `curriculum.json` + `curriculum.md`.
**Mimo rozsah:** mapování konceptů na cvičební materiály (drilly/Evans/Real Book) =
další etapa (zatím prázdný háček `practice[]`); samotné výukové UI.

## 4. Architektura
Orchestrátor (deterministický Python) řídí; lokální model (Ollama) dělá jazyk.
**Model nikdy nedostane víc, než se mu vejde do kontextu** — vždy jen malé okno.

```
Levine korpus (.md)
 [1] chunk           malá PŘEKRÝVAJÍCÍ se okna (dle num_ctx; ~1-2 strany, ~10-15 % překryv)
 [2] MAP  -> Ollama  per okno: JSON seznam konceptů (název, popis NAŠÍMI slovy, prereq, level, keywords)
 [3] REDUCE          deterministický dedup (normalizovaný název + podobnost) napříč okny -> jeden graf
 [4] ORDER           topologické pořadí dle prerekvizit (+ pořadí zdrojových stran jako tie-break)
 [5] CRITIC -> Ollama nad KOMPAKTNÍM seznamem (po dávkách): co chybí / cykly / nesmyslné pořadí -> opravy
 [6] OUTPUT          curriculum.json (graf) + curriculum.md (čitelná osnova)
```

## 5. Komponenty a rozhraní
- **`chunk_corpus(corpus_dir, max_chars, overlap) -> list[Chunk]`** — Chunk = `(text, source_ref)`;
  `source_ref` nese kapitolu/strany z page markerů. Okna malá, s překryvem.
- **`OllamaClient(model, num_ctx)`** s `.generate_json(prompt, schema_hint) -> dict` —
  HTTP volání Ollama `/api/generate` s `format: "json"`. Jediné místo, kde se mluví s modelem.
  Vyměnitelný (fake klient pro testy). `available() -> bool` (server běží + model je stažený).
- **`extract_concepts(chunk, client) -> list[Concept]`** — MAP nad jedním oknem.
- **`merge_concepts(list[list[Concept]]) -> list[Concept]`** — deterministický dedup + sloučení
  zdrojů/prerekvizit (normalizace názvu, fuzzy shoda nad prahem).
- **`order_concepts(concepts) -> list[Concept]`** — topologické řazení dle prerekvizit, detekce cyklů.
- **`critique(concepts, client) -> list[Concept]`** — kritik pass (po dávkách) → doplnění/oprava.
- **`write_curriculum(concepts, out_dir)`** — `curriculum.json` + čitelný `curriculum.md`.
- **`build_curriculum(corpus_dir, out_dir, client, ...)`** — orchestrace [1]→[6] + log + cache map výstupů.

## 6. Schéma uzlu konceptu (curriculum.json)
```json
{
  "id": "kebab-case-stabilní-klíč",
  "name": "Lidský název konceptu",
  "summary": "2-4 věty NAŠIMI slovy: co to je, k čemu/kdy se používá.",
  "level": "beginner | intermediate | advanced",
  "prerequisites": ["id-jiného-konceptu", "..."],
  "keywords": ["...", "..."],
  "source_refs": [{"chapter": "CHAPTER SIX", "pages": "p.84-89"}],
  "practice": []
}
```
`curriculum.md` = čitelný průřez: oddíly dle úrovně/pořadí, u konceptu název + summary +
prerekvizity + odkaz na kapitolu. Žádný citovaný text z knihy.

## 7. Model a Ollama
- Parametr `--model`; default **`qwen3.6:27b-mlx`** (nejlepší kvalita do 24 GB, MLX = rychlé),
  fallback **`gemma4`** (lehčí/rychlejší). Výběr po **A/B testu na 1 kapitole** (kvalita vs čas).
- `format: "json"` pro strukturovaný výstup; `num_ctx` nastavený podle velikosti okna.
- Hardware: M4 Pro, 24 GB. 19GB model je těsný, ale projde; gemma4 komfortní.

## 8. Autorská práva / úložiště
- **Kód** → repo `improved/levine_curriculum/`.
- **Výstup osnovy** → `~/OneDrive/Jazz Learning/Levine Corpus/curriculum/` (gitignored, jako korpus).
- Osnova = **původní formulace + struktura**, ne Levinův text. Cache map výstupů → `_work/` (gitignored).

## 9. Kvalita a robustnost
- Auto **critic pass** (pojistka úplnosti — hlavní riziko fully-auto) + **tvůj spot-check** výsledku.
- MAP cache per-okno → běh je resumable; chyba jednoho okna se zaloguje a přeskočí.
- Dedup deterministický (žádný velký kontext); critic po dávkách (kompaktní seznam).
- Pokud model vrátí nevalidní JSON → 1 retry s tvrdším promptem, pak skip okna s logem.

## 10. Testování (TDD)
- `chunk_corpus` (velikost/překryv/source_ref), `merge_concepts` (dedup, sloučení prereq),
  `order_concepts` (topo + detekce cyklu), JSON schema validace → unit testy se **syntetickými** daty.
- `OllamaClient` přes **fake klienta** (předpřipravené odpovědi) → testuje orchestraci/cache/critic
  bez reálného modelu.
- Reálná kvalita extrakce = malý běh na 1-2 kapitolách (A/B qwen vs gemma), ruční spot-check.

## 11. Mimo rozsah / další etapy
- Etapa 3: mapování `practice[]` na existující cvičení (drilly, simplified Evans, Real Book tunes).
- Etapa 4: interaktivní výukový SW nad osnovou (UI, průchod, sledování pokroku) — napojení na
  `improved/voice/` nebo nový front-end.
