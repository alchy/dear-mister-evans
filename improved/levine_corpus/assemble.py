"""assemble -- spojení OCR dávek do jednoho proudu s page markery."""


def assemble(batches):
    """batches: [(first_page, last_page, text)] v pořadí -> jeden markdown proud.
    Před každou dávku vloží '<!-- p.<first> -->' pro dohledání zdroje."""
    parts = []
    for first, _last, text in batches:
        parts.append(f"<!-- p.{first} -->")
        parts.append(text.strip())
    return "\n".join(parts) + "\n"
