# Design: OCR korpus z Levinovy *The Jazz Piano Book*

> Datum: 2026-06-23. Cíl: z naskenované knihy vyrobit čistý **textový/metodický
> korpus** jako podklad pro učící nástroj „podle autentického Levina".
> Etapa 1 (tento spec): **OCR → čistý markdown po kapitolách**. Strukturování
> (kapitoly→sekce→koncepty) je samostatná pozdější etapa.

## 1. Cíl
Vzít uživatelovu vlastní skenovanou kopii Levinovy knihy a získat z ní spolehlivý,
čitelný **text** (próza: koncepty, terminologie, pořadí témat, vysvětlení, struktura
kapitol). Z toho se v další etapě postaví kurikulum/obsah učícího nástroje.

Použití je **osobní/studijní** nad vlastní kopií. Tomu odpovídá i nakládání s výstupem
(viz §8): kód do repa, text knihy **nikdy** do gitu.

## 2. Zdroj (ověřená fakta)
- Soubor: `~/OneDrive/Jazz Learning/The Jazz Piano Book - PDF Room.pdf`.
- **316 stran**, skenováno (Creator „CanoScan", Producer „Adobe Acrobat 6.0 Paper Capture").
- **Bez textové vrstvy** (0 znaků na vzorových stranách 10/60/160/260) → OCR nutné.
- Skeny: 300 dpi, bitonální (1-bit gray), ~2552×3312 px, JBIG2. Dobrá kvalita pro OCR textu.
- Kniha obsahuje hodně **notového zápisu** — ten se NEřeší (text-only korpus, viz §3).

## 3. Rozsah
**V rozsahu (etapa 1):**
- Render stran PDF na obrázky.
- OCR prózy do textu, s vyměnitelným enginem.
- Sešití do správného pořadí čtení + segmentace na kapitoly.
- Čištění (dehyfenace, odstranění živých záhlaví/zápatí a čísel stran, normalizace).
- Výstup: **markdown po kapitolách**.

**Mimo rozsah (pozdější etapy):**
- OMR (notové příklady jako hratelná data) — neřešíme, překrývá se s MIDI pipeline.
- Strukturovaný korpus (JSON kapitola→sekce→koncept, prerekvizity) — samostatný spec.
- Samotný učící nástroj / jeho UI.

## 4. Architektura
Pipeline s **odděleným OCR krokem** (lze vyměnit engine bez zásahu do zbytku):

```
PDF (316 str)
  │
[1] render_pages   PDF -> page-NNN.png (cache na disku)
  │
[2] ocr_engine     batch obrázků -> markdown text   (PLUGGABLE: baidu | tesseract)
  │                 (cache výstupu po dávkách -> resumable)
  │
[3] assemble       per-dávka text -> jeden proud, reading-order, page markery
  │
[4] segment        rozdělení na kapitoly podle detekovaných nadpisů
  │
[5] clean          dehyfenace, záhlaví/zápatí ven, normalizace -> finální markdown
  │
výstup: <OneDrive>/Jazz Learning/Levine Corpus/NN-<kapitola>.md
```

## 5. Komponenty a rozhraní
Každá komponenta má jednu odpovědnost a čisté rozhraní, jde testovat zvlášť.

- **`render_pages(pdf_path, out_dir, dpi, page_range) -> list[Path]`**
  Vyrenderuje stránky na PNG (poppler `pdftoppm` přes subprocess; pymupdf není ve venv).
  Idempotentní: existující stránky přeskočí.

- **`OcrEngine` (rozhraní)** — kontrakt pro [2]:
  - `available() -> bool` — je engine nainstalovaný/spustitelný?
  - `max_pages -> int` — kolik stran zvládne v jedné dávce (Baidu ~40, Tesseract 1).
  - `ocr_batch(image_paths: list[Path]) -> str` — vrátí markdown text dávky.
  Implementace:
  - `BaiduEngine` — Unlimited-OCR, jeden průchod přes dávku (drží reading-order).
  - `TesseractEngine` — per-strana smyčka, konkatenace (fallback).
  Driver volá engine po dávkách dle `max_pages`, **cachuje** výstup dávky na disk
  (klíč = engine + rozsah stran + hash obrázků) → běh je resumable.

