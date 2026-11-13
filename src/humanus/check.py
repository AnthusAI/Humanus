"""``check``: one document plus a policy pack in, an annotated document out.

The result is standoff annotation (``check-result-v1``): segments, protected
regions and findings, each with offsets into the submitted text counted in
UTF-16 code units so a browser editor can use them directly.
"""
from __future__ import annotations

import hashlib
from bisect import bisect_left, bisect_right
from itertools import accumulate
from typing import Any, Mapping

from .bilingual_judge import BilingualJudge, run_judge_lane
from .contracts import ContractValidationError, validate_payload
from .classifier_lane import ClassifierCache, DecisionModel, default_decision_model, process_cache, run_classifier_lane
from .finding_ids import finding_id
from .languages import Language, UnsupportedLanguageError, resolve_language
from .parity import Bitext, GlossaryEntry, run_parity_lane
from .policy_pack import ANY_LANGUAGE, BILINGUAL_LANES, PolicyPack, PolicyPackValidationError, load_policy_pack
from .rules_lane import Hit, run_rules_lane
from .segmentation import ProtectedRegion, Segment, SegmentedDocument, normalize_text, plain_text, segment_document

REQUEST_SCHEMA = "check-request-v1"


class CheckRequestValidationError(ContractValidationError):
    """The request is not a valid ``check-request-v1`` document."""


_DEFAULT = object()


def check(
    request: Mapping[str, Any],
    *,
    decision_model: DecisionModel | None | object = _DEFAULT,
    classifier_cache: ClassifierCache | None = None,
    bilingual_judge: BilingualJudge | None = None,
) -> dict[str, Any]:
    """Check ``request["content"]`` against ``request["pack"]``.

    ``decision_model`` defaults to Jev when ``TYPESAFE_API_KEY`` is set; pass
    ``None`` to run without one. ``classifier_cache`` defaults to a cache shared
    by every check in this process.

    With ``request["source"]`` the content is also checked as a translation of
    that source: the pack's parity detectors compare the two texts, and its
    judge detectors ask ``bilingual_judge`` (supplied by the caller; Humanus
    has no default judge) about each block.
    """
    validate_payload(REQUEST_SCHEMA, request, CheckRequestValidationError)
    try:
        pack = load_policy_pack(request["pack"], schema_checked=True)
    except PolicyPackValidationError as exc:
        location = "/".join(part for part in ("pack", exc.location) if part)
        raise CheckRequestValidationError(REQUEST_SCHEMA, str(exc), location) from exc

    content = request["content"]
    language = reading_language(content["language"], pack, REQUEST_SCHEMA, CheckRequestValidationError)
    tables = request.get("options", {}).get("tables", True)
    document = segment_document(content["text"], content["format"], language=language, tables=tables)
    lane_options = request.get("options", {}).get("lanes", {})
    bitext = _bitext(request, pack, document, tables, lane_options)
    lanes: dict[str, Any] = {}
    hits: list[Hit] = []

    if lane_options.get("rules", True):
        rule_hits, detectors, not_run = run_rules_lane(document, pack)
        hits.extend(rule_hits)
        lanes["rules"] = {"status": "ran", "detectors": detectors}
        if not_run:
            lanes["rules"]["notRun"] = not_run
    else:
        lanes["rules"] = {"status": "disabled"}

    coverage: list[dict[str, Any]] = []
    usage: dict[str, int] = {}
    if lane_options.get("classifier", True):
        outcome = run_classifier_lane(
            document,
            pack,
            decision_model=default_decision_model() if decision_model is _DEFAULT else decision_model,
            cache=classifier_cache if classifier_cache is not None else process_cache(),
            options=request.get("options", {}).get("classifier", {}),
        )
        hits.extend(outcome.hits)
        coverage = outcome.coverage
        lanes["classifier"] = outcome.status
        usage = {
            "classifierRequests": outcome.requests,
            "classifierInputTokens": outcome.input_tokens,
            "classifierCacheHits": outcome.cache_hits,
        }
    else:
        lanes["classifier"] = {"status": "disabled"}

    if bitext is not None:
        if lane_options.get("parity", True):
            parity_hits, detectors, not_run = run_parity_lane(bitext, pack)
            hits.extend(parity_hits)
            lanes["parity"] = {"status": "ran", "detectors": detectors}
            if not_run:
                lanes["parity"]["notRun"] = not_run
        else:
            lanes["parity"] = {"status": "disabled"}
        if lane_options.get("judge", True):
            judge_hits, lanes["judge"] = run_judge_lane(bitext, pack, bilingual_judge)
            hits.extend(judge_hits)
        else:
            lanes["judge"] = {"status": "disabled"}

    return _annotate(document, pack, hits, lanes, coverage, usage, bitext.source if bitext is not None else None)


