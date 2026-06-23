"""extract -- MAP krok: z jednoho okna textu vytáhne koncepty (Ollama, vlastní slova)."""
from .concept import slugify

MAP_PROMPT = (
    "You are building a jazz-piano learning curriculum. From the passage below, "
    "list the distinct musical CONCEPTS a student should learn. Use your OWN words; "
    "do NOT copy sentences from the text. For each concept give a short summary "
    "(1-3 sentences), a difficulty level (beginner|intermediate|advanced), the names "
    "of prerequisite concepts, and a few keywords. Return strict JSON: "
    '{"concepts":[{"name":...,"summary":...,"level":...,"prerequisites":[...],"keywords":[...]}]}.'
    "\n\nPASSAGE:\n%s"
)


def extract_concepts(chunk, client):
    """-> list uzlů dle schématu; source_refs převzaty z chunku."""
    data = client.generate_json(MAP_PROMPT % chunk.text)
    out = []
    for c in data.get("concepts", []):
        name = (c.get("name") or "").strip()
        if not name:
            continue
        out.append({
            "id": slugify(name),
            "name": name,
            "summary": (c.get("summary") or "").strip(),
            "level": (c.get("level") or "review"),
            "prerequisites": [slugify(p) for p in c.get("prerequisites", []) if (p or "").strip()],
            "keywords": [k for k in c.get("keywords", []) if (k or "").strip()],
            "source_refs": [{"chapter": chunk.chapter, "pages": chunk.pages}],
            "practice": [],
        })
    return out
