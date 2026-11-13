"""The parity lane: a translation compared with its source, by code.

A check request that carries a ``source`` (the text the content was
translated from, in its own language) runs the policy pack's ``parity``
detectors. Each compares something that must survive translation: the
document's structure, link targets, citation keys, code, Markus directives
and their attributes, numbers and dates read as values, names and glossary
terms, quotations, emphasis that still renders, hedges and attributions, and
sentence counts. A difference is a faithfulness finding with a span in both
texts, and a replacement when the repair is certain.

Nothing here knows a language. How a language writes numbers, which words
hedge a claim and what a name looks like come from the two language packs; a
check whose data a pack lacks is reported as not run, by name and reason.

Block-by-block checks need the two texts to line up: the same blocks (and
directives) in the same order. When they do not, the ``structure`` check
reports where they part, and every block-by-block check is reported as not
run with that reason; none of them guesses an alignment.
"""
from __future__ import annotations

import re
import unicodedata
from collections import Counter
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from functools import cached_property, lru_cache
from typing import Any, Callable, Iterable, Iterator, Mapping

from markdown_it import MarkdownIt

from .languages import Language, LanguageCannotRun
from .policy_pack import ParityDetector, PolicyPack
from .rules_lane import Hit
from .segmentation import ProtectedRegion, SegmentedDocument, mask_inline, split_sentences

# (target start, target end, source start, source end, message, replacement)
ParityMatch = tuple[int, int, int, int, str, "str | None"]


class ParityCannotRun(Exception):
    """A parity check needs something the two texts do not give it (blocks that line up, markup); the reason is reported."""


@dataclass(frozen=True)
class GlossaryEntry:
    term: str
    translations: tuple[str, ...]  # approved forms; empty when the term is not translated
    case_sensitive: bool = False

    @property
    def accepted(self) -> tuple[str, ...]:
        return self.translations or (self.term,)


@dataclass(frozen=True)
class Unit:
    """One stretch of text and its translation: a prose block, a block quote, or a directive attribute value."""

    label: str  # paragraph | heading1..6 | listItem | tableCell | blockQuote | attribute:<name>
    source: tuple[int, int]
    target: tuple[int, int]

    @property
    def prose(self) -> bool:
        return not self.label.startswith("attribute:")


@dataclass(frozen=True)
class _Element:
    label: str  # structure label
    start: int
    end: int


@dataclass(frozen=True)
class _Attribute:
    name: str
    value: str
    start: int  # of the value
    end: int


@dataclass(frozen=True)
class _Directive:
    name: str  # "" for a container's closing fence
    start: int
    end: int
    attributes: tuple[_Attribute, ...]


class Bitext:
    """A source document and its translation, read in their own languages."""

    def __init__(self, source: SegmentedDocument, target: SegmentedDocument, format: str, glossary: tuple[GlossaryEntry, ...] = ()) -> None:
        self.source = source
        self.target = target
        self.format = format
        self.glossary = glossary

    @cached_property
    def source_elements(self) -> tuple[_Element, ...]:
        return _elements(self.source, self.source_directives)

    @cached_property
    def target_elements(self) -> tuple[_Element, ...]:
        return _elements(self.target, self.target_directives)

    @cached_property
    def source_directives(self) -> tuple[_Directive, ...]:
        return _directives(self.source)

    @cached_property
    def target_directives(self) -> tuple[_Directive, ...]:
        return _directives(self.target)

    @cached_property
    def misalignment(self) -> str | None:
        """Why the two texts' blocks do not line up, or None when they do."""
        source, target = [e.label for e in self.source_elements], [e.label for e in self.target_elements]
        if source == target:
            return None
        index = next((i for i, (a, b) in enumerate(zip(source, target)) if a != b), min(len(source), len(target)))
        return (
            f"the source and the translation do not have the same blocks in the same order (they part at block {index + 1}: "
            f"{_describe(source, index)} in the source, {_describe(target, index)} in the translation), so block-by-block checks cannot run"
        )

    @cached_property
    def _units(self) -> tuple[Unit, ...]:
        not_prose = {"directive", "code", "html", "table", "frontMatter"}
        units = [
            Unit(s.label, (s.start, s.end), (t.start, t.end))
            for s, t in zip(self.source_elements, self.target_elements)
            if s.label.split(":")[0] not in not_prose
        ]
        for s_dir, t_dir in zip(self.source_directives, self.target_directives):
            target_attributes = {a.name: a for a in t_dir.attributes}
            for attribute in s_dir.attributes:
                other = target_attributes.get(attribute.name)
                if other is not None and other.value != attribute.value:
                    units.append(Unit(f"attribute:{attribute.name}", (attribute.start, attribute.end), (other.start, other.end)))
        return tuple(units)

    def units(self) -> tuple[Unit, ...]:
        """The aligned units; raises :class:`ParityCannotRun` when the blocks do not line up."""
        if self.misalignment is not None:
            raise ParityCannotRun(self.misalignment)
        return self._units

    def source_text(self, unit: Unit) -> str:
        return self.source.text[unit.source[0] : unit.source[1]]

    def target_text(self, unit: Unit) -> str:
        return self.target.text[unit.target[0] : unit.target[1]]

    def target_span_for(self, source_index: int) -> tuple[int, int]:
        """The target unit lined up with the source unit containing ``source_index``; the whole translation when there is none."""
        if self.misalignment is None:
            for unit in self._units:
                if unit.source[0] <= source_index < unit.source[1]:
                    return unit.target
        return 0, len(self.target.text)

    def source_span_for(self, target_index: int) -> tuple[int, int]:
        if self.misalignment is None:
            for unit in self._units:
                if unit.target[0] <= target_index < unit.target[1]:
                    return unit.source
        return 0, len(self.source.text)


