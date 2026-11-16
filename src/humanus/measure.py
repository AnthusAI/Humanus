"""Plain measurements of a text: its size, structure, sourcing and how much a revision changed.

Measurements are guidance for people and agents, never gates: they report
numbers, set no limits and judge nothing. They are deterministic (the same text
and language always give the same numbers; no model is called) and read the
text the way its language pack does, so a length is words in English and
Spanish and characters in Simplified Chinese.

``measure`` reads one text; ``diff`` compares two. Both read the text a reader
reads: front matter, code, Markus directives and raw HTML are skipped, markup
is stripped to its words, and a block quotation is read (it is a reader's words
to read) but is left out of the structure figures, which describe the author's
own paragraphs and sentences. Markup-only edits are therefore not changes.
"""
from __future__ import annotations

import re
from collections.abc import Sequence
from difflib import SequenceMatcher
from typing import Any

from .languages import Language, resolve_language
from .parity import _citations_in, _links_in
from .segmentation import SegmentedDocument, normalize_text, plain_text, segment_document

MEASURE_VERSION = 1

# A reference-style link in running text: [text][label] or [text][].
_REFERENCE_USE = re.compile(r"\]\[[^\]]*\]")
_QUOTE_MARKER = re.compile(r"^[ ]{0,3}(?:>[ ]?)+", re.M)


def measure(
    text: str,
    language: Language | str,
    concepts: Sequence[str] | None = None,
    *,
    format: str = "markus",
    headline: str | None = None,
    dek: str | None = None,
    blurb: str | None = None,
) -> dict[str, Any]:
    """Measure ``text`` written in ``language`` (a language pack or BCP 47 tag).

    ``headline``, ``dek`` and ``blurb`` are the story's other texts; each one
    given is measured (present or empty, and its length), each left out is not.
    ``concepts`` is reserved for the concept-density measurement, which is a
    later slice: passing it is refused rather than ignored.
    """
    if concepts is not None:
        raise NotImplementedError("concept measurements are not available yet; call measure() without a concept list")
    lang = _language(language)
    document = segment_document(text, format, language=lang)

    prose = [s for s in document.segments if s.kind == "paragraph"]
    quotes = _quotations(document, lang)
    size_units = sum(len(lang.units(s.text)) for s in prose) + sum(len(lang.units(q)) for q in quotes)

    paragraphs = [s for s in prose if s.block == "paragraph"]
    paragraph_sizes = [len(lang.units(s.text)) for s in paragraphs]
    sentence_sizes = [
        len(lang.units(s.text))
        for s in document.segments
        if s.kind == "sentence" and s.block in {"paragraph", "listItem"}
    ]

    structure: dict[str, Any] = {
        "sections": sum(1 for s in prose if s.block == "heading"),
        "paragraphs": len(paragraphs),
        "longestParagraph": max(paragraph_sizes, default=0),
        "longestSentence": max(sentence_sizes, default=0),
    }
    for name, value in (("headline", headline), ("dek", dek), ("blurb", blurb)):
        if value is not None:
            length = len(lang.units(plain_text(value)))
            structure[name] = {"present": length > 0, "length": length}

    links = _links_in(document)
    citations = _citations_in(document)
    sources = len(links) + len(citations)
    anchors = sorted([start for _, start, _ in links] + [start for _, start, _ in citations])
    unsourced = sum(1 for p in paragraphs if not _has_source(p.start, p.end, p.source, anchors))

    return {
        "measureVersion": MEASURE_VERSION,
        "language": lang.tag,
        "size": {
            "unit": lang.unit,
            "units": size_units,
            "readingMinutes": round(size_units / lang.reading_units_per_minute, 2),
            "readingUnitsPerMinute": lang.reading_units_per_minute,
        },
        "structure": structure,
        "sourcing": {
            "links": len(links),
            "citations": len(citations),
            "sources": sources,
            "per500": round(sources * 500 / size_units, 2) if size_units else None,
            "paragraphsWithoutSource": unsourced,
            "shareParagraphsWithoutSource": round(unsourced / len(paragraphs), 4) if paragraphs else None,
        },
    }


def diff(old_text: str, new_text: str, language: Language | str, *, format: str = "markus") -> dict[str, Any]:
    """How much ``new_text`` changed from ``old_text``, in the language's unit of length.

    The two texts are compared unit by unit after markup is stripped. In a
    stretch that was replaced, as many units as the shorter side has are
    *rewritten*; the surplus on the new side is *added* and on the old side
    *removed*. ``shareChanged`` is the touched units over the merged text
    (unchanged plus touched): 0.0 for identical text, 1.0 when nothing is kept.
    """
    lang = _language(language)
    old, new = _units(old_text, lang, format), _units(new_text, lang, format)
    added = removed = rewritten = unchanged = 0
    for tag, i1, i2, j1, j2 in SequenceMatcher(None, old, new, autojunk=False).get_opcodes():
        before, after = i2 - i1, j2 - j1
        if tag == "equal":
            unchanged += before
        else:
            rewritten += min(before, after)
            added += max(after - before, 0)
            removed += max(before - after, 0)
    touched = added + removed + rewritten
    merged = unchanged + touched
    return {
        "measureVersion": MEASURE_VERSION,
        "language": lang.tag,
        "unit": lang.unit,
        "oldUnits": len(old),
        "newUnits": len(new),
        "added": added,
        "removed": removed,
        "rewritten": rewritten,
        "unchanged": unchanged,
        "shareChanged": round(touched / merged, 4) if merged else 0.0,
    }


def _language(language: Language | str) -> Language:
    return resolve_language(language) if isinstance(language, str) else language


def _units(text: str, lang: Language, format: str) -> list[str]:
    document = segment_document(text, format, language=lang)
    blocks = [(s.start, s.text) for s in document.segments if s.kind == "paragraph"]
    blocks += [(start, quote) for start, quote in _quotation_blocks(document, lang)]
    units: list[str] = []
    for _, block in sorted(blocks):
        units.extend(normalize_text(u) for u in lang.units(block))
    return units


def _quotations(document: SegmentedDocument, lang: Language) -> list[str]:
    return [quote for _, quote in _quotation_blocks(document, lang)]


def _quotation_blocks(document: SegmentedDocument, lang: Language) -> list[tuple[int, str]]:
    """The words inside block quotations, each with the offset where its quotation starts."""
    quotes = []
    for region in document.protected:
        if region.kind == "quote":
            words = plain_text(_QUOTE_MARKER.sub("", document.text[region.start : region.end]))
            if words:
                quotes.append((region.start, words))
    return quotes


def _has_source(start: int, end: int, source: str, anchors: Sequence[int]) -> bool:
    return any(start <= at < end for at in anchors) or bool(_REFERENCE_USE.search(source))
