"""output -- zápis osnovy: curriculum.json (graf) + curriculum.md + critic_report.md."""
import json
from pathlib import Path


def write_curriculum(concepts, out_dir, critic_report=None):
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    (out / "curriculum.json").write_text(json.dumps(concepts, ensure_ascii=False, indent=2))
    lines = ["# Výuková osnova (auto-extrakce z Levina — vlastní formulace)\n"]
    for c in concepts:
        prereq = ", ".join(c["prerequisites"]) or "—"
        src = "; ".join(f"{s['chapter']} {s['pages']}".strip() for s in c["source_refs"]) or "—"
        lines.append(f"### {c['name']} · {c['level']}\n{c['summary']}\n"
                     f"- Prerekvizity: {prereq}\n- Zdroj: {src}\n- Cvičení: (zatím nenamapováno)\n")
    (out / "curriculum.md").write_text("\n".join(lines))
    if critic_report is not None:
        rep = ["# Critic report\n", "## Možné chybějící koncepty"]
        rep += [f"- {m}" for m in critic_report.get("missing", [])] or ["(žádné)"]
        rep += ["\n## Poznámky"]
        rep += [f"- {n}" for n in critic_report.get("notes", [])] or ["(žádné)"]
        (out / "critic_report.md").write_text("\n".join(rep))
    return out
