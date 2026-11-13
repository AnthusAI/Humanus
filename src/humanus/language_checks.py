"""Generic built-in checks that take every word, unit and rate from the language pack.

``frame``      ordered parts with a bounded gap inside one sentence ("不是 … 而是",
               "no solo … sino").
``density``    how often a word class occurs in a paragraph, against the language
               pack's native baseline rate for it.
``typography`` a named mechanical rule (punctuation width, quotation marks, number
               forms ...) whose data is in the language pack; every finding carries
               its deterministic replacement.

None of them knows any language. A check that needs something the language pack
does not have raises :class:`LanguageCannotRun`, and the rules lane reports the
detector as not run with that reason.
"""
from __future__ import annotations

import math
import re
from decimal import Decimal
from typing import Callable, Iterable

from .languages import Language, LanguageCannotRun
from .segmentation import Segment, SegmentedDocument, mask_inline

Match = tuple[int, int, "str | None", "str | None"]

_LATIN_OR_DIGIT = re.compile(r"[A-Za-z0-9]")
_INLINE_SPACE = " \t"


# --- frame ---------------------------------------------------------------------------


def frame(document: SegmentedDocument, paragraphs: list[Segment], sentences: list[Segment], params: dict) -> Iterable[Match]:
    language = document.language
    parts = [language.phrase_pattern((part,)) for part in params["parts"]]
    max_gap = params.get("maxGap", 30)
    segments = sentences if params.get("within", "sentence") == "sentence" else paragraphs
    label = " … ".join(params["parts"])
    for segment in segments:
        masked = mask_inline(segment.source)
        position = 0
        while True:
            span = _find_frame(masked, parts, position, max_gap, language)
            if span is None:
                break
            yield segment.start + span[0], segment.start + span[1], f"Uses the frame '{label}'.", None
            position = span[1]


def _find_frame(text: str, parts: list[re.Pattern[str]], position: int, max_gap: int, language: Language) -> tuple[int, int] | None:
    for first in parts[0].finditer(text, position):
        end = first.end()
        for part in parts[1:]:
            following = part.search(text, end)
            if following is None or len(language.units(text[end : following.start()])) > max_gap:
                break
            end = following.end()
        else:
            return first.start(), end
    return None


# --- density -------------------------------------------------------------------------


def density(document: SegmentedDocument, paragraphs: list[Segment], sentences: list[Segment], params: dict) -> Iterable[Match]:
    language = document.language
    if "tag" in params:
        tagger = language.require_tagger()
        raise LanguageCannotRun(f"the {language.tag} language pack names the tagger '{tagger}', which this Humanus cannot run")
    name = params["lexicon"]
    terms = language.lexicon(name)
    baseline = language.baseline.get(name)
    if not baseline:
        raise LanguageCannotRun(f"the {language.tag} language pack has no native baseline rate for '{name}'")
    native = baseline["per1000"]
    provisional = "" if baseline.get("measured", False) else " (provisional, not yet measured)"
    significance = params.get("significance", 0.01)
    pattern = language.phrase_pattern(terms)
    shown = "/".join(terms)
    for paragraph in paragraphs:
        count = len(pattern.findall(mask_inline(paragraph.source)))
        size = len(language.units(paragraph.text))
        if not count or not size or poisson_at_least(count, native * size / 1000) >= significance:
            continue
        rate = 1000 * count / size
        yield (
            paragraph.start,
            paragraph.end,
            f"'{shown}' occurs {count} times in {size} {language.unit}s ({rate:.1f} per 1,000); "
            f"native writing averages {native:g} per 1,000{provisional}.",
            None,
        )


def poisson_at_least(count: int, expected: float) -> float:
    """P(X >= count) for X ~ Poisson(expected)."""
    if expected <= 0:
        return 0.0 if count > 0 else 1.0
    below = sum(math.exp(-expected + k * math.log(expected) - math.lgamma(k + 1)) for k in range(count))
    return max(0.0, 1.0 - below)


# --- typography ------------------------------------------------------------------------


def typography(document: SegmentedDocument, paragraphs: list[Segment], sentences: list[Segment], params: dict) -> Iterable[Match]:
    rule = TYPOGRAPHY_RULES[params["rule"]]
    yield from rule(document.language, paragraphs)


