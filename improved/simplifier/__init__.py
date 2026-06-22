"""simplifier -- živé Evansovo MIDI -> knihovna ii-V-I licků (akord + melodie).

Čistý nový balík (NEdědí ze starého arrange.py/harmony.py, který předpokládá
pevnou mřížku bar=4.0). Vstup je ŽIVÉ hraní (rubato, flat nominální tempo), takže
beat se musí DETEKOVAT z onsetů. Fáze:

  io_midi  -> onsety v reálném čase
  beats    -> beat-tracking (rubato-aware, symbolicky)
  chords   -> akord na beat-span (Evans-aware: ne bass=root kvůli rootless voicingům)
  melody   -> skyline + čištění (rytmus v beat jednotkách)
  functional -> ii-V-I / ii-V / turnaround segmentace (klesající kvinty)
  licks    -> sestav + ulož JSON + MIDI
"""
