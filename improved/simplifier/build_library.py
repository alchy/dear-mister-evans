"""build_library -- projede složku slices -> agregovaná knihovna licků.

  python -m simplifier.build_library "<složka s *.mid>" [out.json]
"""
import os, sys, glob
from collections import Counter
from . import licks as L


def build(slice_dir, out_json=None):
    paths = sorted(glob.glob(os.path.join(slice_dir, "*.mid")))
    all_licks = []
    for p in paths:
        name = os.path.basename(p)
        try:
            ls = L.extract_from_file(p)
        except Exception as e:
            print(f"  {name:>16}: CHYBA {type(e).__name__}: {e}")
            continue
        for lk in ls:
            lk["source"] = name
        all_licks.extend(ls)
        print(f"  {name:>16}: {len(ls):>2} licků  {dict(Counter(l['type'] for l in ls))}")
    all_licks.sort(key=lambda x: -x["score"])
    print(f"\nCELKEM {len(all_licks)} licků z {len(paths)} souborů  "
          f"{dict(Counter(l['type'] for l in all_licks))}")
    if out_json:
        L.save_library(all_licks, out_json)
        print(f"uloženo -> {out_json}")
    return all_licks


if __name__ == "__main__":
    licks = build(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else None)
    print("\nTOP 15 napříč knihovnou (skóre):")
    for lk in licks[:15]:
        print(f"  {lk['score']:.2f} tok={lk['flow']:.2f} cons={lk['cons']:.2f} "
              f"[{lk['type']:>7}] {lk['changes']:<22} {len(lk['melody']):>2}not  {lk['source']}")
