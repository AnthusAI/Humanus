"""``check``: one document plus a policy pack in, an annotated document out.

The result is standoff annotation (``check-result-v1``): segments, protected
regions and findings, each with offsets into the submitted text counted in
UTF-16 code units so a browser editor can use them directly.
"""
from __future__ import annotations

import hashlib
from itertools import accumulate
from typing import Any, Mapping

from .contracts import ContractValidationError, validate_payload
from .policy_pack import PolicyPack, PolicyPackValidationError, load_policy_pack
from .segmentation import ProtectedRegion, Segment, SegmentedDocument, segment_document

REQUEST_SCHEMA = "check-request-v1"
RESULT_SCHEMA = "check-result-v1"
LANES = ("rules", "classifier")


class CheckRequestValidationError(ContractValidationError):
    """The request is not a valid ``check-request-v1`` document."""


def check(request: Mapping[str, Any]) -> dict[str, Any]:
    """Check ``request["content"]`` against ``request["pack"]``."""
    validate_payload(REQUEST_SCHEMA, request, CheckRequestValidationError)
    try:
        pack = load_policy_pack(request["pack"])
    except PolicyPackValidationError as exc:
        location = "/".join(part for part in ("pack", exc.location) if part)
        raise CheckRequestValidationError(REQUEST_SCHEMA, str(exc), location) from exc

    content = request["content"]
    document = segment_document(content["text"], content["format"])
    lane_options = request.get("options", {}).get("lanes", {})
    result = _annotate(document, pack, lanes={lane: _lane_status(pack, lane, lane_options) for lane in LANES})
    validate_payload(RESULT_SCHEMA, result)
    return result


def _lane_status(pack: PolicyPack, lane: str, lane_options: Mapping[str, bool]) -> dict[str, Any]:
    if not lane_options.get(lane, True):
        return {"status": "disabled"}
    if not any(d.lane == lane for p in pack.enabled_policies for d in p.detectors):
        return {"status": "ran", "detectors": 0}
    return {"status": "unavailable", "reason": f"the {lane} lane is not implemented in this version", "detectors": 0}


def _annotate(document: SegmentedDocument, pack: PolicyPack, lanes: dict[str, Any]) -> dict[str, Any]:
    to_utf16 = Utf16Offsets(document.text)
    return {
        "schemaVersion": 1,
        "offsetUnit": "utf16",
        "document": {
            "hash": "sha256:" + hashlib.sha256(document.text.encode("utf-8")).hexdigest(),
            "length": to_utf16(len(document.text)),
        },
        "pack": {"packId": pack.pack_id, "version": pack.version},
        "segments": [_segment_payload(segment, to_utf16) for segment in document.segments],
        "protected": [_region_payload(region, to_utf16) for region in document.protected],
        "findings": [],
        "coverage": [],
        "lanes": lanes,
    }


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


def _region_payload(region: ProtectedRegion, to_utf16: "Utf16Offsets") -> dict[str, Any]:
    return {"kind": region.kind, "start": to_utf16(region.start), "end": to_utf16(region.end)}


class Utf16Offsets:
    """Convert Python string indexes (code points) to UTF-16 code unit offsets."""

    def __init__(self, text: str) -> None:
        self._prefix = [0, *accumulate(2 if ord(char) > 0xFFFF else 1 for char in text)]

    def __call__(self, index: int) -> int:
        return self._prefix[index]
