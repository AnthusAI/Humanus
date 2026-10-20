"""Stable finding identity.

A finding id depends only on what the finding is about: the policy and
detector, the normalized text of the segment it sits in, the excerpt, and
which occurrence of that excerpt in the segment it is. Edits elsewhere in the
document do not change it, so a CMS can keep an editor's dismissal across
rescans. Editing the segment itself produces a new id, because the editor has
not yet seen that text.
"""
from __future__ import annotations

import hashlib

from .segmentation import normalize_text


def finding_id(
    *,
    policy_id: str,
    detector_id: str,
    segment_text: str | None,
    excerpt: str,
    occurrence: int = 0,
) -> str:
    """Return ``f-<16 hex>`` for a finding.

    ``segment_text`` is ``None`` for document-scope findings, which have one
    identity per detector regardless of the document's content.
    """
    parts = [
        policy_id,
        detector_id,
        "" if segment_text is None else normalize_text(segment_text),
        normalize_text(excerpt),
        str(occurrence),
    ]
    digest = hashlib.sha256("\x1f".join(parts).encode("utf-8")).hexdigest()
    return f"f-{digest[:16]}"