def run_parity_lane(bitext: Bitext, pack: PolicyPack) -> tuple[list[Hit], int, list[dict[str, str]]]:
    """Run every enabled parity detector; return the hits, the count run, and those that could not run with the reason."""
    hits: list[Hit] = []
    count = 0
    not_run: list[dict[str, str]] = []
    for policy in pack.enabled_policies:
        for detector in policy.detectors:
            if not isinstance(detector, ParityDetector):
                continue
            try:
                matches = list(PARITY_CHECKS[detector.check](bitext, detector.params))
            except (LanguageCannotRun, ParityCannotRun) as exc:
                not_run.append({"policyId": policy.id, "detectorId": detector.id, "reason": str(exc)})
                continue
            count += 1
            for t_start, t_end, s_start, s_end, message, replacement in matches:
                hits.append(Hit(policy, detector, t_start, t_end, detector.message or message, replacement, source_span=(s_start, s_end)))
    return hits, count, not_run


# --- reading the two documents ---------------------------------------------------------

_HEADING_ATX = re.compile(r"[ ]{0,3}(#{1,6})(?:\s|$)")
_DIRECTIVE_HEAD = re.compile(r"[ ]{0,3}(:{2,})([A-Za-z][\w-]*)?")
_ATTRIBUTE = re.compile(r"""([A-Za-z][\w:-]*)=(?:"([^"]*)"|'([^']*)'|([^\s"'}]+))""")
_LABEL = re.compile(r"\[([^\]]*)\]")


def _elements(document: SegmentedDocument, directives: tuple[_Directive, ...]) -> tuple[_Element, ...]:
    """Everything that gives a document its shape, in order: prose blocks by kind, block quotes, code, tables, directives."""
    elements = [_Element(_block_label(document.text, p.start, p.block or "paragraph"), p.start, p.end) for p in document.paragraphs]
    for region in document.protected:
        if region.kind == "directive":
            continue
        elements.append(_Element("blockQuote" if region.kind == "quote" else region.kind, region.start, region.end))
    for directive in directives:
        elements.append(_Element(f"directive:{directive.name or '/'}", directive.start, directive.end))
    return tuple(sorted(elements, key=lambda e: (e.start, e.end)))


def _block_label(text: str, start: int, block: str) -> str:
    if block != "heading":
        return block
    line_start = text.rfind("\n", 0, start) + 1
    atx = _HEADING_ATX.match(text, line_start)
    if atx:
        return f"heading{len(atx.group(1))}"
    line_end = text.find("\n", start)
    underline = text[line_end + 1 :].split("\n", 1)[0].strip() if line_end >= 0 else ""
    return "heading1" if underline.startswith("=") else "heading2"


def _directives(document: SegmentedDocument) -> tuple[_Directive, ...]:
    directives = []
    for region in document.protected:
        if region.kind != "directive":
            continue
        source = document.text[region.start : region.end]
        head = _DIRECTIVE_HEAD.match(source)
        if head is None:
            continue
        name = head.group(2) or ""
        attributes = []
        rest = head.end()
        label = _LABEL.match(source, rest)
        if label:
            attributes.append(_Attribute("[label]", label.group(1), region.start + label.start(1), region.start + label.end(1)))
            rest = label.end()
        brace = source.find("{", rest)
        if brace >= 0:
            close = source.rfind("}")
            for match in _ATTRIBUTE.finditer(source, brace, close if close > brace else len(source)):
                group = next(g for g in (2, 3, 4) if match.group(g) is not None)
                attributes.append(_Attribute(match.group(1), match.group(group), region.start + match.start(group), region.start + match.end(group)))
        directives.append(_Directive(name, region.start, region.end, tuple(attributes)))
    return tuple(directives)


def _describe(labels: list[str], index: int) -> str:
    return f"a {labels[index]}" if index < len(labels) else "the end of the document"


def _blank(text: str, regions: Iterable[ProtectedRegion | tuple[int, int]]) -> str:
    chars = list(text)
    for region in regions:
        start, end = (region.start, region.end) if isinstance(region, ProtectedRegion) else region
        for index in range(start, end):
            if chars[index] != "\n":
                chars[index] = " "
    return "".join(chars)


# --- structure -------------------------------------------------------------------------