- **`assemble(batch_texts) -> str`** — spojí dávky do jednoho proudu, vloží page markery
  (`<!-- p.NNN -->`) pro pozdější dohledání zdroje.

- **`segment_chapters(text) -> list[(title, body)]`** — rozdělí podle detekovaných
  nadpisů kapitol (heuristika na vzor nadpisu + číslo). Když detekce selže, vrátí
  jeden celek (lepší než špatně rozsekat).

- **`clean(text) -> str`** — dehyfenace na konci řádku, odstranění opakujících se
  živých záhlaví/zápatí a čísel stran, normalizace mezer/odstavců.

- **`build_corpus(pdf, out_dir, engine, ...)`** — orchestrace [1]→[5], reporty/log.

## 6. Tok dat
PDF → PNG stránky (cache) → markdown po dávkách (cache) → spojený proud s page
markery → kapitoly → vyčištěný markdown soubor na kapitolu v OneDrive.

## 7. Volba enginu: spike napřed
Engine je rozhodnutí s rizikem, proto **spike-first**:
1. **Spike Baidu Unlimited-OCR na ~5 stranách** — rozjet na Macu (Apple Silicon),
   změřit kvalitu textu i rychlost/stránku. Baidu je 1 den starý (vyšlo 2026-06-22),
   takže ověřit reálnou dostupnost (HF Transformers + MPS, příp. Ollama/llama.cpp GGUF).
2. **Když spike projde** (kvalita dobrá, rychlost únosná) → Baidu na celou knihu.
3. **Když je moc syrový** → `TesseractEngine` beze změny zbytku pipeline.
4. Cloud (Mathpix) jen jako poslední možnost — nahrává knihu ven, nedoporučeno.

Kritéria spike (objektivně): čitelnost prózy bez zásadních chyb, zachované odstavce,
únosný čas (řádově umožní 316 stran v rozumném okně), žádné padání toolingu.

## 8. Kam co patří (autorská práva)
- **Kód pipeline** → repo `improved/levine_corpus/` (commitne se).
- **OCR výstup (text knihy)** → `~/OneDrive/Jazz Learning/Levine Corpus/` (lokálně,
  osobní). **Nikdy do gitu.** Přidat do `.gitignore` ochranu (`*Levine Corpus*`,
  výstupní cesty), aby se text omylem nedostal na GitHub.
- Rendrované stránky a cache OCR → mimo repo (temp / OneDrive), taky gitignored.

## 9. Ošetření chyb a robustnost
- Chybějící engine → `available()` to zachytí předem, jasná hláška + nabídnout fallback.
- Selhání OCR jednotlivé dávky → zaloguj, přeskoč, pokračuj (neshazuj celých 316 stran);
  na konci report, které stránky chybí.
- Resumable: cache stránek i dávek → opakovaný běh dělá jen chybějící.
- Segmentace kapitol nejistá → raději nerozsekat než rozsekat špatně (degradace na 1 celek).

## 10. Testování (TDD)
- **Čisticí funkce** (`clean`, dehyfenace, odstranění záhlaví/zápatí): unit testy nad
  **syntetickým** textem (ne nad knihou) — deterministické, žádný copyright v testech.
- **Segmentace kapitol**: testy nad syntetickým textem s vzory nadpisů.
- **Driver/cache/assemble**: `FakeEngine` vracející předpřipravený text → ověří dávkování,
  cache/resumability a sešití bez reálného OCR.
- **Kvalita reálného OCR**: ověřuje **spike** ručně na 5 skutečných stranách (exploračně,
  ne automaticky). Po plném běhu namátková kontrola vybraných kapitol.

## 11. Otevřené body / další etapy
- Etapa 2: strukturování textu na kurikulum (kapitola→sekce→koncept, pořadí, prerekvizity).
- Etapa 3: napojení korpusu na učící nástroj (mimo tento spec).
- Notové příklady: pokud se ukáže potřeba, zvážit jejich uložení jako oříznuté obrázky
  s odkazem z textu (ne OMR) — rozhodnout později.
