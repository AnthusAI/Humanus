"""The deterministic rules lane: phrase, regex and built-in detectors.

Every detector runs only on prose segments, so code, block quotes, directives
and the rest of the protected regions are never checked. A finding that lies
entirely inside a direct quotation (double quotes) is dropped as well, because
the words are someone else's, unless the detector or its policy sets
``quotations: check`` (placeholder leaks and chatbot artifacts do). Phrase detectors also
skip inline code, URLs, link targets and citations; regex detectors see the
raw prose so they can match URL fragments when a policy asks for that.

Everything that depends on the language comes from the document's language
pack: the quotation marks, how a phrase matches (on word boundaries, or
anywhere in a script written without spaces), and which built-in checks can
run. A detector the language cannot run is reported in ``notRun`` with the
reason, never skipped in silence.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, replace
from typing import Any, Iterable, Mapping

from .builtin_checks import BUILTIN_CHECKS, Match
from .languages import LanguageCannotRun
from .policy_pack import BuiltinDetector, Detector, PhraseDetector, Policy, PolicyPack, RegexDetector
from .segmentation import Segment, SegmentedDocument, mask_inline

# Checks that judge the document as a whole run on its sentences and paragraphs, not table cells.
AGGREGATE_CHECKS = frozenset(
    {"information_density", "average_sentence_length", "reading_grade_level", "paragraph_length", "uniform_cadence", "overused_words"}
)
# Sentence-level checks that look inside the sentence for the words to judge.
QUOTATION_AWARE_CHECKS = frozenset({"passive_voice"})


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
    source_span: tuple[int, int] | None = None  # parity and judge lanes: where the finding is in the source text
    judgment: Mapping[str, Any] | None = None  # judge lane: the bilingual judge's reading behind the finding


def run_rules_lane(document: SegmentedDocument, pack: PolicyPack) -> tuple[list[Hit], int, list[dict[str, str]]]:
    """Run every enabled rules detector; return the hits, the count of detectors run, and those that could not run."""
    hits: list[Hit] = []
    count = 0
    not_run: list[dict[str, str]] = []
    quotations: list[tuple[int, int]] | None = None
    for policy in pack.enabled_policies:
        for detector in policy.detectors:
            if detector.lane != "rules":
                continue
            exempt = (detector.quotations or policy.quotations or "exempt") == "exempt"
            if exempt and quotations is None:
                quotations = quotation_spans(document)
            try:
                matches = list(_run_detector(document, detector, exempt))
            except LanguageCannotRun as exc:
                not_run.append({"policyId": policy.id, "detectorId": detector.id, "reason": str(exc)})
                continue
            count += 1
            for start, end, message, replacement in matches:
                if exempt and any(a <= start and end <= b for a, b in quotations):
                    continue
                hits.append(Hit(policy, detector, start, end, detector.message or message or policy.title, replacement))
    return _dedupe(hits), count, not_run


def quotation_spans(document: SegmentedDocument) -> list[tuple[int, int]]:
    """Source spans of direct quotations: passages in the language's quotation marks, and block quotes."""
    spans = [(r.start, r.end) for r in document.protected if r.kind == "quote"]
    for paragraph in document.paragraphs:
        masked = mask_inline(paragraph.source)
        spans.extend((paragraph.start + m.start(), paragraph.start + m.end()) for m in document.language.quotation_pattern.finditer(masked))
    return spans


def _run_detector(document: SegmentedDocument, detector: Detector, exempt_quotations: bool = False) -> Iterable[Match]:
    paragraphs = [p for p in document.paragraphs if _applies(detector, p)]
    if isinstance(detector, PhraseDetector):
        language = document.language
        pattern = language.phrase_pattern(detector.phrases, detector.case_sensitive)
        exceptions = language.phrase_pattern(detector.exceptions, detector.case_sensitive) if detector.exceptions else None
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
        if detector.check not in document.language.builtins:
            raise LanguageCannotRun(f"the {document.language.tag} language pack does not provide the built-in check '{detector.check}'")
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


def _dedupe(hits: list[Hit]) -> list[Hit]:
    """One hit per policy and span; a hit that offers a replacement wins over one that does not."""
    unique: dict[tuple[str, int, int], Hit] = {}
    for hit in hits:
        key = (hit.policy.id, hit.start, hit.end)
        if key not in unique or (unique[key].replacement is None and hit.replacement is not None):
            unique[key] = hit
    return list(unique.values())
