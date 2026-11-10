"""
Reading a document into pages of text.

Every check works on a dict {page number: text}. Line breaks matter for
tables (one table row per line works best), so they are kept. Positions of
findings refer to the text after `with_lines`, which keeps exactly one
character for every run of whitespace, so they are the same as in
`normalize`.

Sources:
- PDF (needs the optional dependency pypdf): one page per PDF page.
- JATS/PMC XML: page 1 is the abstract plus the results section, every
  table is a page of its own with one row per line. Introduction and
  discussion are left out because they quote numbers from other studies.
- plain text: one page, or pages separated by form feeds.
"""

from __future__ import annotations

import re
from pathlib import Path
from xml.etree import ElementTree as ET

# Some PDF fonts (Symbol, Wingdings) map ASCII into the private use area U+F020..F07E.
_SYMBOL_FONT = {c: c - 0xF000 for c in range(0xF020, 0xF07F)}


def readable(text: str) -> str:
    return text.translate(_SYMBOL_FONT)


def normalize(text: str) -> str:
    """Collapse all whitespace to single spaces."""
    return re.sub(r"\s+", " ", text).strip()


def with_lines(text: str) -> str:
    """Like normalize, but a run of whitespace containing a line break becomes one line break."""
    return re.sub(r"\s+", lambda m: "\n" if "\n" in m.group() else " ", text).strip()


def read_pdf(path: str | Path) -> dict[int, str]:
    import logging

    try:
        from pypdf import PdfReader
    except ImportError as e:  # pragma: no cover
        raise SystemExit("Reading PDF needs pypdf: pip install 'numcheck[pdf]'") from e
    logging.getLogger("pypdf").setLevel(logging.ERROR)
    reader = PdfReader(str(path))
    return {i: (p.extract_text() or "") for i, p in enumerate(reader.pages, start=1)}


def _text(e) -> str:
    return re.sub(r"\s+", " ", "".join(e.itertext())).strip()


def read_jats(path: str | Path) -> dict[int, str]:
    """Abstract and results section as page 1, each table as a further page."""
    article = ET.parse(str(path)).getroot()
    parts = [_text(a) for a in article.iter("abstract")]
    body = article.find(".//body")
    if body is not None:
        for sec in body.findall("sec"):
            title = sec.find("title")
            if title is not None and re.match(r"\s*(\d+\.?\s*)?results?\b", _text(title), re.I):
                parts += [_text(p) for p in sec.iter("p")]
    pages = {1: "\n".join(parts)}
    for i, wrap in enumerate(article.iter("table-wrap"), start=2):
        rows = [" ".join(_text(c) for c in tr) for tr in wrap.iter("tr")]
        pages[i] = "\n".join(rows)
    return pages


def read_text(path: str | Path) -> dict[int, str]:
    text = Path(path).read_text(encoding="utf-8", errors="replace")
    return {i: page for i, page in enumerate(text.split("\f"), start=1)}


def read(path: str | Path) -> dict[int, str]:
    """Pages of a PDF, JATS/PMC XML or text file, by file extension."""
    suffix = Path(path).suffix.lower()
    if suffix == ".pdf":
        return read_pdf(path)
    if suffix in (".xml", ".nxml"):
        return read_jats(path)
    return read_text(path)


def prepare(pages: dict[int, str]) -> dict[int, str]:
    """The text the checks see, and that finding positions refer to."""
    return {n: with_lines(readable(t)) for n, t in sorted(pages.items())}
