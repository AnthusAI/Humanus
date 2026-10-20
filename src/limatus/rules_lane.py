"""The deterministic rules lane: phrase, regex and built-in detectors.

Every detector runs only on prose segments, so code, quotes, directives and
the rest of the protected regions are never checked. Phrase detectors also
skip inline code, URLs, link targets and citations; regex detectors see the
raw prose so they can match URL fragments when a policy asks for that.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache
from typing import Callable, Iterable

from .editorial_density import analyze_density
from .editorial_diagnosis import (
    _CITATION_PATTERN,
    _CONTRACTION_PAIRS,
    _CRUTCH_WORDS,
    _EMPTY_LEADIN_PATTERNS,
    _INTENSIFIER_VAGUE_PATTERN,
    _LIST_SHAPED_PATTERN,
    _PASSIVE_PATTERN,
    _STAT_PERCENT_PATTERN,
    _STICKER_NUMBER_PATTERN,
    _check_redundancy,
    _sentence_has_statistical_claim,
    _sentence_has_unsupported_certainty,
)
from .editorial_style import DensityThresholds
from .emoji import EMOJI_PATTERN
from .policy_pack import BuiltinDetector, Detector, PhraseDetector, Policy, PolicyPack, RegexDetector
from .segmentation import Segment, SegmentedDocument, mask_inline


@dataclass(frozen=True)
class Hit:
    """A raw match: where it is and what to say about it."""

    policy: Policy
    detector: Detector
    start: int
    end: int
    message: str
    replacement: str | None = None
    segment: Segment | None = None  # set when the lane judged a specific segment
    status: str = "violation"
    probability: float | None = None


def run_rules_lane(document: SegmentedDocument, pack: PolicyPack) -> tuple[list[Hit], int]:
    """Run every enabled rules detector; return the hits and the detector count."""
    hits: list[Hit] = []
    count = 0
    for policy in pack.enabled_policies:
        for detector in policy.detectors:
            if detector.lane != "rules":
                continue
            count += 1
            for start, end, message, replacement in _run_detector(document, detector):
                hits.append(Hit(policy, detector, start, end, detector.message or message or policy.title, replacement))
    return _dedupe(hits), count


Match = tuple[int, int, "str | None", "str | None"]


def _run_detector(document: SegmentedDocument, detector: Detector) -> Iterable[Match]:
    paragraphs = [p for p in document.paragraphs if _applies(detector, p)]
    if isinstance(detector, PhraseDetector):
        pattern = _phrase_pattern(detector.phrases, detector.case_sensitive)
        for paragraph in paragraphs:
            for match in pattern.finditer(mask_inline(paragraph.source)):
                yield paragraph.start + match.start(), paragraph.start + match.end(), None, detector.replacement
    elif isinstance(detector, RegexDetector):
        flags = re.IGNORECASE if detector.ignore_case else 0
        pattern = re.compile(detector.pattern, flags)
        exceptions = [re.compile(e, flags) for e in detector.exceptions]
        for paragraph in paragraphs:
            excepted = [m.span() for e in exceptions for m in e.finditer(paragraph.source)]
            for match in pattern.finditer(paragraph.source):
                if match.end() > match.start() and not any(a <= match.start() and match.end() <= b for a, b in excepted):
                    yield paragraph.start + match.start(), paragraph.start + match.end(), None, None
    elif isinstance(detector, BuiltinDetector):
        sentences = [s for s in document.sentences() if _applies(detector, s)]
        yield from BUILTIN_CHECKS[detector.check](document, paragraphs, sentences, dict(detector.params))


def _applies(detector: Detector, segment: Segment) -> bool:
    return detector.blocks is None or segment.block in detector.blocks


@lru_cache(maxsize=512)
def _phrase_pattern(phrases: tuple[str, ...], case_sensitive: bool) -> re.Pattern[str]:
    alternatives = sorted((r"\s+".join(map(re.escape, p.split())) for p in phrases), key=len, reverse=True)
    return re.compile(rf"(?<!\w)(?:{'|'.join(alternatives)})(?!\w)", 0 if case_sensitive else re.IGNORECASE)


def _dedupe(hits: list[Hit]) -> list[Hit]:
    seen: set[tuple[str, str, int, int]] = set()
    unique: list[Hit] = []
    for hit in hits:
        key = (hit.policy.id, hit.detector.id, hit.start, hit.end)
        if key not in seen:
            seen.add(key)
            unique.append(hit)
    return unique


# --- built-in checks ------------------------------------------------------------
# Each takes (document, paragraphs, sentences, params) and yields matches.

BuiltinCheck = Callable[[SegmentedDocument, list[Segment], list[Segment], dict], Iterable[Match]]


def _sentence_check(predicate: Callable[[Segment], bool], message: str) -> BuiltinCheck:
    def run(document, paragraphs, sentences, params):
        for sentence in sentences:
            if predicate(sentence):
                yield sentence.start, sentence.end, message, None

    return run


def _empty_leadin(sentence: Segment) -> bool:
    return any(re.search(p, sentence.text, re.IGNORECASE) for p in _EMPTY_LEADIN_PATTERNS)


def _unsupported_certainty(sentence: Segment) -> bool:
    return _sentence_has_unsupported_certainty(sentence.text) and not _CITATION_PATTERN.search(sentence.source)


def _missing_attribution(sentence: Segment) -> bool:
    if not _sentence_has_statistical_claim(sentence.text) or _CITATION_PATTERN.search(sentence.source):
        return False
    return not (_STICKER_NUMBER_PATTERN.search(sentence.text) and not _STAT_PERCENT_PATTERN.search(sentence.text))


def _list_shaped_prose(document, paragraphs, sentences, params):
    for paragraph in paragraphs:
        if _LIST_SHAPED_PATTERN.search(paragraph.text):
            yield paragraph.start, paragraph.end, "Paragraph reads like an inline list without substantive development.", None


def _uniform_cadence(document, paragraphs, sentences, params):
    prose = [s for s in sentences if s.block == "paragraph"]
    if len(prose) < 5:
        return
    run_start = 0
    while run_start < len(prose):
        anchor = len(prose[run_start].text.split())
        run_end = run_start + 1
        while run_end < len(prose) and abs(len(prose[run_end].text.split()) - anchor) <= 3:
            run_end += 1
        if run_end - run_start >= 5:
            yield prose[run_start].start, prose[run_end - 1].end, "Five or more consecutive sentences share nearly identical length.", None
            run_start = run_end
        else:
            run_start += 1


def _overused_words(document, paragraphs, sentences, params):
    words = " ".join(p.text for p in paragraphs)
    total = max(len(words.split()), 1)
    threshold = max(3, round(total / 250))
    for word in _CRUTCH_WORDS:
        pattern = re.compile(rf"\b{re.escape(word)}\b", re.IGNORECASE)
        uses = len(pattern.findall(words))
        if uses <= threshold:
            continue
        for paragraph in paragraphs:
            first = pattern.search(mask_inline(paragraph.source))
            if first:
                yield (
                    paragraph.start + first.start(),
                    paragraph.start + first.end(),
                    f"'{word}' appears {uses} times across {total} words; cut most of them.",
                    None,
                )
                break


def _uncontracted_forms(document, paragraphs, sentences, params):
    for paragraph in paragraphs:
        masked = mask_inline(paragraph.source)
        taken: list[tuple[int, int]] = []
        for formal, contracted in _CONTRACTION_PAIRS:
            for match in re.finditer(rf"\b{re.escape(formal)}\b", masked, re.IGNORECASE):
                start, end = match.span()
                if any(start < b and end > a for a, b in taken):
                    continue
                if formal == "that is" and masked[end : end + 1] == ",":
                    continue
                matched = paragraph.source[start:end]
                replacement = contracted[0].upper() + contracted[1:] if matched[0].isupper() else contracted
                taken.append((start, end))
                yield paragraph.start + start, paragraph.start + end, f"'{matched}' could contract to '{replacement}'.", replacement


def _prose_only_text(document: SegmentedDocument) -> str:
    """The document with everything outside prose paragraphs blanked (offsets preserved)."""
    chars = [c if c == "\n" else " " for c in document.text]
    for paragraph in document.paragraphs:
        chars[paragraph.start : paragraph.end] = document.text[paragraph.start : paragraph.end]
    return "".join(chars)


def _redundancy(document, paragraphs, sentences, params):
    prose = _prose_only_text(document)
    for group in _check_redundancy(prose):
        for member in group["members"]:
            span = member["span"]
            start, end = span["start"], span["end"]
            while start < end and prose[start].isspace():
                start += 1
            while end > start and prose[end - 1].isspace():
                end -= 1
            yield start, end, "Repeats a four-word phrase used elsewhere in the document.", None


def _information_density(document, paragraphs, sentences, params):
    thresholds = DensityThresholds(
        min_words=params.get("minWords", 400),
        min_lexical_density=params.get("minLexicalDensity", 0.45),
        max_gzip_ratio=params.get("maxGzipRatio", 0.35),
    )
    for finding in analyze_density("\n\n".join(p.text for p in paragraphs), thresholds).findings:
        yield 0, len(document.text), finding["rationale"], None


def _contrast_cap(document, paragraphs, sentences, params):
    cap = params["max"]
    matches = [
        (p.start + m.start(), p.start + m.end())
        for p in paragraphs
        for m in re.finditer(r",\s*not\s+\w+", mask_inline(p.source), re.IGNORECASE)
    ]
    if len(matches) > cap:
        for start, end in matches:
            yield start, end, f"{len(matches)} 'X, not Y' contrasts in this document; the cap is {cap}.", None


def _no_emojis(document, paragraphs, sentences, params):
    for paragraph in paragraphs:
        for match in EMOJI_PATTERN.finditer(paragraph.source):
            yield paragraph.start + match.start(), paragraph.start + match.end(), "Contains an emoji.", ""


BUILTIN_CHECKS: dict[str, BuiltinCheck] = {
    "empty_leadin": _sentence_check(_empty_leadin, "Sentence opens with empty boilerplate instead of a concrete stake."),
    "list_shaped_prose": _list_shaped_prose,
    "vague_claim": _sentence_check(
        lambda s: bool(_INTENSIFIER_VAGUE_PATTERN.search(s.text)),
        "Sentence pairs empty intensifiers with vague transformation language.",
    ),
    "unsupported_certainty": _sentence_check(_unsupported_certainty, "Sentence states certainty without attributable evidence."),
    "uniform_cadence": _uniform_cadence,
    "redundancy": _redundancy,
    "passive_voice": _sentence_check(lambda s: bool(_PASSIVE_PATTERN.search(s.text)), "Sentence uses passive voice."),
    "missing_attribution": _sentence_check(_missing_attribution, "Numeric or statistical claim lacks attributable evidence."),
    "information_density": _information_density,
    "overused_words": _overused_words,
    "uncontracted_forms": _uncontracted_forms,
    "contrast_cap": _contrast_cap,
    "no_emojis": _no_emojis,
}
