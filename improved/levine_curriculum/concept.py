"""concept -- schéma uzlu osnovy + pomocníci (slugify, blank_concept)."""
import re

CONCEPT_KEYS = ["id", "name", "summary", "level", "prerequisites",
                "keywords", "source_refs", "practice"]


def slugify(name):
    s = re.sub(r"[^a-z0-9]+", "-", (name or "").lower()).strip("-")
    return s or "concept"


def blank_concept(name, **kw):
    c = {"id": slugify(name), "name": name, "summary": "", "level": "review",
         "prerequisites": [], "keywords": [], "source_refs": [], "practice": []}
    for k, v in kw.items():
        if k in CONCEPT_KEYS:
            c[k] = v
    return c
