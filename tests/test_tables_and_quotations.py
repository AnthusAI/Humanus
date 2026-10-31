from __future__ import annotations

import pytest

from humanus.check import check
from humanus.contracts import ContractValidationError
from humanus.segmentation import segment_document

PACK = {
    "schemaVersion": 1,
    "packId": "t",
    "version": "1",
    "policies": [
        {
            "id": "words",
            "version": 1,
            "title": "Words",
            "guidance": "No utilize.",
            "severity": "warn",
            "detectors": [{"id": "utilize", "lane": "rules", "kind": "phrase", "phrases": ["utilize"]}],
        }
    ],
}


def _cells(text: str, **kwargs) -> list[str]:
    return [s.source for s in segment_document(text, **kwargs).paragraphs if s.block == "tableCell"]


def test_escaped_pipes_do_not_split_a_cell():
    cells = _cells("| a | b |\n|---|---|\n| left \\| right | next cell |\n")
    assert cells == ["a", "b", "left \\| right", "next cell"]


def test_tables_without_outer_pipes_and_inside_lists():
    assert _cells("a | b\n--|--\nhello there | more words\n") == ["a", "b", "hello there", "more words"]
    assert _cells("- item\n\n  | k | v |\n  |---|---|\n  | one | two |\n") == ["k", "v", "one", "two"]


def test_numbers_symbols_and_code_only_cells_are_skipped():
    cells = _cells("| x | y |\n|---|---|\n| 12.5% | $3,000 |\n| `code()` | `` `x` `` |\n| mix `code` words | -- |\n")
    assert cells == ["x", "y", "mix `code` words"]


def test_tables_off_protects_the_table_again():
    document = segment_document("Before.\n\n| a | b |\n|---|---|\n| one | two |\n", tables=False)
    assert [r.kind for r in document.protected] == ["table"]
    assert [s.source for s in document.paragraphs] == ["Before."]


def test_cell_findings_use_utf16_offsets_into_the_original_text():
    text = "| 😀 | note |\n|---|---|\n| 😀 | We utilize it. |\n"
    result = check({"schemaVersion": 1, "content": {"format": "markdown", "text": text}, "pack": PACK}, decision_model=None)
    (finding,) = result["findings"]
    units = text.encode("utf-16-le")
    assert units[finding["span"]["start"] * 2 : finding["span"]["end"] * 2].decode("utf-16-le") == "utilize"


def test_table_option_must_be_boolean():
    with pytest.raises(ContractValidationError):
        check({"schemaVersion": 1, "content": {"format": "text", "text": "x"}, "pack": PACK, "options": {"tables": "no"}}, decision_model=None)


def test_quotations_value_is_validated():
    pack = {**PACK, "policies": [{**PACK["policies"][0], "quotations": "sometimes"}]}
    with pytest.raises(ContractValidationError):
        check({"schemaVersion": 1, "content": {"format": "text", "text": "x"}, "pack": pack}, decision_model=None)


def test_quotation_exemption_covers_blockquote_and_straight_or_curly_quotes():
    text = 'He said "we utilize it" and “they utilize it” too.\n\nThey utilize it.\n'
    result = check({"schemaVersion": 1, "content": {"format": "markdown", "text": text}, "pack": PACK}, decision_model=None)
    assert [f["excerpt"] for f in result["findings"]] == ["utilize"]
    assert result["findings"][0]["span"]["start"] == text.index("They") + 5
