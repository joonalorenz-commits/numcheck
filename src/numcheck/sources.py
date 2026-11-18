"""
Compare a statement with the publication it cites.

A summary document (an SSCP, a clinical evaluation, a review) often repeats a
result from a published study: "During follow-up, 11 of 137 (8.8%) patients
died [53]". Whether that number is right can only be decided in the source.
This module fetches the open-access full text from PubMed Central and finds
the sentences there that report the same result:

    numcheck-source report.pdf --page 10 --source PMC8999580
    numcheck-source --text "11 of 137 (8.8%) patients died" --source 10.3390/jcm11071978

For every statement it reports

    same         a sentence in the source has all numbers of the statement
    differs      the closest sentence in the source shares the key numbers but
                 not all of them (the differing numbers are listed)
    not_found    no sentence in the source shares enough numbers

and, independently, every source sentence it shows is run through the normal
checks, so a source that contradicts itself (abstract says 12 of 137, results
say 11 of 137) is visible.

Matching uses only the numbers, not the words: two sentences match when they
share the percentage and at least one count, or at least three numbers.
Nothing is sent anywhere except the identifier to NCBI.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.parse
import urllib.request
from dataclasses import asdict, dataclass, field
from html.parser import HTMLParser
from pathlib import Path
from xml.etree import ElementTree as ET

from numcheck import __version__, check, document

USER_AGENT = f"numcheck/{__version__} (+https://github.com/joonalorenz-commits/numcheck)"
_NUM = re.compile(r"(?<![\w.])(\d{1,3}(?:,\d{3})+|\d+(?:\.\d+)?)(\s?%)?")
_SENT = re.compile(r"(?<=[.;!?])\s+(?=[A-Z(\[])")


@dataclass
class Match:
    statement: str
    verdict: str                       # same | differs | not_found
    numbers: list[str]
    source_section: str = ""
    source_sentence: str = ""
    missing_in_source: list[str] = field(default_factory=list)
    other_sentences: list[dict] = field(default_factory=list)   # further matches, e.g. abstract vs results
    source_flags: list[dict] = field(default_factory=list)      # arithmetic flags in the matched source sentences

    def as_dict(self) -> dict:
        return asdict(self)


# ------------------------------------------------------------ fetching

def _get(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read(30_000_000)


def resolve(identifier: str) -> str:
    """PMCID for a PMCID, PMID or DOI. Raises ValueError if there is no PMC full text."""
    ident = identifier.strip()
    if re.fullmatch(r"(?i)pmc\d+", ident):
        return ident.upper()
    if ident.lower().startswith("https://doi.org/"):
        ident = ident[16:]
    url = ("https://www.ncbi.nlm.nih.gov/pmc/utils/idconv/v1.0/?format=json&tool=numcheck&ids="
           + urllib.parse.quote(ident))
    records = json.loads(_get(url)).get("records", [])
    for r in records:
        if r.get("pmcid"):
            return r["pmcid"]
    raise ValueError(f"No PubMed Central full text found for {identifier}.")


def _text(e) -> str:
    return re.sub(r"\s+", " ", "".join(e.itertext())).strip()


def sections(jats: bytes) -> list[tuple[str, str]]:
    """(section title, text) for the abstract, every body section and every table."""
    root = ET.fromstring(jats)
    out = []
    for a in root.iter("abstract"):
        out.append(("Abstract", _text(a)))
    body = root.find(".//body")
    if body is not None:
        for sec in body.iter("sec"):
            title = sec.find("title")
            paras = [_text(p) for p in sec.findall("p")]
            if paras:
                out.append((_text(title) if title is not None else "Body", " ".join(paras)))
    for wrap in root.iter("table-wrap"):
        label = wrap.find("label")
        rows = [" ".join(_text(c) for c in tr) for tr in wrap.iter("tr")]
        out.append((_text(label) if label is not None else "Table", "\n".join(rows)))
    return out


def fetch(pmcid: str) -> list[tuple[str, str]]:
    """Full text from NCBI, or from Europe PMC when NCBI returns no body (some publishers)."""
    num = pmcid.upper().removeprefix("PMC")
    data = _get(f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi?db=pmc&id={num}&rettype=xml&tool=numcheck")
    if b"<body" not in data:
        try:
            data2 = _get(f"https://www.ebi.ac.uk/europepmc/webservices/rest/PMC{num}/fullTextXML")
            if b"<body" in data2:
                data = data2
        except Exception:
            pass
    if b"<body" in data:
        return sections(data)
    # Some publishers block the XML but PMC still shows the article as a web page.
    try:
        html_sections = sections_from_html(_get(f"https://pmc.ncbi.nlm.nih.gov/articles/PMC{num}/").decode("utf-8", "replace"))
    except Exception:
        html_sections = []
    if len(html_sections) > 1:
        return html_sections
    if b"<abstract" in data:
        return sections(data)
    raise ValueError(f"PMC{num} has no full text at NCBI, Europe PMC or the PMC web page.")


class _HTMLSections(HTMLParser):
    """Text of a PMC article page, split at h2/h3 headings; table rows as lines."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.out: list[tuple[str, list[str]]] = [("Front", [])]
        self.skip = 0
        self.heading: list[str] | None = None
        self.cell = False

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style", "nav", "header", "footer"):
            self.skip += 1
        elif tag in ("h2", "h3"):
            self.heading = []
        elif tag in ("td", "th"):
            self.cell = True

    def handle_endtag(self, tag):
        if tag in ("script", "style", "nav", "header", "footer") and self.skip:
            self.skip -= 1
        elif tag in ("h2", "h3") and self.heading is not None:
            self.out.append((" ".join("".join(self.heading).split()), []))
            self.heading = None
        elif tag in ("p", "tr", "li", "div"):
            self.out[-1][1].append("\n")
        elif tag in ("td", "th"):
            self.out[-1][1].append(" ")

    def handle_data(self, data):
        if self.skip:
            return
        if self.heading is not None:
            self.heading.append(data)
        else:
            self.out[-1][1].append(data)