def _structure(bitext: Bitext, params: Mapping[str, Any]) -> Iterator[ParityMatch]:
    if bitext.misalignment is None:
        return
    source, target = bitext.source_elements, bitext.target_elements
    index = next((i for i, (a, b) in enumerate(zip(source, target)) if a.label != b.label), min(len(source), len(target)))
    s_span = (source[index].start, source[index].end) if index < len(source) else (len(bitext.source.text),) * 2
    t_span = (target[index].start, target[index].end) if index < len(target) else (len(bitext.target.text),) * 2
    yield (
        *t_span,
        *s_span,
        f"The translation's structure differs from the source's at block {index + 1}: "
        f"{_describe([e.label for e in source], index)} in the source, {_describe([e.label for e in target], index)} in the translation. "
        f"Source: {_census(source)}. Translation: {_census(target)}.",
        None,
    )


def _census(elements: tuple[_Element, ...]) -> str:
    counts = Counter(e.label.split(":")[0] for e in elements)
    return ", ".join(f"{n} {label}" for label, n in sorted(counts.items()))


# --- tokens that must be the same set: links, citations, code ----------------------------

_INLINE_CODE = re.compile(r"(`+)(?:(?!\1).)+?\1", re.S)
_LINK_DESTINATION = re.compile(r"\]\(\s*<?([^)\s>]+)>?(?:\s+\"[^\"]*\")?\s*\)")
_REFERENCE_DEFINITION = re.compile(r"^[ ]{0,3}\[[^\]]+\]:\s*<?([^\s>]+)>?", re.M)
_AUTOLINK = re.compile(r"<((?:https?|mailto|ftp):[^>\s]+)>", re.I)
_BARE_URL = re.compile(r"\b(?:https?|ftp)://[A-Za-z0-9\-._~:/?#\[\]@!$&'*+,;=%]+")
_CITATION = re.compile(r"\[(-?@[^\]]+)\]")
_CITATION_KEY = re.compile(r"@([\w][\w:./#+-]*\w|\w)")


def _verbatim_text(document: SegmentedDocument) -> str:
    """The document with code, directives, raw HTML and front matter blanked, keeping offsets."""
    return _blank(document.text, (r for r in document.protected if r.kind in {"code", "directive", "html", "frontMatter"}))


def _links_in(document: SegmentedDocument) -> list[tuple[str, int, int]]:
    text = _verbatim_text(document)
    text = _blank(text, (m.span() for m in _INLINE_CODE.finditer(text)))
    links = []
    for pattern in (_LINK_DESTINATION, _REFERENCE_DEFINITION, _AUTOLINK):
        for match in pattern.finditer(text):
            links.append((match.group(1), match.start(1), match.end(1)))
    remaining = _blank(text, ((start, end) for _, start, end in links))
    for match in _BARE_URL.finditer(remaining):
        url = match.group().rstrip(".,;:!?'")
        links.append((url, match.start(), match.start() + len(url)))
    return sorted(links, key=lambda link: link[1])


def _citations_in(document: SegmentedDocument) -> list[tuple[str, int, int]]:
    text = _verbatim_text(document)
    text = _blank(text, (m.span() for m in _INLINE_CODE.finditer(text)))
    keys = []
    for citation in _CITATION.finditer(text):
        for key in _CITATION_KEY.finditer(citation.group(1)):
            keys.append((key.group(0), citation.start(1) + key.start(), citation.start(1) + key.end()))
    return keys


def _code_in(document: SegmentedDocument) -> list[tuple[str, int, int]]:
    text = _blank(document.text, (r for r in document.protected if r.kind in {"code", "html", "directive", "frontMatter"}))
    spans = [(m.group(), m.start(), m.end()) for m in _INLINE_CODE.finditer(text)]
    spans += [(document.text[r.start : r.end], r.start, r.end) for r in document.protected if r.kind in {"code", "html"}]
    return sorted(spans, key=lambda s: s[1])


def _same_tokens(bitext: Bitext, extract: Callable[[SegmentedDocument], list[tuple[str, int, int]]], what: str) -> Iterator[ParityMatch]:
    """Every token of the source appears in the translation as often, byte for byte, and no other."""
    source, target = extract(bitext.source), extract(bitext.target)
    available = Counter(key for key, _, _ in target)
    for key, start, end in source:
        if available[key] > 0:
            available[key] -= 1
            continue
        yield (*bitext.target_span_for(start), start, end, f"The translation drops the {what} {_quote(key)}, which the source has.", None)
    available = Counter(key for key, _, _ in source)
    for key, start, end in target:
        if available[key] > 0:
            available[key] -= 1
            continue
        yield (start, end, *bitext.source_span_for(start), f"The translation has the {what} {_quote(key)}, which the source does not.", None)


def _links(bitext: Bitext, params: Mapping[str, Any]) -> Iterator[ParityMatch]:
    return _same_tokens(bitext, _links_in, "link target")


def _citations(bitext: Bitext, params: Mapping[str, Any]) -> Iterator[ParityMatch]:
    return _same_tokens(bitext, _citations_in, "citation key")


def _code(bitext: Bitext, params: Mapping[str, Any]) -> Iterator[ParityMatch]:
    return _same_tokens(bitext, _code_in, "code or raw HTML")


def _quote(text: str) -> str:
    short = text if len(text) <= 80 else text[:77] + "..."
    return f"“{short}”"


# --- directives ------------------------------------------------------------------------


