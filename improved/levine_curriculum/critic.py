"""critic -- kontrolní pass nad KOMPAKTNÍM seznamem konceptů (po dávkách).
Vrací report (chybějící koncepty + poznámky) pro spot-check; graf NEmutuje."""

CRITIC_PROMPT = (
    "Below is a list of jazz-piano curriculum concept names. As a jazz educator, "
    "identify (a) important concepts that are MISSING from this list, and (b) brief "
    "notes on anything clearly out of order. Use your own words. Return strict JSON: "
    '{"missing":[names], "notes":[strings]}.\n\nCONCEPTS:\n%s'
)


def critique(concepts, client, batch=80):
    names = [c["name"] for c in concepts]
    missing, notes = [], []
    for i in range(0, len(names), batch):
        data = client.generate_json(CRITIC_PROMPT % "\n".join(names[i:i + batch]))
        missing += [m for m in data.get("missing", []) if (m or "").strip()]
        notes += [n for n in data.get("notes", []) if (n or "").strip()]
    seen = set()
    uniq_missing = [m for m in missing if not (m in seen or seen.add(m))]
    return {"missing": uniq_missing, "notes": notes}