def _bitext(request: Mapping[str, Any], pack: PolicyPack, document: SegmentedDocument, tables: bool, lane_options: Mapping[str, Any]) -> Bitext | None:
    """The source a translation is checked against, read in its own language; None for an ordinary check.

    A pack that compares translations needs a source, and a source needs a
    pack that compares it: either alone is refused, never silently ignored.
    """
    source = request.get("source")
    if source is None:
        if pack.compares_translations:
            raise CheckRequestValidationError(
                REQUEST_SCHEMA,
                f"policy pack '{pack.pack_id}' has parity or judge detectors, which compare a translation with its source, "
                "but the request has no source (text, format and language)",
                "source",
            )
        return None
    if lane_options.get("parity", True) or lane_options.get("judge", True):
        if not pack.compares_translations:
            raise CheckRequestValidationError(
                REQUEST_SCHEMA,
                f"the request has a source but policy pack '{pack.pack_id}' has no parity or judge detector to compare it with",
                "source",
            )
    if source["format"] != request["content"]["format"]:
        raise CheckRequestValidationError(
            REQUEST_SCHEMA, f"the source is '{source['format']}' but the content is '{request['content']['format']}'; a translation keeps its source's format", "source/format"
        )
    try:
        source_language = resolve_language(source["language"])
    except UnsupportedLanguageError as exc:
        raise CheckRequestValidationError(REQUEST_SCHEMA, str(exc), "source/language") from exc
    glossary = request.get("glossary")
    entries: tuple[GlossaryEntry, ...] = ()
    if glossary is not None:
        try:
            glossary_language = resolve_language(glossary["language"])
        except UnsupportedLanguageError as exc:
            raise CheckRequestValidationError(REQUEST_SCHEMA, str(exc), "glossary/language") from exc
        if glossary_language.tag not in {document.language.tag, document.language.base}:
            raise CheckRequestValidationError(
                REQUEST_SCHEMA,
                f"the glossary is for '{glossary['language']}' but the content is '{request['content']['language']}'",
                "glossary/language",
            )
        entries = tuple(
            GlossaryEntry(entry["term"], tuple(entry.get("translations", ())), entry.get("caseSensitive", False)) for entry in glossary["entries"]
        )
    source_document = segment_document(source["text"], source["format"], language=source_language, tables=tables)
    return Bitext(source_document, document, source["format"], entries)


def reading_language(
    tag: str, pack: PolicyPack, schema_name: str, error_class: type[ContractValidationError]
) -> Language:
    """The language pack to read content tagged ``tag`` with, checked against the policy pack's language.

    A language with no language pack is refused, and so is a policy pack
    written for another language: English policies never run on Chinese text.
    A pack for a base language (es) applies to its regional variants (es-419);
    a pack for one variant never applies to another.
    """
    try:
        language = resolve_language(tag)
    except UnsupportedLanguageError as exc:
        raise error_class(schema_name, str(exc), "content/language") from exc
    if pack.language != ANY_LANGUAGE and resolve_language(pack.language).tag not in {language.tag, language.base}:
        raise error_class(
            schema_name,
            f"policy pack '{pack.pack_id}' is written for '{pack.language}' but the content is '{tag}'; "
            f"use a pack for {language.tag} or a language-neutral pack (language \"*\")",
            "content/language",
        )
    return language


def _annotate(
    document: SegmentedDocument,
    pack: PolicyPack,
    hits: list[Hit],
    lanes: dict[str, Any],
    coverage: list[dict[str, Any]],
    usage: dict[str, int],
    source: SegmentedDocument | None = None,
) -> dict[str, Any]:
    to_utf16 = Utf16Offsets(document.text)
    source_utf16 = Utf16Offsets(source.text) if source is not None else None
    result = {
        "schemaVersion": 1,
        "offsetUnit": "utf16",
        "document": {
            "hash": "sha256:" + hashlib.sha256(document.text.encode("utf-8")).hexdigest(),
            "length": to_utf16(len(document.text)),
        },
        "pack": {"packId": pack.pack_id, "version": pack.version},
        "language": {"tag": document.language.tag, "version": document.language.version},
    }
    if source is not None:
        result["source"] = {
            "hash": "sha256:" + hashlib.sha256(source.text.encode("utf-8")).hexdigest(),
            "length": source_utf16(len(source.text)),
            "language": {"tag": source.language.tag, "version": source.language.version},
        }
    result.update(
        {
            "segments": [_segment_payload(segment, to_utf16) for segment in document.segments],
            "protected": [_region_payload(region, to_utf16) for region in document.protected],
            "findings": _finding_payloads(document, hits, to_utf16, source, source_utf16),
            "coverage": coverage,
            "lanes": lanes,
        }
    )
    if usage:
        result["usage"] = usage
    return result