def _punctuation_width(language: Language, paragraphs: list[Segment]) -> Iterable[Match]:
    table_data, script_data, full_width = language.typography_data("punctuationWidth", "scriptCharacters", "fullWidthPunctuation")
    table = {entry["mark"]: entry for entry in table_data}
    script = re.compile(script_data)

    def native(char: str) -> bool:
        return bool(char) and (script.fullmatch(char) is not None or char in full_width)

    for paragraph in paragraphs:
        masked = mask_inline(paragraph.source)
        for index, char in enumerate(masked):
            entry = table.get(char)
            if entry is None or (char == "." and "..." in masked[max(0, index - 2) : index + 3]):
                continue
            left, before = _neighbour(masked, index, -1)
            right, after = _neighbour(masked, index, 1)
            context = entry["context"]
            wanted = native(before) if context == "before" else native(after) if context == "after" else native(before) or native(after)
            if not wanted:
                continue
            if "notBefore" in entry and index + 1 < len(masked) and re.match(entry["notBefore"], masked[index + 1]):
                continue
            yield (
                paragraph.start + left,
                paragraph.start + right,
                f"Half-width '{char}' in {language.name} text: write '{entry['fullWidth']}', with no space beside it.",
                entry["fullWidth"],
            )


def _neighbour(text: str, index: int, step: int) -> tuple[int, str]:
    """The span edge after skipping spaces from ``index`` in direction ``step``, and the character found there."""
    position = index + step
    while 0 <= position < len(text) and text[position] in _INLINE_SPACE:
        position += step
    if step < 0:
        return position + 1, text[position] if position >= 0 else ""
    return position, text[position] if position < len(text) else ""


def _quotation_marks(language: Language, paragraphs: list[Segment]) -> Iterable[Match]:
    (quotes,) = language.typography_data("quotes")
    opening, closing = quotes["outer"]
    for paragraph in paragraphs:
        masked = mask_inline(paragraph.source)
        for number, match in enumerate(re.finditer('"', masked)):
            replacement = opening if number % 2 == 0 else closing
            yield (
                paragraph.start + match.start(),
                paragraph.start + match.end(),
                f"Straight quotation mark in {language.name} text: write {opening}…{closing}.",
                replacement,
            )


def _ellipsis(language: Language, paragraphs: list[Segment]) -> Iterable[Match]:
    ellipsis, script_data = language.typography_data("ellipsis", "scriptCharacters")
    script = re.compile(script_data)
    for paragraph in paragraphs:
        masked = mask_inline(paragraph.source)
        for match in re.finditer(r"\.{3,}|(?<!…)…(?!…)", masked):
            left, before = _neighbour(masked, match.start(), -1)
            right, after = _neighbour(masked, match.end() - 1, 1)
            if script.fullmatch(before or " ") or script.fullmatch(after or " "):
                yield paragraph.start + left, paragraph.start + right, f"Write the {language.name} ellipsis '{ellipsis}'.", ellipsis


def _space_beside_full_width(language: Language, paragraphs: list[Segment]) -> Iterable[Match]:
    (full_width,) = language.typography_data("fullWidthPunctuation")
    converted = {entry["mark"] for entry in language.typography.get("punctuationWidth", ())}
    for paragraph in paragraphs:
        masked = mask_inline(paragraph.source)
        for match in re.finditer(r"[ \t]+", masked):
            before = masked[match.start() - 1] if match.start() else ""
            after = masked[match.end()] if match.end() < len(masked) else ""
            if not (before in full_width and before) and not (after in full_width and after):
                continue
            # A space beside a half-width mark or a lone ellipsis belongs to the rule that converts that mark.
            if before in converted or after in converted or _lone_ellipsis(masked, match.start() - 1) or _lone_ellipsis(masked, match.end()):
                continue
            yield paragraph.start + match.start(), paragraph.start + match.end(), f"No space beside full-width punctuation in {language.name}.", ""


def _lone_ellipsis(text: str, index: int) -> bool:
    return 0 <= index < len(text) and text[index] == "…" and text[index - 1 : index] != "…" and text[index + 1 : index + 2] != "…"