def _directive_check(bitext: Bitext, params: Mapping[str, Any]) -> Iterator[ParityMatch]:
    translatable = set(params["translatable"]) | {"[label]"}
    source, target = bitext.source_directives, bitext.target_directives
    names_s, names_t = [d.name for d in source], [d.name for d in target]
    if names_s != names_t:
        index = next((i for i, (a, b) in enumerate(zip(names_s, names_t)) if a != b), min(len(names_s), len(names_t)))
        s_span = (source[index].start, source[index].end) if index < len(source) else (len(bitext.source.text),) * 2
        t_span = (target[index].start, target[index].end) if index < len(target) else (len(bitext.target.text),) * 2
        yield (
            *t_span,
            *s_span,
            f"The translation's directives differ from the source's at directive {index + 1} "
            f"({_directive_name(names_s, index)} in the source, {_directive_name(names_t, index)} in the translation).",
            None,
        )
        return
    for s_dir, t_dir in zip(source, target):
        target_attributes = {a.name: a for a in t_dir.attributes}
        source_names = {a.name for a in s_dir.attributes}
        for attribute in s_dir.attributes:
            other = target_attributes.get(attribute.name)
            if other is None:
                yield t_dir.start, t_dir.end, attribute.start, attribute.end, f"The translation's {s_dir.name} directive drops the attribute '{attribute.name}'.", None
            elif attribute.name not in translatable and other.value != attribute.value:
                yield (
                    other.start,
                    other.end,
                    attribute.start,
                    attribute.end,
                    f"The {s_dir.name} directive's '{attribute.name}' attribute is not translated; it must stay as the source has it: {_quote(attribute.value)}.",
                    attribute.value,
                )
        for attribute in t_dir.attributes:
            if attribute.name not in source_names:
                yield attribute.start, attribute.end, s_dir.start, s_dir.end, f"The translation's {s_dir.name} directive adds the attribute '{attribute.name}'.", None


def _directive_name(names: list[str], index: int) -> str:
    if index >= len(names):
        return "none"
    return f"'{names[index]}'" if names[index] else "a closing fence"


# --- numbers and dates -----------------------------------------------------------------


@dataclass(frozen=True)
class _Number:
    start: int  # within the unit text
    end: int
    keys: frozenset  # Decimal values it can be read as, and its digits as written ("raw:...")
    scaled: bool  # a scale word (million, 万) follows
    value: Decimal | None  # the value in its own language's form, when it has one


_DIGITS = re.compile(r"(?<![A-Za-z0-9])\d+(?:[.,]\d+)*")
_NUMBER_FORMS: dict[tuple[str, str], re.Pattern[str]] = {}


def _read(token: str, decimal: str, group: str) -> Decimal | None:
    key = (decimal, group)
    if key not in _NUMBER_FORMS:
        d, g = re.escape(decimal), re.escape(group)
        _NUMBER_FORMS[key] = re.compile(rf"\d+|\d{{1,3}}(?:{g}\d{{3}})+(?:{d}\d+)?|\d+{d}\d+")
    if not _NUMBER_FORMS[key].fullmatch(token):
        return None
    try:
        return Decimal(token.replace(group, "").replace(decimal, "."))
    except InvalidOperation:
        return None


def _numbers_in(text: str, language: Language) -> tuple[list[_Number], list[_Number]]:
    """Numbers written in digits (hard) and in words, month names or native numerals (soft), with their values."""
    decimal, group, also_read, scales, words, months, numerals = language.number_data(
        "decimal", "group", "alsoRead", "scales", "words", "months", "numerals"
    )
    masked = mask_inline(text)
    scale_pattern = language.phrase_pattern(tuple(scales)) if scales else None
    scale_values = {" ".join(name.lower().split()): Decimal(str(value)) for name, value in scales.items()}

    def scale_after(end: int) -> tuple[int, Decimal]:
        if scale_pattern is None:
            return end, Decimal(1)
        gap = len(masked[end:]) - len(masked[end:].lstrip(" \t "))
        match = scale_pattern.match(masked, end + gap)
        if match is None:
            return end, Decimal(1)
        return match.end(), scale_values[" ".join(match.group().lower().split())]

    hard: list[_Number] = []
    for match in _DIGITS.finditer(masked):
        token = match.group()
        local = _read(token, decimal, group)
        values = {v for v in [local, *(_read(token, f["decimal"], f["group"]) for f in also_read)] if v is not None}
        end, scale = scale_after(match.end())
        keys = {v * scale for v in values} | {f"raw:{token}"}
        hard.append(_Number(match.start(), end, frozenset(keys), scale != 1, None if local is None else local * scale))

    soft: list[_Number] = []
    if scale_pattern is not None:
        # A scale word on its own is a value too: "a billion times", "hundreds".
        after_digits = {n.end for n in hard}
        for m in scale_pattern.finditer(masked):
            if m.end() not in after_digits:
                value = scale_values[" ".join(m.group().lower().split())]
                soft.append(_Number(m.start(), m.end(), frozenset({value}), True, value))
    word_values = {name.lower(): Decimal(str(value)) for name, value in words.items()}
    if word_values:
        found = [(m.start(), m.end(), word_values[m.group().lower()]) for m in language.phrase_pattern(tuple(words)).finditer(masked)]
        for start, end, value in _join_compound_words(found, masked):
            end, scale = scale_after(end)
            soft.append(_Number(start, end, frozenset({value * scale}), scale != 1, value * scale))
    if months:
        month_values = {name.lower(): Decimal(index + 1) for index, name in enumerate(months)}
        for m in language.phrase_pattern(tuple(months)).finditer(masked):
            soft.append(_Number(m.start(), m.end(), frozenset({month_values[m.group().lower()]}), False, month_values[m.group().lower()]))
    if numerals:
        characters = "".join(numerals["digits"]) + "".join(numerals["units"])
        for m in re.finditer(f"[{re.escape(characters)}]+", masked):
            value = _native_numeral(m.group(), numerals)
            soft.append(_Number(m.start(), m.end(), frozenset({value}), False, value))
    return hard, soft


