"""Font discovery for the finalist dashboard (Pillow). Falls back gracefully, never crashes on a missing font."""
from __future__ import annotations

from functools import lru_cache
from typing import Any

from PIL import Image, ImageDraw, ImageFont

REGULAR = ["segoeui.ttf", "SegoeUI.ttf", "arial.ttf", "Arial.ttf", "Helvetica.ttc", "DejaVuSans.ttf",
           "LiberationSans-Regular.ttf", "NotoSans-Regular.ttf"]
BOLD = ["segoeuib.ttf", "arialbd.ttf", "Arial Bold.ttf", "DejaVuSans-Bold.ttf", "LiberationSans-Bold.ttf",
        "NotoSans-Bold.ttf"]
# Used only when the chosen font has no glyph for the symbol.
TRANSLIT = {"→": "->", "•": "|", "—": "-", "·": "-", "…": "..."}


class FontKit:
    """Loads fonts lazily, measures text, and transliterates symbols the font cannot draw."""

    def __init__(self, regular: list[str] | None = None, bold: list[str] | None = None):
        self._regular = regular or REGULAR
        self._bold = bold or BOLD
        self._unicode_ok: bool | None = None

    @lru_cache(maxsize=None)
    def font(self, size: int, bold: bool = False) -> Any:
        for name in (self._bold if bold else self._regular):
            try:
                return ImageFont.truetype(name, size)
            except OSError:
                continue
        try:  # Pillow >= 10.1 ships a scalable built-in font
            return ImageFont.load_default(size)
        except TypeError:
            return ImageFont.load_default()

    @property
    def unicode_ok(self) -> bool:
        if self._unicode_ok is None:
            f = self.font(24)

            def glyph(c: str) -> bytes:
                im = Image.new("L", (48, 48), 0)
                ImageDraw.Draw(im).text((4, 4), c, font=f, fill=255)
                return im.tobytes()

            try:
                missing = glyph(chr(0xFFFF))
                self._unicode_ok = all(glyph(c) != missing for c in TRANSLIT)
            except Exception:
                self._unicode_ok = False
        return self._unicode_ok

    def txt(self, s: str) -> str:
        if self.unicode_ok:
            return s
        for k, v in TRANSLIT.items():
            s = s.replace(k, v)
        return s

    def width(self, s: str, size: int, bold: bool = False) -> float:
        return float(self.font(size, bold).getlength(s))

    def height(self, size: int, bold: bool = False) -> int:
        a, d = self.font(size, bold).getmetrics()
        return int(a + d)
