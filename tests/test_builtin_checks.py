from __future__ import annotations

from pathlib import Path

import pytest

from humanus.check import check

FIXTURES = Path(__file__).parent / "fixtures" / "builtin-checks"


def _findings(text: str, check_name: str, params: dict | None = None) -> list[dict]:
    detector = {"id": "d", "lane": "rules", "kind": "builtin", "check": check_name}
    if params:
        detector["params"] = params
    pack = {
        "schemaVersion": 1,
        "packId": "p",
        "version": "1",
        "policies": [{"id": "house", "version": 1, "title": "House", "guidance": "g", "severity": "info", "detectors": [detector]}],
    }
    request = {"schemaVersion": 1, "content": {"format": "markus", "text": text}, "pack": pack}
    return check(request, decision_model=None)["findings"]


def test_repeated_body_prose_is_redundancy() -> None:
    findings = _findings((FIXTURES / "redundancy-body-prose.md").read_text(), "redundancy")
    assert len(findings) == 2
    assert all("editorial team reviewed the manuscript" in f["excerpt"] for f in findings)


@pytest.mark.parametrize(
    "fixture",
    [
        "redundancy-image-alts.md",  # image alt text is not prose
        "redundancy-blockquote-refrain.md",  # quotes are someone else's words
        "redundancy-italic-pull-quote.md",  # italic formula repeated by a pull-quote directive
        # A body sentence echoing a block quote is not redundancy: quoted material is
        # protected and never checked (the legacy diagnose flagged this case).
        "redundancy-blockquote-mixed.md",
    ],
)
def test_quoted_or_non_prose_repetition_is_not_redundancy(fixture: str) -> None:
    assert _findings((FIXTURES / fixture).read_text(), "redundancy") == []


def test_short_identical_refrain_is_not_redundancy() -> None:
    text = "We keep going. The work is long.\n\nWe keep going. The road is longer.\n\nWe keep going until the end."
    assert _findings(text, "redundancy") == []


def test_unsupported_certainty_and_attribution() -> None:
    assert [f["excerpt"] for f in _findings("This always works. It ships Tuesday.", "unsupported_certainty")] == ["This always works."]
    assert _findings("This always works according to Smith (2024).", "unsupported_certainty") == []
    assert [f["excerpt"] for f in _findings("Latency fell 40%. Nice.", "missing_attribution")] == ["Latency fell 40%."]


def test_information_density_flags_low_density_long_text() -> None:
    filler = " ".join(["it is the one that is in it and is it."] * 60)
    messages = [f["message"] for f in _findings(filler, "information_density", {"minWords": 100})]
    assert any("Lexical density" in m for m in messages)
    assert _findings("Short text.", "information_density") == []


def test_contrast_cap_marks_each_contrast_over_the_cap() -> None:
    text = "Fast, not slow. Cheap, not dear. Calm, not loud."
    assert len(_findings(text, "contrast_cap", {"max": 2})) == 3
    assert _findings(text, "contrast_cap", {"max": 3}) == []
