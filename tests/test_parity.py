"""Unit tests for reading numbers and names in the parity lane, and the bilingual result contract."""
from __future__ import annotations

from decimal import Decimal

import pytest

from humanus.check import CheckRequestValidationError, check
from humanus.contracts import validate_payload
from humanus.languages import resolve_language
from humanus.packs import builtin_pack
from humanus.parity import _names_in, _native_numeral, _numbers_in


@pytest.mark.parametrize(
    "run, value",
    [("两百", 200), ("十五", 15), ("一万二千", 12000), ("三亿五千万", 350000000), ("二〇二六", 2026), ("一万亿", 10**12)],
)
def test_chinese_numerals_read_as_values(run, value):
    numerals = resolve_language("zh-Hans").numbers["numerals"]
    assert _native_numeral(run, numerals) == Decimal(value)


@pytest.mark.parametrize(
    "language, text, value",
    [
        ("en", "1,250.5", Decimal("1250.5")),
        ("es", "1.250,5", Decimal("1250.5")),
        ("es", "1,250.5", Decimal("1250.5")),  # an English form carried into Spanish still reads
        ("es-419", "1,250.5", Decimal("1250.5")),
        ("zh-Hans", "5000 万", Decimal("50000000")),
        ("en", "1.5 billion", Decimal("1500000000")),
        ("es", "1.500 millones", Decimal("1500000000")),
        ("es", "2 mil millones", Decimal("2000000000")),
    ],
)
def test_digits_read_with_the_language_forms(language, text, value):
    hard, _ = _numbers_in(text, resolve_language(language))
    assert len(hard) == 1 and value in hard[0].keys


def test_words_and_months_are_soft_values():
    _, soft = _numbers_in("twenty-five agents in May, two hundred plays", resolve_language("en"))
    assert {Decimal(25), Decimal(5), Decimal(200)} <= {v for n in soft for v in n.keys if isinstance(v, Decimal)}


def test_names_by_shape_and_position():
    names = [n for n, *_ in _names_in("Hugging Face says METR and OpenAI tested GPT-6 in Paris on Monday.", "paragraph", resolve_language("en"))]
    assert names == ["Hugging Face", "METR", "OpenAI", "GPT", "Paris"]


def test_a_title_cased_heading_yields_only_shaped_names():
    names = [n for n, *_ in _names_in("How the OpenAI Test Escaped", "heading2", resolve_language("en"))]
    assert names == ["OpenAI"]


def _request(**overrides):
    request = {
        "schemaVersion": 1,
        "content": {"format": "markus", "language": "es-419", "text": "Calculan que unos 1,200 agentes participaron."},
        "source": {"format": "markus", "language": "en", "text": "They estimate that about 1,200 agents participated."},
        "pack": builtin_pack("translation-faithfulness"),
    }
    request.update(overrides)
    return request


def test_a_bilingual_result_follows_the_contract():
    result = check(_request(), decision_model=None)
    validate_payload("check-result-v1", result)
    assert result["source"]["language"] == {"tag": "en", "version": resolve_language("en").version}
    assert set(result["lanes"]) == {"rules", "classifier", "parity", "judge"}
    assert not [f for f in result["findings"] if f["severity"] == "error"]


def test_disabled_bilingual_lanes_are_reported_disabled():
    result = check(_request(options={"lanes": {"parity": False, "judge": False}}), decision_model=None)
    assert result["lanes"]["parity"] == {"status": "disabled"} and result["lanes"]["judge"] == {"status": "disabled"}


def test_source_and_content_must_share_a_format():
    request = _request()
    request["source"] = {**request["source"], "format": "text"}
    with pytest.raises(CheckRequestValidationError) as error:
        check(request, decision_model=None)
    assert error.value.location == "source/format"


def test_a_glossary_needs_a_source():
    request = _request(glossary={"language": "es-419", "entries": [{"term": "agent", "translations": ["agente"]}]})
    del request["source"]
    with pytest.raises(CheckRequestValidationError):
        check(request, decision_model=None)


def test_a_glossary_entry_is_translated_or_kept_never_both():
    entry = {"term": "agent", "translations": ["agente"], "doNotTranslate": True}
    with pytest.raises(CheckRequestValidationError):
        check(_request(glossary={"language": "es-419", "entries": [entry]}), decision_model=None)


def test_a_judge_answer_outside_its_schema_fails_the_lane():
    result = check(_request(), decision_model=None, bilingual_judge=lambda prompt: {"issues": [{"category": "style"}]})
    assert result["lanes"]["judge"]["status"] == "failed"
    assert "response schema" in result["lanes"]["judge"]["reason"]
