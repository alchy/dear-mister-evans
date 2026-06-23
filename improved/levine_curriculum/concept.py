"""concept -- schéma uzlu osnovy + pomocníci (slugify, norm_level, canonical_key)."""
import re

CONCEPT_KEYS = ["id", "name", "summary", "level", "prerequisites",
                "keywords", "source_refs", "practice"]

LEVELS = ("beginner", "intermediate", "advanced")
_STOP = {"a", "an", "the", "and", "or", "of", "in", "to", "for", "with",
         "on", "at", "by", "as", "is", "its", "into"}


def slugify(name):
    s = re.sub(r"[^a-z0-9]+", "-", (name or "").lower()).strip("-")
    return s or "concept"


def norm_level(s):
    """Sjednoť úroveň na lowercase ze známé sady; jinak 'review'."""
    s = (s or "").strip().lower()
    return s if s in LEVELS else "review"


def _singular(tok):
    return tok[:-1] if len(tok) > 3 and tok.endswith("s") and not tok.endswith("ss") else tok


def canonical_key(name):
    """Kanonický klíč pro fuzzy dedup: lowercase, zahodí závorky/interpunkci/stopwords,
    singularizuje, seřadí unikátní tokeny. 'Tritone Substitutions' == 'Tritone Substitution'."""
    s = re.sub(r"\([^)]*\)", " ", (name or "").lower())
    toks = [_singular(t) for t in re.findall(r"[a-z0-9]+", s) if t not in _STOP]
    return " ".join(sorted(set(toks))) or "concept"


def blank_concept(name, **kw):
    c = {"id": slugify(name), "name": name, "summary": "", "level": "review",
         "prerequisites": [], "keywords": [], "source_refs": [], "practice": []}
    for k, v in kw.items():
        if k in CONCEPT_KEYS:
            c[k] = v
    return c
