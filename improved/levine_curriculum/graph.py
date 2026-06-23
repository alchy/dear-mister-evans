"""graph -- deterministické sloučení konceptů (dedup) + topologické řazení."""


def merge_concepts(per_chunk):
    """Sloučí uzly se stejným id napříč okny: union prereq/keywords/source_refs,
    delší summary vyhrává. -> list uzlů (pořadí prvního výskytu)."""
    by_id = {}
    order = []
    for lst in per_chunk:
        for c in lst:
            cur = by_id.get(c["id"])
            if cur is None:
                by_id[c["id"]] = {**c,
                                  "prerequisites": list(c["prerequisites"]),
                                  "keywords": list(c["keywords"]),
                                  "source_refs": list(c["source_refs"])}
                order.append(c["id"])
            else:
                cur["prerequisites"] = sorted(set(cur["prerequisites"]) | set(c["prerequisites"]))
                cur["keywords"] = sorted(set(cur["keywords"]) | set(c["keywords"]))
                for s in c["source_refs"]:
                    if s not in cur["source_refs"]:
                        cur["source_refs"].append(s)
                if len(c["summary"]) > len(cur["summary"]):
                    cur["summary"] = c["summary"]
    return [by_id[i] for i in order]


def order_concepts(concepts):
    """Topologické řazení dle prerekvizit (prereq před závislým). Cykly přeruší
    (back-edge se ignoruje), takže vždy vrátí všechny uzly. Stabilní vůči vstupu."""
    cmap = {c["id"]: c for c in concepts}
    ids = set(cmap)
    deps = {c["id"]: [p for p in c["prerequisites"] if p in ids and p != c["id"]] for c in concepts}
    state = {i: 0 for i in ids}     # 0 unvisited, 1 in-progress, 2 done
    result = []

    def visit(i):
        if state[i] != 0:
            return                  # done nebo in-progress (cyklus) -> přeskoč
        state[i] = 1
        for p in deps[i]:
            visit(p)
        state[i] = 2
        result.append(cmap[i])

    for c in concepts:              # stabilní pořadí vstupu
        visit(c["id"])
    return result
