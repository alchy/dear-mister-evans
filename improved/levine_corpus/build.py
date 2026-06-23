# improved/levine_corpus/build.py
"""build -- orchestrace OCR korpusu: render -> dávky -> OCR(cache) -> assemble
-> clean -> segment -> markdown po kapitolách. + CLI."""
import re
from pathlib import Path
from .render import render_pages
from .assemble import assemble
from .clean import clean_document
from .segment import segment_chapters


def _page_no(path):
    m = re.search(r"(\d+)", Path(path).stem)
    return int(m.group(1)) if m else 0


def batch_pages(image_paths, max_pages):
    """-> [(first_page, last_page, [paths])] po max_pages."""
    out = []
    for i in range(0, len(image_paths), max_pages):
        chunk = image_paths[i:i + max_pages]
        out.append((_page_no(chunk[0]), _page_no(chunk[-1]), chunk))
    return out


def _slug(title, i):
    s = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")[:40] or "chapter"
    return f"{i:02d}-{s}.md"


def build_corpus(pdf_path, work_dir, out_dir, engine, first=None, last=None):
    """Celá pipeline. -> list cest k zapsaným .md kapitolám."""
    work = Path(work_dir); cache = work / "cache"; cache.mkdir(parents=True, exist_ok=True)
    out = Path(out_dir); out.mkdir(parents=True, exist_ok=True)
    pages = render_pages(pdf_path, work / "pages", first=first, last=last)
    batches = batch_pages(pages, engine.max_pages)
    texts = []
    for f, l, imgs in batches:
        cf = cache / f"batch-{f:04d}-{l:04d}.md"
        if cf.exists():
            text = cf.read_text()
        else:
            text = engine.ocr_batch(imgs)
            cf.write_text(text)
        texts.append((f, l, text))
    doc = clean_document(assemble(texts))
    written = []
    for i, (title, body) in enumerate(segment_chapters(doc), 1):
        fp = out / _slug(title, i)
        fp.write_text(f"# {title}\n\n{body}\n")
        written.append(fp)
    return written


def main():
    import argparse
    ap = argparse.ArgumentParser(description="OCR Levine -> markdown korpus")
    ap.add_argument("pdf")
    ap.add_argument("out_dir")
    ap.add_argument("--work", required=True)
    ap.add_argument("--engine", choices=["tesseract", "baidu"], default="tesseract")
    ap.add_argument("--first", type=int)
    ap.add_argument("--last", type=int)
    a = ap.parse_args()
    if a.engine == "baidu":
        from .engine_baidu import BaiduEngine
        eng = BaiduEngine()
    else:
        from .engine import TesseractEngine
        eng = TesseractEngine()
    if not eng.available():
        raise SystemExit(f"engine '{a.engine}' není dostupný")
    paths = build_corpus(a.pdf, a.work, a.out_dir, eng, first=a.first, last=a.last)
    print(f"hotovo: {len(paths)} kapitol -> {a.out_dir}")


if __name__ == "__main__":
    main()
