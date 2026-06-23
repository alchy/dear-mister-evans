"""graph -- deterministické sloučení konceptů (fuzzy dedup) + topologické řazení."""
from .concept import slugify, norm_level, canonical_key


def _jaccard(a, b):
    return len(a & b) / len(a | b) if a and b else 0.0


def merge_concepts(per_chunk, sim_threshold=0.8):
    """Fuzzy sloučení napříč okny: koncepty se shodným kanonickým klíčem NEBO vysokou
    tokenovou podobností (Jaccard >= práh) tvoří jeden uzel. Reprezentant = nejkratší
    název; prerekvizity se PŘEMAPUJÍ na kanonická id; level = většinové hlasování.
    Union-Find clustering, deterministické."""
    flat = [c for lst in per_chunk for c in lst]
    n = len(flat)
    if n == 0:
        return []
    toks = [set(canonical_key(c["name"]).split()) for c in flat]
    parent = list(range(n))

    def find(x):
        r = x
        while parent[r] != r:
            r = parent[r]
        while parent[x] != r:
            parent[x], x = r, parent[x]
        return r

    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[max(ra, rb)] = min(ra, rb)

    by_key = {}
    for i in range(n):
        k = " ".join(sorted(toks[i]))
        if k in by_key:
            union(i, by_key[k])
        else:
            by_key[k] = i
    for i in range(n):
        for j in range(i + 1, n):
            if find(i) != find(j) and _jaccard(toks[i], toks[j]) >= sim_threshold:
                union(i, j)

    clusters, order = {}, []
    for i in range(n):
        r = find(i)
        if r not in clusters:
            clusters[r] = []
            order.append(r)
        clusters[r].append(i)

    def _rep(members):
        return min(members, key=lambda i: (len(flat[i]["name"]), i))

    cluster_id = {r: slugify(flat[_rep(clusters[r])]["name"]) for r in order}
    remap = {slugify(flat[i]["name"]): cluster_id[find(i)] for i in range(n)}

    result = []
    for r in order:
        members = clusters[r]
        rep = _rep(members)
        cid = cluster_id[r]
        prereqs, keywords, refs, summary, votes = set(), set(), [], "", {}
        for i in members:
            c = flat[i]
            prereqs |= set(c["prerequisites"])
            keywords |= set(c["keywords"])
            for s in c["source_refs"]:
                if s not in refs:
                    refs.append(s)
            if len(c["summary"]) > len(summary):
                summary = c["summary"]
            lv = norm_level(c["level"])
            votes[lv] = votes.get(lv, 0) + 1
        remapped = sorted({remap.get(p, p) for p in prereqs} - {cid})
        level = max(votes, key=lambda k: (votes[k], k))
        result.append({"id": cid, "name": flat[rep]["name"], "summary": summary,
                       "level": level, "prerequisites": remapped,
                       "keywords": sorted(keywords), "source_refs": refs, "practice": []})
    return result


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
