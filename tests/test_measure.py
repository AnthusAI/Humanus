from __future__ import annotations

import pytest

from humanus import UnsupportedLanguageError, diff, list_languages, measure, resolve_language


def test_measure_accepts_a_language_pack_or_a_tag():
    assert measure("Two words.", "en") == measure("Two words.", resolve_language("en"))


def test_every_shipped_language_has_a_reading_rate():
    for tag in list_languages():
        assert resolve_language(tag).reading_units_per_minute > 0


def test_regional_spanish_inherits_the_reading_rate():
    assert resolve_language("es-419").reading_units_per_minute == resolve_language("es").reading_units_per_minute


def test_chinese_aliases_measure_in_characters():
    assert measure("猫睡觉。", "zh-CN")["size"] == {"unit": "character", "units": 3, "readingMinutes": 0.01, "readingUnitsPerMinute": 255.0}


def test_concepts_are_refused_until_that_slice_exists():
    with pytest.raises(NotImplementedError):
        measure("Text.", "en", concepts=["cats"])


def test_unsupported_language_is_refused():
    with pytest.raises(UnsupportedLanguageError):
        measure("Bonjour.", "fr")
    with pytest.raises(UnsupportedLanguageError):
        diff("a", "b", "fr")


def test_table_cells_count_toward_size_but_not_paragraphs():
    text = "Intro words here.\n\n| A | B |\n|---|---|\n| cell one | cell two |\n"
    result = measure(text, "en")
    assert result["structure"]["paragraphs"] == 1
    assert result["size"]["units"] > 3


def test_empty_text_has_no_rates():
    result = measure("", "en")
    assert result["size"]["units"] == 0 and result["sourcing"]["per500"] is None
    assert result["sourcing"]["shareParagraphsWithoutSource"] is None


def test_blurb_given_but_empty_is_present_false():
    assert measure("Body.", "en", blurb="")["structure"]["blurb"] == {"present": False, "length": 0}


def test_diff_accounting_is_consistent():
    old = "one two three four five six seven eight nine ten"
    new = "one two THREE four five six seven eight nine ten eleven twelve"
    result = diff(old, new, "en")
    assert result["oldUnits"] == result["unchanged"] + result["rewritten"] + result["removed"]
    assert result["newUnits"] == result["unchanged"] + result["rewritten"] + result["added"]
    assert 0 < result["shareChanged"] < 1


def test_diff_is_deterministic_and_symmetric_in_size():
    a, b = "alpha beta gamma delta", "alpha gamma delta epsilon zeta"
    assert diff(a, b, "en") == diff(a, b, "en")
    forward, backward = diff(a, b, "en"), diff(b, a, "en")
    assert forward["added"] == backward["removed"] and forward["removed"] == backward["added"]


def test_diff_ignores_front_matter_and_code():
    assert diff("---\nx: 1\n---\nSame text.\n\n```\nold\n```", "Same text.\n\n```\nnew\n```", "en")["shareChanged"] == 0.0
