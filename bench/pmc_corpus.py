"""
Download the validation corpus: open access RCT articles from PubMed Central.

    python bench/pmc_corpus.py [COUNT]        default 500

Searches randomized controlled trials published 2020 to 2025 in five journals
that are fully open access in PMC, newest first, and stores each article's
JATS XML in bench/corpus/. Already downloaded articles are skipped.

NCBI allows three requests per second without an API key; articles are
fetched in blocks of 20 with a pause in between. The article list depends
on the day it is run (newest first); bench/corpus_ids.txt holds the list
used for the numbers in the README, and `--ids` downloads exactly those.
"""

from __future__ import annotations

import json
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path
from xml.etree import ElementTree as ET

HERE = Path(__file__).resolve().parent
CORPUS = HERE / "corpus"
IDS = HERE / "corpus_ids.txt"
EUTILS = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/"
QUERY = ('"randomized controlled trial"[pt] AND 2020:2025[pdat] AND '
         '("JAMA Netw Open"[ta] OR "BMJ"[ta] OR "PLoS Med"[ta] OR "BMC Med"[ta] OR "Trials"[ta])')
HEADERS = {"User-Agent": "numcheck-validation/0.1"}


def _get(url: str) -> bytes:
    with urllib.request.urlopen(urllib.request.Request(url, headers=HEADERS), timeout=60) as r:
        return r.read()


def search(count: int) -> list[str]:
    url = EUTILS + "esearch.fcgi?" + urllib.parse.urlencode(
        {"db": "pmc", "term": QUERY, "retmax": count, "retmode": "json", "sort": "pub_date"})
    return json.loads(_get(url))["esearchresult"]["idlist"]


def download(ids: list[str]) -> None:
    CORPUS.mkdir(exist_ok=True)
    missing = [i for i in ids if not (CORPUS / f"PMC{i}.xml").exists()]
    for start in range(0, len(missing), 20):
        block = missing[start:start + 20]
        root = ET.fromstring(_get(EUTILS + "efetch.fcgi?" + urllib.parse.urlencode({"db": "pmc", "id": ",".join(block)})))
        for article in root.findall("article"):
            pmcid = next((e.text for e in article.iter("article-id") if e.get("pub-id-type") in ("pmc", "pmcid")), None)
            if pmcid:
                (CORPUS / f"PMC{pmcid.replace('PMC', '')}.xml").write_bytes(ET.tostring(article, encoding="utf-8"))
        time.sleep(0.5)


def main(args: list[str]) -> int:
    if "--ids" in args:
        ids = [line.strip().replace("PMC", "") for line in IDS.read_text().splitlines() if line.strip()]
    else:
        ids = search(int(args[0]) if args else 500)
    download(ids)
    print(f"{len(list(CORPUS.glob('PMC*.xml')))} articles in {CORPUS}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