def _segment_payload(segment: Segment, to_utf16: "Utf16Offsets") -> dict[str, Any]:
    payload: dict[str, Any] = {
        "id": segment.id,
        "kind": segment.kind,
        "start": to_utf16(segment.start),
        "end": to_utf16(segment.end),
        "textHash": segment.text_hash[:16],
    }
    if segment.kind != "document":
        payload["text"] = segment.text
    if segment.block is not None:
        payload["block"] = segment.block
    if segment.parent_id is not None:
        payload["parentId"] = segment.parent_id
    return payload


def _finding_payloads(
    document: SegmentedDocument,
    hits: list[Hit],
    to_utf16: "Utf16Offsets",
    source: SegmentedDocument | None = None,
    source_utf16: "Utf16Offsets | None" = None,
) -> list[dict[str, Any]]:
    locate = SegmentLocator(document)
    occurrences: dict[tuple[str, str, str, str], int] = {}
    findings: list[dict[str, Any]] = []
    for hit in sorted(hits, key=lambda h: (h.start, h.end, h.policy.id, h.detector.id)):
        segment = hit.segment or locate(hit.start, hit.end)
        whole_document = segment.kind == "document"
        bilingual = hit.detector.lane in BILINGUAL_LANES
        # A faithfulness finding may sit in a directive attribute (outside every segment); it still quotes its span.
        excerpt = document.text[hit.start : hit.end] if bilingual or not whole_document else ""
        source_excerpt = source.text[hit.source_span[0] : hit.source_span[1]] if bilingual else ""
        identity = f"{excerpt}\x1e{source_excerpt}" if bilingual else excerpt
        key = (hit.policy.id, hit.detector.id, segment.id, normalize_text(identity))
        occurrence = occurrences.get(key, 0)
        occurrences[key] = occurrence + 1
        finding: dict[str, Any] = {
            "id": finding_id(
                policy_id=hit.policy.id,
                detector_id=hit.detector.id,
                segment_text=None if whole_document else segment.source,
                excerpt=identity,
                occurrence=occurrence,
            ),
            "policyId": hit.policy.id,
            "policyVersion": hit.policy.version,
            "detectorId": hit.detector.id,
            "lane": hit.detector.lane,
            "severity": hit.policy.severity,
            "status": hit.status,
            "segmentId": segment.id,
            "span": {"start": to_utf16(hit.start), "end": to_utf16(hit.end)},
            "excerpt": excerpt,
            "excerptText": plain_text(excerpt) if excerpt else "",
            "message": hit.message,
        }
        if hit.probability is not None:
            finding["probability"] = hit.probability
        if hit.raw_probability is not None and hit.raw_probability != hit.probability:
            finding["rawProbability"] = hit.raw_probability
        if hit.replacement is not None:
            finding["replacement"] = hit.replacement
        if bilingual:
            finding["category"] = "faithfulness"
            finding["source"] = {
                "span": {"start": source_utf16(hit.source_span[0]), "end": source_utf16(hit.source_span[1])},
                "excerpt": source_excerpt,
            }
        if hit.judgment is not None:
            finding["judgment"] = dict(hit.judgment)
        findings.append(finding)
    return findings


class SegmentLocator:
    """Find the smallest segment (sentence, then paragraph, then document) containing a span."""

    def __init__(self, document: SegmentedDocument) -> None:
        self._document_segment = document.segments[0]
        self._levels = [
            (level, [segment.start for segment in level])
            for level in (document.sentences(), document.paragraphs)
        ]

    def __call__(self, start: int, end: int) -> Segment:
        for level, starts in self._levels:
            index = bisect_right(starts, start) - 1
            if index >= 0 and end <= level[index].end:
                return level[index]
        return self._document_segment


def _region_payload(region: ProtectedRegion, to_utf16: "Utf16Offsets") -> dict[str, Any]:
    return {"kind": region.kind, "start": to_utf16(region.start), "end": to_utf16(region.end)}


class Utf16Offsets:
    """Convert Python string indexes (code points) to UTF-16 code unit offsets."""

    def __init__(self, text: str) -> None:
        self._prefix = [0, *accumulate(2 if ord(char) > 0xFFFF else 1 for char in text)]

    def __call__(self, index: int) -> int:
        return self._prefix[index]

    def to_index(self, utf16_offset: int) -> int:
        """The Python string index at a UTF-16 offset (which must not split a surrogate pair)."""
        index = bisect_left(self._prefix, utf16_offset)
        if index >= len(self._prefix) or self._prefix[index] != utf16_offset:
            raise ValueError(f"UTF-16 offset {utf16_offset} is outside the text or splits a character")
        return index
