"""tunes -- načte jazzové standardy ze standards.json (rozšiřitelné za běhu).

Každý standard = {name, key, changes}. changes = akordy oddělené mezerou (1 = 1 takt).
Rozšiřuj přidáním položek do standards.json; není potřeba měnit kód.
"""
import os
import json

_PATH = os.path.join(os.path.dirname(__file__), "standards.json")


def load():
    try:
        with open(_PATH, encoding="utf-8") as fh:
            return json.load(fh).get("standards", [])
    except Exception:
        return []
