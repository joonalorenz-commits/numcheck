"""
German number format: "19,4 %", "1.234 Patienten", "HR 0,48 [0,29; 0,80]".

The checks read English numbers. A page written in German notation is
rewritten to English notation before the checks see it, character for
character, so that finding positions still point at the same place:

- decimal comma -> point:          19,4    -> 19.4
- thousands point -> comma:        1.234   -> 1,234
- interval separator in brackets:  [a; b]  -> [a, b]
- a space the PDF reader put after a decimal comma before an interval:
  "0, 694 [0,484; 0,995]" -> "0.694  [0.484, 0.995]"

Whether a page is German is decided per page from the numbers themselves:
"(19,4)" or "4,1 %" is a decimal comma that English text never has, while
English decimals look like "19.4". A page counts as German when it has at
least three decimal commas and more of them than decimal points. Pages in
English notation are returned unchanged, so English documents give exactly
the same findings as before.
"""

from __future__ import annotations

import re

# A decimal comma: one to two digits after the comma, inside a bracket or before a percent sign or a
# semicolon of an interval. "1,234" (English thousands) has three digits and does not count.
_DE_DECIMAL = re.compile(r"(?<![\d.,])\d{1,3},\d{1,2}(?![\d,])(?=\s?(?:%|\)|;|\]))|(?<=[(\[])\s?\d{1,3},\d{1,2}(?![\d,])")
_EN_DECIMAL = re.compile(r"(?<![\d.,])\d{1,3}\.\d{1,2}(?![\d.])(?=\s?(?:%|\)|,|\]))|(?<=[(\[])\s?\d{1,3}\.\d{1,2}(?![\d.])")

# A number in German notation: thousands points and/or a decimal comma.
_DE_NUMBER = re.compile(r"(?<![\d.,])(?:\d{1,3}(?:\.\d{3})+(?:,\d+)?|\d+,\d+)(?!\d)(?!\.\d)")
# "[0,29; 0,80]" and "(0,29; 0,80)" after the numbers have been converted
_INTERVAL_SEMICOLON = re.compile(r"(?<=[\[(])(\s?[−-]?\d+(?:\.\d+)?\s?);(?=\s?[−-]?\d+(?:\.\d+)?\s?[\])])")
# "0, 694 [" : a decimal comma split by the PDF reader, followed by an interval
_SPLIT_DECIMAL = re.compile(r"(?<![\d.,])(\d+), (\d+)(?=\s?\[)")


def is_german(text: str) -> bool:
    de = len(_DE_DECIMAL.findall(text))
    return de >= 3 and de > len(_EN_DECIMAL.findall(text))


def _swap(m: re.Match) -> str:
    return m.group().translate(str.maketrans({".": ",", ",": "."}))


def to_english(text: str) -> str:
    """The same text in English number notation, with exactly the same length."""
    out = _DE_NUMBER.sub(_swap, text)
    out = _SPLIT_DECIMAL.sub(lambda m: f"{m.group(1)}.{m.group(2)} ", out)
    out = _INTERVAL_SEMICOLON.sub(lambda m: m.group(1) + ",", out)
    assert len(out) == len(text)
    return out


def english(text: str) -> str:
    """Pages in German notation in English notation, all others unchanged."""
    return to_english(text) if is_german(text) else text