def _join_compound_words(found: list[tuple[int, int, Decimal]], text: str) -> list[tuple[int, int, Decimal]]:
    """"twenty-five" and "twenty five" are one number, 25."""
    joined: list[tuple[int, int, Decimal]] = []
    for start, end, value in found:
        if joined:
            p_start, p_end, p_value = joined[-1]
            if text[p_end:start] in {"-", " "} and p_value >= 20 and p_value % 10 == 0 and p_value < 100 and value < 10:
                joined[-1] = (p_start, end, p_value + value)
                continue
        joined.append((start, end, value))
    return joined


def _native_numeral(run: str, numerals: Mapping[str, Any]) -> Decimal:
    """A run of native numeral characters as a value: 两百 = 200, 一万二千 = 12000, 二〇二六 = 2026."""
    digits, units = numerals["digits"], numerals["units"]
    if all(ch in digits for ch in run):
        return Decimal("".join(str(digits[ch]) for ch in run))
    total, section, number = Decimal(0), Decimal(0), Decimal(0)
    big = sorted({v for v in units.values() if v >= 10000})
    for ch in run:
        if ch in digits:
            number = Decimal(digits[ch])
        elif units[ch] in big:
            section += number
            total = (total + section) * Decimal(units[ch]) if total and total < units[ch] else total + section * Decimal(units[ch])
            section, number = Decimal(0), Decimal(0)
        else:
            section += (number or Decimal(1)) * Decimal(units[ch])
            number = Decimal(0)
    return total + section + number


def _numbers(bitext: Bitext, params: Mapping[str, Any]) -> Iterator[ParityMatch]:
    source_language, target_language = bitext.source.language, bitext.target.language
    for unit in bitext.units():
        s_text, t_text = bitext.source_text(unit), bitext.target_text(unit)
        s_hard, s_soft = _numbers_in(s_text, source_language)
        t_hard, t_soft = _numbers_in(t_text, target_language)
        used: set[int] = set()
        missing: list[_Number] = []
        for number in s_hard:
            match = next((i for i, other in enumerate(t_hard) if i not in used and number.keys & other.keys), None)
            if match is not None:
                used.add(match)
            elif not any(number.keys & other.keys for other in t_soft):
                missing.append(number)
        added = [n for i, n in enumerate(t_hard) if i not in used and not any(n.keys & other.keys for other in s_soft)]
        s0, t0 = unit.source[0], unit.target[0]
        for s_num, t_num in zip(missing, added):
            s_surface, t_surface = s_text[s_num.start : s_num.end], t_text[t_num.start : t_num.end]
            yield (
                t0 + t_num.start,
                t0 + t_num.end,
                s0 + s_num.start,
                s0 + s_num.end,
                f"A number changed: the source says {_quote(s_surface)} where the translation says {_quote(t_surface)}.",
                _render_fix(s_num, s_surface, t_num, source_language, target_language),
            )
        for s_num in missing[len(added) :]:
            yield (
                *unit.target,
                s0 + s_num.start,
                s0 + s_num.end,
                f"The translation drops the number {_quote(s_text[s_num.start : s_num.end])}: no value in it matches.",
                None,
            )
        for t_num in added[len(missing) :]:
            yield (
                t0 + t_num.start,
                t0 + t_num.end,
                *unit.source,
                f"The translation adds the number {_quote(t_text[t_num.start : t_num.end])}, which the source does not have.",
                None,
            )


def _render_fix(source: _Number, surface: str, target: _Number, source_language: Language, target_language: Language) -> str | None:
    """The source's value written the target language's way, when the swap is certain (no scale words on either side)."""
    if source.scaled or target.scaled or source.value is None:
        return None
    decimal, group, minimum = target_language.number_data("decimal", "group", "minimumGroupingDigits")
    value = source.value
    written = str(int(value)) if value == value.to_integral_value() else format(value.normalize(), "f")
    whole, _, fraction = written.partition(".")
    if source_language.numbers["group"] in surface and len(whole) >= 3 + minimum:
        head = len(whole) % 3 or 3
        whole = whole[:head] + "".join(group + whole[i : i + 3] for i in range(head, len(whole), 3))
    return whole + (decimal + fraction if fraction else "")


