"""render -- stránky PDF -> PNG přes poppler pdftoppm (idempotentní)."""
import subprocess
from pathlib import Path


def _pdftoppm_cmd(pdf_path, out_prefix, dpi, first, last):
    """Sestaví argv pro pdftoppm. Pure (testovatelné bez subprocesu)."""
    cmd = ["pdftoppm", "-png", "-gray", "-r", str(dpi)]
    if first is not None:
        cmd += ["-f", str(first)]
    if last is not None:
        cmd += ["-l", str(last)]
    cmd += [str(pdf_path), str(out_prefix)]
    return cmd


def render_pages(pdf_path, out_dir, dpi=300, first=None, last=None, force=False):
    """PDF -> page-NNN.png v out_dir. Idempotentní: pokud už PNG existují a ne force,
    jen je vrátí. -> seřazený list Path."""
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    existing = sorted(out.glob("page-*.png"))
    if existing and not force:
        return existing
    cmd = _pdftoppm_cmd(pdf_path, out / "page", dpi, first, last)
    subprocess.run(cmd, check=True)
    return sorted(out.glob("page-*.png"))
