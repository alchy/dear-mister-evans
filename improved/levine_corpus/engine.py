"""engine -- vyměnitelný OCR krok. Rozhraní OcrEngine + Tesseract baseline."""
import subprocess
from pathlib import Path
from shutil import which


class OcrEngine:
    """Kontrakt OCR enginu. ocr_batch dostane dávku obrázků (<= max_pages) a vrátí text."""
    max_pages = 1

    def available(self) -> bool:
        raise NotImplementedError

    def ocr_batch(self, image_paths) -> str:
        raise NotImplementedError


class TesseractEngine(OcrEngine):
    """Per-strana Tesseract (subprocess), konkatenace. Spolehlivý lokální baseline."""
    max_pages = 1

    def __init__(self, lang="eng"):
        self.lang = lang

    def available(self) -> bool:
        return which("tesseract") is not None

    def ocr_batch(self, image_paths) -> str:
        texts = []
        for p in image_paths:
            r = subprocess.run(["tesseract", str(p), "stdout", "-l", self.lang],
                               capture_output=True, text=True, check=True)
            texts.append(r.stdout)
        return "\n".join(texts)