_ISO_DATE = re.compile(r"(?<![\d-])(\d{4})-(\d{2})-(\d{2})(?![\d-])")


def _iso_dates(bitext: Bitext, params: Mapping[str, Any]) -> Iterator[ParityMatch]:
    """A date the source writes as YYYY-MM-DD is a fixed format (a byline, a log line): the translation keeps it as is."""
    target_language = bitext.target.language
    for unit in bitext.units():
        s_text, t_text = bitext.source_text(unit), bitext.target_text(unit)
        t_masked = mask_inline(t_text)
        for match in _ISO_DATE.finditer(mask_inline(s_text)):
            if match.group() in t_masked:
                continue
            year, month, day = (Decimal(int(g)) for g in match.groups())
            hard, soft = _numbers_in(t_text, target_language)
            window = _date_window(hard + soft, year, month, day)
            s_span = (unit.source[0] + match.start(), unit.source[0] + match.end())
            if window is None:
                yield (*unit.target, *s_span, f"The source writes the date {match.group()} in a fixed format; the translation does not keep it.", None)
            else:
                start, end = window
                yield (
                    unit.target[0] + start,
                    unit.target[0] + end,
                    *s_span,
                    f"The source writes the date {match.group()} in a fixed format (ISO 8601); the translation rewrites it as {_quote(t_text[start:end])}. Keep it as written.",
                    match.group(),
                )


def _date_window(numbers: list[_Number], year: Decimal, month: Decimal, day: Decimal) -> tuple[int, int] | None:
    """The shortest stretch holding the year, the month and the day, each read as a value."""
    ordered = sorted(numbers, key=lambda n: n.start)
    best: tuple[int, int] | None = None
    for i, first in enumerate(ordered):
        wanted = {"y": year, "m": month, "d": day}
        for number in ordered[i:]:
            for part, value in list(wanted.items()):
                if value in number.keys:
                    del wanted[part]
                    break
            if not wanted:
                if best is None or number.end - first.start < best[1] - best[0]:
                    best = (first.start, number.end)
                break
    return best


# --- names and glossary ----------------------------------------------------------------

_WORD = re.compile(r"[^\W_](?:[\w&+.]*[^\W_])?")


def _names_in(text: str, label: str, language: Language) -> list[tuple[str, int, int, tuple[str, ...]]]:
    """Proper names in a unit, as (name, start, end, forms that count as keeping it), by the language's name shape."""
    shape = language.name_shape()
    masked = mask_inline(text)
    if shape == "latin-runs":
        runs = re.finditer(r"[A-Za-z][A-Za-z0-9&+.-]*(?:[ ][A-Za-z0-9][A-Za-z0-9&+.-]*)*(?<![.-])", masked)
        return [(m.group(), m.start(), m.end(), (m.group(),)) for m in runs]
    if shape != "capitalized":
        raise LanguageCannotRun(f"the {language.tag} language pack names an unknown name shape '{shape}'")
    common = {w.lower() for w in language.lexicons.get("functionWords", ())} | {w.lower() for w in language.lexicons.get("notNames", ())}
    common |= {m.lower() for m in language.numbers.get("months", ())}
    starts = {start for start, _ in split_sentences(masked, language)}
    title_like = label.startswith("heading")
    names: list[tuple[str, int, int, tuple[str, ...]]] = []
    group: list[re.Match[str]] = []

    def flush() -> None:
        tokens = list(group)
        group.clear()
        if not tokens:
            return
        if title_like:
            # Headings are title-cased: only a word shaped like a name is one.
            names.extend((t.group(), t.start(), t.end(), (t.group(),)) for t in tokens if _shaped(t.group()))
            return
        whole = masked[tokens[0].start() : tokens[-1].end()]
        if _sentence_initial(masked, tokens[0].start(), starts) and not _shaped(tokens[0].group()):
            # A capital that opens a sentence proves nothing: "Hugging Face said" or "Yesterday OpenAI said".
            if len(tokens) == 1:
                return
            rest = masked[tokens[1].start() : tokens[-1].end()]
            names.append((whole, tokens[0].start(), tokens[-1].end(), (whole, rest)))
            return
        names.append((whole, tokens[0].start(), tokens[-1].end(), (whole,)))

    for token in _WORD.finditer(masked):
        word = token.group()
        name_like = (word[0].isupper() or _shaped(word)) and word.lower() not in common and not word.isdigit()
        if name_like and group and masked[group[-1].end() : token.start()] == " ":
            group.append(token)
        else:
            flush()
            if name_like:
                group.append(token)
    flush()
    return names


def _shaped(word: str) -> bool:
    """A name by its shape alone: an acronym (METR), a capital inside (OpenAI, iPhone), or letters with digits (GPT-6)."""
    letters = [c for c in word if c.isalpha()]
    if len(letters) >= 2 and all(c.isupper() for c in letters):
        return True
    if any(c.isupper() for c in word[1:]) and any(c.islower() for c in word):
        return True
    return any(c.isdigit() for c in word) and bool(letters)


_FIELD_SEPARATORS = "·•|:—–"