def _latin_spacing(language: Language, paragraphs: list[Segment]) -> Iterable[Match]:
    spacing, script_data = language.typography_data("latinSpacing", "scriptCharacters")
    script = re.compile(script_data)
    for paragraph in paragraphs:
        source = paragraph.source
        masked = mask_inline(source)
        for index in range(len(masked) - 1):
            a, b = masked[index], masked[index + 1]
            if source[index] != a or source[index + 1] != b:
                continue
            if (script.fullmatch(a) and _LATIN_OR_DIGIT.fullmatch(b)) or (_LATIN_OR_DIGIT.fullmatch(a) and script.fullmatch(b)):
                yield (
                    paragraph.start + index,
                    paragraph.start + index + 1,
                    f"Put a space between {language.name} text and Latin letters or digits ('{a}{spacing}{b}').",
                    a + spacing,
                )


_NUMERAL = r"(?<![\d.,])(\d{1,3}(?:,\d{3})+|\d+)(\.\d+)?"


def _number_words(language: Language, paragraphs: list[Segment]) -> Iterable[Match]:
    words, units, spacing, script_data = language.typography_data("numberWords", "largeNumberUnits", "latinSpacing", "scriptCharacters")
    script = re.compile(script_data)
    names = sorted(words, key=len, reverse=True)
    pattern = re.compile(_NUMERAL + r"\s*(" + "|".join(r"\s+".join(map(re.escape, n.split())) for n in names) + r")(?![A-Za-z])", re.IGNORECASE)
    ordered = sorted(units, key=lambda u: u["value"], reverse=True)
    for paragraph in paragraphs:
        masked = mask_inline(paragraph.source)
        for match in pattern.finditer(masked):
            numeral = match.group(1) + (match.group(2) or "")
            word = " ".join(match.group(3).lower().split())
            form = words[word]
            if "format" in form:
                replacement = form["format"].format(n=numeral)
            else:
                value = Decimal(numeral.replace(",", "")) * Decimal(form["multiply"])
                unit = next((u for u in ordered if value >= u["value"]), None)
                replacement = _plain(value / unit["value"]) + spacing + unit["unit"] if unit else _plain(value)
            end = match.end()
            right, after = _neighbour(masked, end - 1, 1)
            if right > end and script.fullmatch(after or " "):
                end = right
            yield (
                paragraph.start + match.start(),
                paragraph.start + end,
                f"English number word left in {language.name} text: write '{replacement}'.",
                replacement,
            )


def _plain(value: Decimal) -> str:
    return format(value.normalize(), "f")


def _number_format(language: Language, paragraphs: list[Segment]) -> Iterable[Match]:
    (numbers,) = language.typography_data("numbers")
    foreign = numbers["foreign"]
    group, decimal = re.escape(foreign["group"]), re.escape(foreign["decimal"])
    # Only forms that cannot be read as local numbers: a group mark and a decimal
    # mark together, two or more group marks, or a decimal mark followed by other
    # than three digits.
    pattern = re.compile(
        rf"(?<![\d.,])(?:\d{{1,3}}(?:{group}\d{{3}})+{decimal}\d+|\d{{1,3}}(?:{group}\d{{3}}){{2,}}|\d+{decimal}(?:\d{{1,2}}|\d{{4,}}))(?!\d|[.,]\d)"
    )
    for paragraph in paragraphs:
        masked = mask_inline(paragraph.source)
        for match in pattern.finditer(masked):
            whole, _, fraction = match.group().replace(foreign["group"], "").partition(foreign["decimal"])
            if len(whole) >= 3 + numbers["minimumGroupingDigits"]:
                head = len(whole) % 3 or 3
                whole = whole[:head] + "".join(numbers["group"] + whole[i : i + 3] for i in range(head, len(whole), 3))
            replacement = whole + (numbers["decimal"] + fraction if fraction else "")
            yield (
                paragraph.start + match.start(),
                paragraph.start + match.end(),
                f"Number in English form: {language.name} writes '{replacement}'.",
                replacement,
            )


TYPOGRAPHY_RULES: dict[str, Callable[[Language, list[Segment]], Iterable[Match]]] = {
    "punctuation-width": _punctuation_width,
    "quotation-marks": _quotation_marks,
    "ellipsis": _ellipsis,
    "space-beside-full-width": _space_beside_full_width,
    "latin-spacing": _latin_spacing,
    "number-words": _number_words,
    "number-format": _number_format,
}
