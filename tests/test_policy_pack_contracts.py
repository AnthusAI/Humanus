from __future__ import annotations

import copy

import pytest

from limatus.check import CheckRequestValidationError, Utf16Offsets, check
from limatus.policy_pack import PolicyPackValidationError, load_policy_pack
from limatus.segmentation import segment_document, split_sentences

PACK = {
    "schemaVersion": 1,
    "packId": "p",
    "version": "1",
    "policies": [
        {
            "id": "tone",
            "version": 1,
            "title": "Tone",
            "guidance": "Be plain.",
            "severity": "info",
            "detectors": [
                {
                    "id": "tone-choice",
                    "lane": "classifier",
                    "scope": "paragraph",
                    "question": {"type": "choice", "instructions": "Tone?", "criteria": {"plain": None, "hype": None}},
                    "violation": {"labels": ["hype"]},
                    "threshold": 0.9,
                    "reviewAt": 0.6,
                }
            ],
        }
    ],
}


def _sources(text: str, kind: str = "paragraph", fmt: str = "markus") -> list[tuple[str | None, str]]:
    document = segment_document(text, fmt)
    return [(s.block, s.source) for s in document.segments if s.kind == kind]


def _sentences(text: str) -> list[str]:
    return [text[a:b] for a, b in split_sentences(text)]


def test_crlf_offsets_select_source() -> None:
    text = "First line\r\ncontinues. Second.\r\n\r\n- item one\r\n- item two\r\n"
    document = segment_document(text)
    assert [s.source for s in document.paragraphs] == ["First line\r\ncontinues. Second.", "item one", "item two"]
    for segment in document.segments:
        assert text[segment.start : segment.end] == segment.source


def test_setext_and_closed_atx_headings() -> None:
    text = "Title here\n==========\n\n## Section ##\n\nBody.\n"
    assert _sources(text) == [("heading", "Title here"), ("heading", "Section"), ("paragraph", "Body.")]


def test_nested_list_items_are_list_items() -> None:
    text = "1. Outer item.\n   - Inner item.\n2. Second outer.\n"
    assert _sources(text) == [("listItem", "Outer item."), ("listItem", "Inner item."), ("listItem", "Second outer.")]


def test_indented_code_and_html_are_protected() -> None:
    text = "Prose.\n\n    code block. not prose.\n\n<div>raw</div>\n"
    document = segment_document(text)
    assert [s.source for s in document.paragraphs] == ["Prose."]
    assert [r.kind for r in document.protected] == ["code", "html"]


def test_quotes_and_brackets_close_sentences() -> None:
    assert _sentences("He said “Stop.” Then he left. (It was late.) Fine.") == [
        "He said “Stop.”",
        "Then he left.",
        "(It was late.)",
        "Fine.",
    ]


def test_lowercase_continuation_and_initials_do_not_split() -> None:
    assert _sentences("Ask J. Smith about it. ok? no, wait. Done.") == ["Ask J. Smith about it. ok? no, wait.", "Done."]


def test_emphasis_wrapped_sentence_start() -> None:
    assert _sentences("One. **Two** is bold. _Three_ too.") == ["One.", "**Two** is bold.", "_Three_ too."]


def test_text_format_has_no_protected_regions() -> None:
    text = "# not a heading\n\nSecond block. Two sentences.\n"
    document = segment_document(text, "text")
    assert [s.source for s in document.paragraphs] == ["# not a heading", "Second block. Two sentences."]
    assert document.protected == ()


def test_unknown_format_is_rejected() -> None:
    with pytest.raises(ValueError):
        segment_document("x", "html")


def test_utf16_offsets_count_astral_characters_twice() -> None:
    to_utf16 = Utf16Offsets("a\U0001F680bé")
    assert [to_utf16(i) for i in range(5)] == [0, 1, 3, 4, 5]


def test_choice_violation_labels_must_be_criteria() -> None:
    pack = copy.deepcopy(PACK)
    pack["policies"][0]["detectors"][0]["violation"] = {"labels": ["shouting"]}
    with pytest.raises(PolicyPackValidationError) as error:
        load_policy_pack(pack)
    assert error.value.location == "policies/0/detectors/0/violation"


def test_review_band_must_sit_below_threshold() -> None:
    pack = copy.deepcopy(PACK)
    pack["policies"][0]["detectors"][0]["reviewAt"] = 0.95
    with pytest.raises(PolicyPackValidationError, match="reviewAt"):
        load_policy_pack(pack)


def test_choice_question_requires_criteria() -> None:
    pack = copy.deepcopy(PACK)
    del pack["policies"][0]["detectors"][0]["question"]["criteria"]
    with pytest.raises(PolicyPackValidationError):
        load_policy_pack(pack)


def test_check_reports_pack_errors_under_pack_location() -> None:
    pack = copy.deepcopy(PACK)
    pack["policies"].append(copy.deepcopy(pack["policies"][0]))
    request = {"schemaVersion": 1, "content": {"format": "markus", "text": "Hi."}, "pack": pack}
    with pytest.raises(CheckRequestValidationError) as error:
        check(request)
    assert error.value.location == "pack/policies/1/id"


def test_disabled_lane_is_reported_disabled() -> None:
    request = {
        "schemaVersion": 1,
        "content": {"format": "markus", "text": "Hi."},
        "pack": PACK,
        "options": {"lanes": {"classifier": False}},
    }
    lanes = check(request)["lanes"]
    assert lanes["classifier"] == {"status": "disabled"}
    assert lanes["rules"]["status"] == "ran"