def _sentence_initial(text: str, index: int, starts: set[int]) -> bool:
    """Whether the word at ``index`` opens a sentence, or a field after a separator ("By the desk · Published ...")."""
    before = [s for s in starts if s <= index]
    if not before or not _WORD.search(text, max(before), index):
        return True
    previous = text[:index].rstrip(" \t\"'“‘«¿¡([*_")
    return bool(previous) and previous[-1] in _FIELD_SEPARATORS


def _glossary_spans(text: str, language: Language, glossary: tuple[GlossaryEntry, ...]) -> list[tuple[GlossaryEntry, int, int]]:
    masked = mask_inline(text)
    return [(entry, m.start(), m.end()) for entry in glossary for m in language.phrase_pattern((entry.term,), entry.case_sensitive).finditer(masked)]


def _contains(text: str, forms: Iterable[str], language: Language, case_sensitive: bool) -> bool:
    return language.phrase_pattern(tuple(forms), case_sensitive).search(mask_inline(text)) is not None


def _names(bitext: Bitext, params: Mapping[str, Any]) -> Iterator[ParityMatch]:
    source_language, target_language = bitext.source.language, bitext.target.language
    for unit in bitext.units():
        s_text, t_text = bitext.source_text(unit), bitext.target_text(unit)
        covered = [(start, end) for _, start, end in _glossary_spans(s_text, source_language, bitext.glossary)]
        seen: set[str] = set()
        for name, start, end, forms in _names_in(s_text, unit.label, source_language):
            if name in seen or any(a < end and start < b for a, b in covered):
                continue
            seen.add(name)
            if not _contains(t_text, forms, target_language, case_sensitive=True):
                yield (
                    *unit.target,
                    unit.source[0] + start,
                    unit.source[0] + end,
                    f"The name {_quote(name)} is missing from the translation. Names stay as written unless the glossary gives an approved local form.",
                    None,
                )


def _glossary(bitext: Bitext, params: Mapping[str, Any]) -> Iterator[ParityMatch]:
    source_language, target_language = bitext.source.language, bitext.target.language
    for unit in bitext.units():
        s_text, t_text = bitext.source_text(unit), bitext.target_text(unit)
        seen: set[str] = set()
        for entry, start, end in _glossary_spans(s_text, source_language, bitext.glossary):
            if entry.term in seen:
                continue
            seen.add(entry.term)
            if _contains(t_text, entry.accepted, target_language, entry.case_sensitive):
                continue
            if entry.translations:
                forms = " or ".join(_quote(t) for t in entry.translations)
                message = f"The glossary renders {_quote(entry.term)} as {forms} in {target_language.tag}; the translation does not use it. Use {_quote(entry.translations[0])}."
            else:
                message = f"{_quote(entry.term)} is on the do-not-translate list; the translation must keep it unchanged."
            yield (*unit.target, unit.source[0] + start, unit.source[0] + end, message, None)


# --- quotations, emphasis, hedges, attributions, sentences --------------------------------


def _quotation_spans(text: str, language: Language) -> list[tuple[int, int]]:
    return [m.span() for m in language.quotation_pattern.finditer(mask_inline(text))]


def _quotations(bitext: Bitext, params: Mapping[str, Any]) -> Iterator[ParityMatch]:
    for unit in bitext.units():
        s_text, t_text = bitext.source_text(unit), bitext.target_text(unit)
        s_quotes, t_quotes = _quotation_spans(s_text, bitext.source.language), _quotation_spans(t_text, bitext.target.language)
        if len(t_quotes) >= len(s_quotes):
            # More quotation marks is a convention (Chinese quotes a term English sets in italics), not a lost quotation.
            continue
        if not t_quotes:
            for start, end in s_quotes:
                yield (*unit.target, unit.source[0] + start, unit.source[0] + end, f"The translation drops the quotation {s_text[start:end]}.", None)
            continue
        yield (
            *unit.target,
            *unit.source,
            f"The source has {len(s_quotes)} quotation(s) here and the translation only {len(t_quotes)}; each quoted passage should stay a quotation.",
            None,
        )


@lru_cache(maxsize=1)
def _inline_parser() -> MarkdownIt:
    return MarkdownIt("commonmark")


def _emphasis_count(text: str) -> int:
    tokens = _inline_parser().parseInline(text)
    return sum(1 for token in tokens for child in (token.children or ()) if child.type in {"em_open", "strong_open"})


_STUCK_CLOSER = re.compile(r"(?<=[^\s*_])([*_]{1,3})(?=[^\s*_])")


