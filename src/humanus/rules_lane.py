"""The deterministic rules lane: phrase, regex and built-in detectors.

Every detector runs only on prose segments, so code, block quotes, directives
and the rest of the protected regions are never checked. A finding that lies
entirely inside a direct quotation (double quotes) is dropped as well, because
the words are someone else's, unless the detector or its policy sets
``quotations: check`` (placeholder leaks and chatbot artifacts do). Phrase detectors also
skip inline code, URLs, link targets and citations; regex detectors see the
raw prose so they can match URL fragments when a policy asks for that.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, replace
from functools import lru_cache
from typing import Iterable

from .builtin_checks import BUILTIN_CHECKS, Match
from .policy_pack import BuiltinDetector, Detector, PhraseDetector, Policy, PolicyPack, RegexDetector
from .segmentation import Segment, SegmentedDocument, mask_inline

# Checks that judge the document as a whole run on its sentences and paragraphs, not table cells.
AGGREGATE_CHECKS = frozenset(
    {"information_density", "average_sentence_length", "reading_grade_level", "paragraph_length", "uniform_cadence", "overused_words"}
)
# Sentence-level checks that look inside the sentence for the words to judge.
QUOTATION_AWARE_CHECKS = frozenset({"passive_voice"})

_QUOTATION = re.compile(r"\u201c[^\u201c\u201d]+\u201d|\"[^\"\n]+\"")


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
    raw_probability: float | None = None


def run_rules_lane(document: SegmentedDocument, pack: PolicyPack) -> tuple[list[Hit], int]:
    """Run every enabled rules detector; return the hits and the detector count."""
    hits: list[Hit] = []
    count = 0
    quotations: list[tuple[int, int]] | None = None
    for policy in pack.enabled_policies:
        for detector in policy.detectors:
            if detector.lane != "rules":
                continue
            count += 1
            exempt = (detector.quotations or policy.quotations or "exempt") == "exempt"
            if exempt and quotations is None:
                quotations = quotation_spans(document)
            for start, end, message, replacement in _run_detector(document, detector, exempt):
                if exempt and any(a <= start and end <= b for a, b in quotations):
                    continue
                hits.append(Hit(policy, detector, start, end, detector.message or message or policy.title, replacement))
    return _dedupe(hits), count


def quotation_spans(document: SegmentedDocument) -> list[tuple[int, int]]:
    """Source spans of direct quotations: double-quoted passages in a paragraph, and block quotes."""
    spans = [(r.start, r.end) for r in document.protected if r.kind == "quote"]
    for paragraph in document.paragraphs:
        masked = mask_inline(paragraph.source)
        spans.extend((paragraph.start + m.start(), paragraph.start + m.end()) for m in _QUOTATION.finditer(masked))
    return spans


def _run_detector(document: SegmentedDocument, detector: Detector, exempt_quotations: bool = False) -> Iterable[Match]:
    paragraphs = [p for p in document.paragraphs if _applies(detector, p)]
    if isinstance(detector, PhraseDetector):
        pattern = _phrase_pattern(detector.phrases, detector.case_sensitive)
        exceptions = _phrase_pattern(detector.exceptions, detector.case_sensitive) if detector.exceptions else None
        for paragraph in paragraphs:
            masked = mask_inline(paragraph.source)
            excepted = [m.span() for m in exceptions.finditer(masked)] if exceptions else []
            for match in pattern.finditer(masked):
                if not any(a <= match.start() and match.end() <= b for a, b in excepted):
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
        params = dict(detector.params)
        if detector.check in AGGREGATE_CHECKS:
            document = replace(document, segments=tuple(s for s in document.segments if s.block != "tableCell"))
            paragraphs = [p for p in paragraphs if p.block != "tableCell"]
        if exempt_quotations and detector.check in QUOTATION_AWARE_CHECKS:
            params["_quotations"] = quotation_spans(document)
        sentences = [s for s in document.sentences() if _applies(detector, s)]
        yield from BUILTIN_CHECKS[detector.check](document, paragraphs, sentences, params)


def _applies(detector: Detector, segment: Segment) -> bool:
    return detector.blocks is None or segment.block in detector.blocks


@lru_cache(maxsize=512)
def _phrase_pattern(phrases: tuple[str, ...], case_sensitive: bool) -> re.Pattern[str]:
    alternatives = sorted((r"\s+".join(map(re.escape, p.split())) for p in phrases), key=len, reverse=True)
    return re.compile(rf"(?<!\w)(?:{'|'.join(alternatives)})(?!\w)", 0 if case_sensitive else re.IGNORECASE)


def _dedupe(hits: list[Hit]) -> list[Hit]:
    """One hit per policy and span; a hit that offers a replacement wins over one that does not."""
    unique: dict[tuple[str, int, int], Hit] = {}
    for hit in hits:
        key = (hit.policy.id, hit.start, hit.end)
        if key not in unique or (unique[key].replacement is None and hit.replacement is not None):
            unique[key] = hit
    return list(unique.values())
