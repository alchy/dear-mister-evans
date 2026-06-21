# Posbírané tipy z webu -> pravidla generátoru

Koncepty z veřejných jazzových lekcí (parafráze, ne citace), převedené na pravidla pro
builder „cíl + spojka". Doplňuje [LEVINE_DESIGN.md](LEVINE_DESIGN.md).

## Koncepty (kurikulum, ověřeno webem)
1. **7. akordy (5 kvalit)** + tenze/alterace — základ harmonie.
2. **Stupnice = „pitch collections"** (ne lineární vzory): Ión/maj7, Dór/m7, Mixo/7,
   Lokr/m7b5, zmenšená/dim. Učit jako množinu tónů, ne drilované vzory.
3. **Guide tóny (3 a 7)** = nejdůležitější pro identitu akordu; veď je **plynule krokem**
   přes changes („guide-tone linka") -> melodie obkresluje harmonii.
4. **Progrese**: ii–V–I (dur i moll), I–vi–ii–V turnaroundy.
5. **Improv**: uč se fráze uchem, mapuj chord-tóny a guide-tóny s voice-leadingem,
   aplikuj pitch collections (teorie dává kontext, ale uši/transkripce nenahradí).

## Stavba linky (bebop) -> pravidla generátoru
6. **Bebop stupnice** = přidaný chromatický průchod (dominant: Mixo +♮7; dur: Ión +♭6),
   takže **rovné osminy drží chord-tóny na těžké**, *když fráze začne na akord. tónu
   (1/3/5/♭7)*. → Pravidlo: scalar spojka = bebop běh, **start z 1/3/5/♭7**, hlídat,
   ať těžké padají na chord-tóny.
7. **Cíle = chord-tóny (zvl. 3 a 7)** na změnách / silných dobách.
8. **Approach note**: dojdi na cíl ze **sousedního tónu shora/zdola** (diatonicky nebo
   půltónem). → spojka `approach`.
9. **Enclosure (obklíčení)**: **obklop cíl** sousedními tóny (typicky tón-nad + tón-pod
   → cíl; nebo scale-nad → chromatika-zdola → cíl). → spojka `enclosure`.
10. **Do dalšího akordu**: miř na jeho 3/7 přes approach/enclosure na „and" před dobou
    (**anticipace**).
11. **Leap rozveď krokem** (obecné bebop pravidlo); jinak převážně krok.

## Mapování na connectory v melody.py
- `scalar`   -> bebop běh, start 1/3/5/♭7, chord-tón na těžkou (pravidlo 6,7).
- `approach` -> půltónový/diatonický náběh na cíl (8).
- `enclosure`-> obklíčení cíle (9).
- `arpeggio` -> skok na akord. tón, rozveď krokem (11).
Výběr/tvar spojky váží **naučený Evans vkus** + osa „inside↔outside" + parametry lekce.

## Zdroje
- learnjazzstandards.com — Ultimate Guide to Jazz Theory (akordy, stupnice, guide tóny, progrese).
- jazzadvice.com — Mastering the Bebop Scale (bebop -> chord-tóny na těžké, start 1/3/5/♭7).
- learnjazzstandards.com — Use Bebop Scales Like a Pro (chromatika, enclosure).