def _emphasis(bitext: Bitext, params: Mapping[str, Any]) -> Iterator[ParityMatch]:
    """Emphasis the source renders must render in the translation; a closing marker stuck to a word after punctuation does not."""
    if bitext.format == "text":
        raise ParityCannotRun("plain text has no emphasis markup to compare")
    full_width = bitext.target.language.typography.get("fullWidthPunctuation", "")
    for unit in bitext.units():
        if not unit.prose:
            continue
        s_text, t_text = bitext.source_text(unit), bitext.target_text(unit)
        wanted, have = _emphasis_count(s_text), _emphasis_count(t_text)
        if have >= wanted:
            continue
        repaired = False
        for match in _STUCK_CLOSER.finditer(t_text):
            mark_at = match.start() - 1
            if not _is_punctuation(t_text[mark_at]):
                continue
            if t_text[mark_at] in full_width:
                # A full-width mark carries its own spacing: move it outside the closer instead of adding a space beside it.
                start, end, replacement = mark_at, match.end(), match.group(1) + t_text[mark_at]
            else:
                start, end, replacement = match.start(), match.end(), match.group(1) + " "
            if _emphasis_count(t_text[:start] + replacement + t_text[end:]) <= have:
                continue
            repaired = True
            yield (
                unit.target[0] + start,
                unit.target[0] + end,
                *unit.source,
                f"The closing emphasis marker {_quote(match.group(1))} after {_quote(t_text[mark_at])} is followed directly by text, so the emphasis does not render and the markers show.",
                replacement,
            )
        if not repaired:
            yield (*unit.target, *unit.source, f"The source renders {wanted} emphasis span(s) here and the translation {have}.", None)


def _is_punctuation(char: str) -> bool:
    return unicodedata.category(char)[0] in {"P", "S"}


def _lexicon_spans(text: str, language: Language, lexicon: str) -> list[tuple[int, int]]:
    return [m.span() for m in language.phrase_pattern(language.lexicon(lexicon)).finditer(mask_inline(text))]


def _hedges(bitext: Bitext, params: Mapping[str, Any]) -> Iterator[ParityMatch]:
    """A translation keeps every hedge (may, 可能) and adds no certainty (clearly, 显然) that the source does not have."""
    source_language, target_language = bitext.source.language, bitext.target.language
    for name in ("hedges", "certainty"):
        source_language.lexicon(name), target_language.lexicon(name)
    for unit in bitext.units():
        s_text, t_text = bitext.source_text(unit), bitext.target_text(unit)
        yield from _fewer(unit, s_text, _lexicon_spans(s_text, source_language, "hedges"), _lexicon_spans(t_text, target_language, "hedges"), "hedge")
        s_sure, t_sure = _lexicon_spans(s_text, source_language, "certainty"), _lexicon_spans(t_text, target_language, "certainty")
        if len(t_sure) > len(s_sure):
            if not s_sure:
                for start, end in t_sure:
                    yield (
                        unit.target[0] + start,
                        unit.target[0] + end,
                        *unit.source,
                        f"The translation adds certainty with {_quote(t_text[start:end])}, which the source does not express.",
                        None,
                    )
            else:
                yield (*unit.target, *unit.source, f"The translation states this more certainly than the source: {len(t_sure)} certainty word(s) against {len(s_sure)}.", None)


def _attributions(bitext: Bitext, params: Mapping[str, Any]) -> Iterator[ParityMatch]:
    """Every attribution (says, according to, 表示) in the source keeps its counterpart in the translation."""
    source_language, target_language = bitext.source.language, bitext.target.language
    source_language.lexicon("attribution"), target_language.lexicon("attribution")
    for unit in bitext.units():
        s_text, t_text = bitext.source_text(unit), bitext.target_text(unit)
        yield from _fewer(
            unit, s_text, _lexicon_spans(s_text, source_language, "attribution"), _lexicon_spans(t_text, target_language, "attribution"), "attribution"
        )


def _fewer(unit: Unit, s_text: str, s_spans: list[tuple[int, int]], t_spans: list[tuple[int, int]], what: str) -> Iterator[ParityMatch]:
    if len(t_spans) >= len(s_spans):
        return
    if not t_spans:
        for start, end in s_spans:
            yield (*unit.target, unit.source[0] + start, unit.source[0] + end, f"The translation drops the {what} {_quote(s_text[start:end])}.", None)
        return
    found = ", ".join(_quote(s_text[a:b]) for a, b in s_spans)
    yield (*unit.target, *unit.source, f"The source has {len(s_spans)} {what}(s) here ({found}) and the translation {len(t_spans)}.", None)


def _sentence_count(bitext: Bitext, params: Mapping[str, Any]) -> Iterator[ParityMatch]:
    """A block whose translation has fewer sentences than its source may have lost one. More sentences is a translator's split."""
    for unit in bitext.units():
        if not unit.prose:
            continue
        s_text, t_text = bitext.source_text(unit), bitext.target_text(unit)
        s_count = len(split_sentences(s_text, bitext.source.language))
        t_count = len(split_sentences(t_text, bitext.target.language))
        if t_count < s_count:
            yield (*unit.target, *unit.source, f"The source has {s_count} sentences here and the translation only {t_count}: check that no sentence was lost.", None)


PARITY_CHECKS: dict[str, Callable[[Bitext, Mapping[str, Any]], Iterable[ParityMatch]]] = {
    "structure": _structure,
    "links": _links,
    "citations": _citations,
    "code": _code,
    "directives": _directive_check,
    "numbers": _numbers,
    "iso_dates": _iso_dates,
    "names": _names,
    "glossary": _glossary,
    "quotations": _quotations,
    "emphasis": _emphasis,
    "hedges": _hedges,
    "attributions": _attributions,
    "sentence_count": _sentence_count,
}
