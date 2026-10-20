"""Regression tests for the standard-rule-set starter packs.

The asd-ste100 fixtures are the gold drafts from the original STE100 work
(PR #45); each must-fail draft names the policies it has to trigger.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from humanus.check import check
from humanus.packs import builtin_pack
from humanus.policy_pack import load_policy_pack

STE = Path(__file__).parent / "fixtures" / "asd-ste100"


def _findings(pack: dict, text: str) -> list[dict]:
    return check({"schemaVersion": 1, "content": {"format": "markus", "text": text}, "pack": pack})["findings"]


def _policies(pack: dict, path: Path) -> set[str]:
    return {f["policyId"] for f in _findings(pack, path.read_text(encoding="utf-8"))}


@pytest.mark.parametrize("name", ["asd-ste100", "plain-language"])
def test_starter_pack_is_valid(name):
    load_policy_pack(builtin_pack(name))


@pytest.mark.parametrize(
    "draft, expected",
    [
        ("gold/must-fail/gold-vocabulary.md", {"ste-approved-words"}),
        ("gold/must-fail/gold-structure.md", {"ste-sentence-length", "ste-one-instruction"}),
        ("gold/must-fail/gold-voice.md", {"ste-active-voice", "ste-no-ing", "ste-articles"}),
        ("two-instructions-draft.md", {"ste-one-instruction"}),
        ("multi-meaning-draft.md", {"ste-one-meaning"}),
    ],
)
def test_ste_must_fail(draft, expected):
    assert _policies(builtin_pack("asd-ste100"), STE / draft) == expected


@pytest.mark.parametrize(
    "draft",
    [
        "gold/must-pass/gold-clean-procedure.md",
        "gold/must-pass/gold-clean-description.md",
        "technical-ing-draft.md",
        "clean-technical-draft.md",
        "article-clean-draft.md",
        "at-limit-procedure-draft.md",
        "at-limit-description-draft.md",
    ],
)
def test_ste_must_pass(draft):
    assert _findings(builtin_pack("asd-ste100"), (STE / draft).read_text(encoding="utf-8")) == []


def test_ste_unapproved_words_offer_the_approved_word():
    findings = _findings(builtin_pack("asd-ste100"), (STE / "gold/must-fail/gold-vocabulary.md").read_text(encoding="utf-8"))
    assert [(f["excerpt"], f.get("replacement")) for f in findings] == [("Utilize", "use"), ("Purchase", "buy")]


def test_ste_whole_document_procedure_flags_non_imperative_prose():
    pack = builtin_pack("asd-ste100")
    imperative = next(p for p in pack["policies"] if p["id"] == "ste-imperative")
    imperative["detectors"][0]["params"] = {"wholeDocument": True}
    assert _policies(pack, STE / "non-imperative-draft.md") == {"ste-imperative"}


PLAIN_SAMPLE = """The applicant shall utilize Form 12 in order to request assistance from the IRS prior to the deadline. It is not uncommon for the agency to conduct an analysis of each and every request, and/or make a decision in the near future.

You must send us your form by May 1. We will review it and tell you what we decide."""


def test_plain_language_rules_flag_the_guidelines_examples():
    findings = _findings(builtin_pack("plain-language"), PLAIN_SAMPLE)
    assert [(f["policyId"], f["excerpt"], f.get("replacement")) for f in findings] == [
        ("pl-must-not-shall", "shall", "must"),
        ("pl-simple-words", "utilize", "use"),
        ("pl-simple-words", "in order to", "to"),
        ("pl-simple-words", "assistance", "help"),
        ("pl-define-abbreviations", "IRS", None),
        ("pl-simple-words", "prior to", "before"),
        ("pl-no-double-negatives", "not uncommon", None),
        ("pl-hidden-verbs", "conduct an analysis", None),
        ("pl-omit-excess-words", "each and every", "each"),
        ("pl-no-slashes", "and/or", None),
        ("pl-hidden-verbs", "make a decision", "decide"),
        ("pl-simple-words", "in the near future", "soon"),
    ]


def test_plain_language_clean_paragraph_has_no_findings():
    assert _findings(builtin_pack("plain-language"), PLAIN_SAMPLE.split("\n\n")[1]) == []


def test_plain_language_asks_the_decision_model_about_audience_and_order():
    pack = builtin_pack("plain-language")
    scopes = {
        p["id"]: d["scope"] for p in pack["policies"] for d in p["detectors"] if d["lane"] == "classifier"
    }
    assert scopes == {"pl-address-the-reader": "paragraph", "pl-main-point-first": "document", "pl-avoid-jargon": "paragraph"}