def sections_from_html(html: str) -> list[tuple[str, str]]:
    p = _HTMLSections()
    p.feed(html)
    out = []
    for title, parts in p.out:
        text = re.sub(r"[ \t]+", " ", "".join(parts))
        text = "\n".join(line.strip() for line in text.split("\n") if line.strip())
        if text and title not in ("Front",):
            out.append((title, text))
    return out


# ------------------------------------------------------------ matching

def numbers(sentence: str) -> list[str]:
    """Numbers of a sentence, normalised: '1,030' -> '1030', '8.8 %' -> '8.8%'. Years and references are kept;
    they rarely decide a match because a match needs a shared percentage or count."""
    out = []
    for m in _NUM.finditer(sentence):
        n = m.group(1).replace(",", "")
        out.append(n + ("%" if m.group(2) else ""))
    return out


def _sentences(text: str) -> list[str]:
    parts = []
    for line in text.split("\n"):
        parts += [s.strip() for s in _SENT.split(line) if s.strip()]
    return parts


def _key(nums: list[str]) -> tuple[set[str], set[str]]:
    pct = {n for n in nums if n.endswith("%")}
    counts = {n for n in nums if not n.endswith("%") and "." not in n}
    return pct, counts


def _score(claim: list[str], cand: list[str]) -> tuple[int, int, int]:
    """(shared percentages, shared counts, shared numbers) between two number lists."""
    cp, cc = _key(claim)
    sp, sc = _key(cand)
    shared = set(claim) & set(cand)
    return len(cp & sp), len(cc & sc), len(shared)


def _relevant(claim: list[str], cand: list[str]) -> bool:
    p, c, n = _score(claim, cand)
    # Same count and denominator with another percentage is a different result
    # reported for the same group, which is exactly what has to be shown.
    return (p >= 1 and c >= 1) or c >= 2 or n >= 3


def compare(statement: str, source: list[tuple[str, str]]) -> Match:
    claim = numbers(statement)
    pool = [(title, s, numbers(s)) for title, text in source for s in _sentences(text)]
    hits = [(title, s, nums) for title, s, nums in pool if _relevant(claim, nums)]
    if not hits:
        return Match(statement, "not_found", claim)
    hits.sort(key=lambda h: _score(claim, h[2]), reverse=True)
    best_title, best, best_nums = hits[0]
    missing = [n for n in claim if n not in best_nums]
    m = Match(statement, "same" if not missing else "differs", claim, best_title, best, missing)
    for title, s, nums in hits[1:6]:
        m.other_sentences.append({"section": title, "sentence": s,
                                  "missing_in_sentence": [n for n in claim if n not in nums]})
    for title, s, _ in hits[:6]:
        for f in check({1: s}):
            if f.flagged:
                m.source_flags.append({"section": title, "check": f.check, "verdict": f.verdict,
                                       "printed": f.printed, "computed": f.computed, "note": f.note})
    return m


def statements(page_text: str) -> list[str]:
    """Sentences of a page that report a result: a percentage together with a count."""
    out = []
    for s in _sentences(document.with_lines(document.readable(page_text))):
        p, c = _key(numbers(s))
        if p and c:
            out.append(s)
    return out


# ------------------------------------------------------------ command line

def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="numcheck-source",
                                 description="Compare statements in a report with the publication they cite.")
    ap.add_argument("report", nargs="?", type=Path, help="PDF or text file with the statements")
    ap.add_argument("--page", type=int, help="only statements on this page")
    ap.add_argument("--text", help="one statement given directly instead of a report")
    ap.add_argument("--source", required=True, help="PMCID, PMID or DOI of the cited publication")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    if not args.text and not args.report:
        ap.error("give a report or --text")

    pmcid = resolve(args.source)
    src = fetch(pmcid)
    if args.text:
        todo = [args.text]
    else:
        pages = document.read(args.report)
        todo = [s for n, t in sorted(pages.items()) if args.page in (None, n) for s in statements(t)]
    results = [compare(s, src) for s in todo]
    if args.json:
        json.dump({"source": pmcid, "results": [r.as_dict() for r in results]}, sys.stdout, ensure_ascii=False, indent=1)
        print()
        return 0
    print(f"Source {pmcid}: {len(src)} sections. {len(results)} statements.")
    for r in results:
        print(f"\n[{r.verdict}] {r.statement[:200]}")
        if r.source_sentence:
            print(f"  {r.source_section}: {r.source_sentence[:300]}")
        if r.missing_in_source:
            print(f"  not in that sentence: {', '.join(r.missing_in_source)}")
        for o in r.other_sentences[:3]:
            print(f"  also {o['section']}: {o['sentence'][:200]}"
                  + (f"  (missing: {', '.join(o['missing_in_sentence'])})" if o["missing_in_sentence"] else ""))
        for f in r.source_flags[:3]:
            print(f"  source itself: {f['section']} · {f['check']} · {f['verdict']} · printed {f['printed']},"
                  f" computed {f['computed']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
