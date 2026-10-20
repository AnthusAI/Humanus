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

from .contracts import ContractValidationError, validate_payload
from .classifier_lane import ClassifierCache, DecisionModel, default_decision_model, process_cache, run_classifier_lane
from .finding_ids import finding_id
from .policy_pack import PolicyPack, PolicyPackValidationError, load_policy_pack
from .rules_lane import Hit, run_rules_lane
from .segmentation import ProtectedRegion, Segment, SegmentedDocument, normalize_text, segment_document

REQUEST_SCHEMA = "check-request-v1"


class CheckRequestValidationError(ContractValidationError):
    """The request is not a valid ``check-request-v1`` document."""


_DEFAULT = object()


def check(
    request: Mapping[str, Any],
    *,
    decision_model: DecisionModel | None | object = _DEFAULT,
    classifier_cache: ClassifierCache | None = None,
) -> dict[str, Any]:
    """Check ``request["content"]`` against ``request["pack"]``.

    ``decision_model`` defaults to Jev when ``TYPESAFE_API_KEY`` is set; pass
    ``None`` to run without one. ``classifier_cache`` defaults to a cache shared
    by every check in this process.
    """
    validate_payload(REQUEST_SCHEMA, request, CheckRequestValidationError)
    try:
        pack = load_policy_pack(request["pack"], schema_checked=True)
    except PolicyPackValidationError as exc:
        location = "/".join(part for part in ("pack", exc.location) if part)
        raise CheckRequestValidationError(REQUEST_SCHEMA, str(exc), location) from exc

    content = request["content"]
    document = segment_document(content["text"], content["format"])
    lane_options = request.get("options", {}).get("lanes", {})
    lanes: dict[str, Any] = {}
    hits: list[Hit] = []

    if lane_options.get("rules", True):
        rule_hits, detectors = run_rules_lane(document, pack)
        hits.extend(rule_hits)
        lanes["rules"] = {"status": "ran", "detectors": detectors}
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

    return _annotate(document, pack, hits, lanes, coverage, usage)


def _annotate(
    document: SegmentedDocument,
    pack: PolicyPack,
    hits: list[Hit],
    lanes: dict[str, Any],
    coverage: list[dict[str, Any]],
    usage: dict[str, int],
) -> dict[str, Any]:
    to_utf16 = Utf16Offsets(document.text)
    result = {
        "schemaVersion": 1,
        "offsetUnit": "utf16",
        "document": {
            "hash": "sha256:" + hashlib.sha256(document.text.encode("utf-8")).hexdigest(),
            "length": to_utf16(len(document.text)),
        },
        "pack": {"packId": pack.pack_id, "version": pack.version},
        "segments": [_segment_payload(segment, to_utf16) for segment in document.segments],
        "protected": [_region_payload(region, to_utf16) for region in document.protected],
        "findings": _finding_payloads(document, hits, to_utf16),
        "coverage": coverage,
        "lanes": lanes,
    }
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
    if segment.block is not None:
        payload["block"] = segment.block
    if segment.parent_id is not None:
        payload["parentId"] = segment.parent_id
    return payload


def _finding_payloads(document: SegmentedDocument, hits: list[Hit], to_utf16: "Utf16Offsets") -> list[dict[str, Any]]:
    locate = SegmentLocator(document)
    occurrences: dict[tuple[str, str, str, str], int] = {}
    findings: list[dict[str, Any]] = []
    for hit in sorted(hits, key=lambda h: (h.start, h.end, h.policy.id, h.detector.id)):
        segment = hit.segment or locate(hit.start, hit.end)
        whole_document = segment.kind == "document"
        excerpt = "" if whole_document else document.text[hit.start : hit.end]
        key = (hit.policy.id, hit.detector.id, segment.id, normalize_text(excerpt))
        occurrence = occurrences.get(key, 0)
        occurrences[key] = occurrence + 1
        finding: dict[str, Any] = {
            "id": finding_id(
                policy_id=hit.policy.id,
                detector_id=hit.detector.id,
                segment_text=None if whole_document else segment.source,
                excerpt=excerpt,
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
            "message": hit.message,
        }
        if hit.probability is not None:
            finding["probability"] = hit.probability
        if hit.replacement is not None:
            finding["replacement"] = hit.replacement
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
