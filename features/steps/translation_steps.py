from __future__ import annotations

import sys
from pathlib import Path

from behave import given, then, when

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from humanus.check import CheckRequestValidationError, Utf16Offsets, check  # noqa: E402
from humanus.contracts import validate_payload  # noqa: E402
from humanus.packs import builtin_pack  # noqa: E402
from humanus.parity import _emphasis_count  # noqa: E402
from humanus.policy_pack import load_policy_pack  # noqa: E402

PACK = "translation-faithfulness"


def _reset(context) -> None:
    for name in ("tf_glossary", "tf_judge_reports", "tf_result", "tf_error"):
        setattr(context, name, None)
    context.tf_prompts = []


# --- the two texts ---------------------------------------------------------------------


@given('the source in "{language}":')
def step_source(context, language):
    _reset(context)
    context.tf_source = {"format": "markus", "language": language, "text": context.text}


@given('the translation in "{language}":')
def step_translation(context, language):
    context.tf_content = {"format": "markus", "language": language, "text": context.text}


@given('a draft in "{language}" with no source:')
def step_draft_without_source(context, language):
    _reset(context)
    context.tf_source = None
    context.tf_content = {"format": "markus", "language": language, "text": context.text}


@given('the "{language}" glossary renders "{term}" as "{translation}"')
def step_glossary(context, language, term, translation):
    context.tf_glossary = {"language": language, "entries": [{"term": term, "translations": [translation]}]}


@given("a translation request whose {side} has no language")
def step_missing_language(context, side):
    _reset(context)
    context.tf_source = {"format": "markus", "language": "en", "text": "The files may have leaked."}
    context.tf_content = {"format": "markus", "language": "zh-Hans", "text": "文件可能泄露了。"}
    del (context.tf_source if side == "source" else context.tf_content)["language"]


def _issues(table) -> list[dict]:
    return [{key: row[key] for key in ("category", "sourceQuote", "targetQuote", "explanation")} for row in table]


@given("a bilingual judge that reports in every pass:")
def step_judge_every_pass(context):
    issues = _issues(context.table)
    context.tf_judge_reports = lambda pass_number: issues


@given("a bilingual judge that reports only in its first pass:")
def step_judge_first_pass(context):
    issues = _issues(context.table)
    context.tf_judge_reports = lambda pass_number: issues if pass_number == 1 else []


# --- comparing -------------------------------------------------------------------------


def _compare(context, pack: dict) -> None:
    request = {"schemaVersion": 1, "content": context.tf_content, "pack": pack}
    if context.tf_source is not None:
        request["source"] = context.tf_source
    if context.tf_glossary is not None:
        request["glossary"] = context.tf_glossary
    def scripted_judge(prompt):
        context.tf_prompts.append(prompt)
        return {"issues": context.tf_judge_reports(prompt["pass"])}

    judge = scripted_judge if context.tf_judge_reports is not None else None

    context.tf_result = None
    context.tf_error = None
    try:
        context.tf_result = check(request, decision_model=None, bilingual_judge=judge)
    except CheckRequestValidationError as exc:
        context.tf_error = exc


@when("Humanus compares them")
def step_compare(context):
    _compare(context, builtin_pack(PACK))


@when('Humanus compares them with the "{name}" starter pack')
@when('Humanus checks the draft with the "{name}" starter pack')
def step_compare_with(context, name):
    _compare(context, builtin_pack(name))


@when("the bilingual judge reads both blocks in {passes:d} passes")
def step_judge_passes(context, passes):
    pack = builtin_pack(PACK)
    for policy in pack["policies"]:
        for detector in policy["detectors"]:
            if detector["lane"] == "judge":
                detector["passes"] = passes
    _compare(context, pack)


# --- findings --------------------------------------------------------------------------


def _findings(context, policy: str | None = None) -> list[dict]:
    assert context.tf_error is None, context.tf_error
    return [f for f in context.tf_result["findings"] if policy is None or f["policyId"] == policy]


def _one(context, severity: str, policy: str) -> dict:
    found = [f for f in _findings(context, policy) if f["severity"] == severity]
    assert found, f"no {severity} {policy} finding in {[(f['policyId'], f['severity'], f['message']) for f in _findings(context)]}"
    context.tf_finding = found[0]
    return found[0]


@then('no "{policy}" finding is reported')
def step_no_policy_finding(context, policy):
    found = _findings(context, policy)
    assert not found, [f["message"] for f in found]


@then("no faithfulness finding is reported")
def step_no_finding(context):
    found = _findings(context)
    assert not found, [(f["policyId"], f["message"]) for f in found]


@then('an error "{policy}" finding is reported')
def step_error_reported(context, policy):
    _one(context, "error", policy)


@then('an error "{policy}" finding names "{first}" and "{second}"')
def step_names_both(context, policy, first, second):
    finding = _one(context, "error", policy)
    assert f"“{first}”" in finding["message"] and f"“{second}”" in finding["message"], finding["message"]


@then('an {severity} "{policy}" finding quotes "{excerpt}" from the source')
@then('a {severity} "{policy}" finding quotes "{excerpt}" from the source')
def step_quotes_source(context, severity, policy, excerpt):
    found = [f for f in _findings(context, policy) if f["severity"] == severity and f["source"]["excerpt"] == excerpt]
    assert found, [(f["policyId"], f["severity"], f["source"]["excerpt"]) for f in _findings(context)]
    context.tf_finding = found[0]


@then('an error "{policy}" finding quotes "{source}" from the source and "{target}" from the translation')
def step_quotes_both(context, policy, source, target):
    found = [f for f in _findings(context, policy) if f["source"]["excerpt"] == source and f["excerpt"] == target and f["severity"] == "error"]
    assert found, [(f["policyId"], f["source"]["excerpt"], f["excerpt"]) for f in _findings(context)]
    context.tf_finding = found[0]


@then('a warn "{policy}" finding has the span "{excerpt}"')
def step_warn_span(context, policy, excerpt):
    found = [f for f in _findings(context, policy) if f["severity"] == "warn" and f["excerpt"] == excerpt]
    assert found, [(f["policyId"], f["excerpt"]) for f in _findings(context)]


@then('an error "{policy}" finding offers "{term}"')
def step_offers(context, policy, term):
    finding = _one(context, "error", policy)
    assert f"Use “{term}”" in finding["message"], finding["message"]


@then('an error "{policy}" finding offers the replacement "{replacement}"')
def step_offers_replacement(context, policy, replacement):
    finding = _one(context, "error", policy)
    assert finding.get("replacement") == replacement, finding


@then('it offers the replacement "{replacement}"')
def step_it_offers(context, replacement):
    assert context.tf_finding.get("replacement") == replacement, context.tf_finding


@then('its source span selects "{source}" and its span selects "{target}"')
def step_spans_select(context, source, target):
    _assert_spans(context, context.tf_finding, source, target)


@then('its span selects "{target}"')
def step_span_selects(context, target):
    _assert_spans(context, context.tf_finding, None, target)


def _assert_spans(context, finding: dict, source: str | None, target: str | None) -> None:
    def select(text: str, span: dict) -> str:
        offsets = Utf16Offsets(text)
        return text[offsets.to_index(span["start"]) : offsets.to_index(span["end"])]

    if source is not None:
        assert select(context.tf_source["text"], finding["source"]["span"]) == source, finding
    if target is not None:
        assert select(context.tf_content["text"], finding["span"]) == target, finding


@then('no finding is reported for the translated "{attribute}" attribute')
def step_no_attribute_finding(context, attribute):
    for finding in _findings(context):
        assert f"'{attribute}'" not in finding["message"], finding["message"]


@then("with every replacement applied the translation renders {count:d} emphasis span")
def step_renders(context, count):
    text = context.tf_content["text"]
    offsets = Utf16Offsets(text)
    edits = sorted(
        ((offsets.to_index(f["span"]["start"]), offsets.to_index(f["span"]["end"]), f["replacement"]) for f in _findings(context, "emphasis") if "replacement" in f),
        reverse=True,
    )
    for start, end, replacement in edits:
        text = text[:start] + replacement + text[end:]
    assert _emphasis_count(text.lstrip("- ")) == count, text


@then('its judgment names the category "{category}" with {agreeing:d} of {passes:d} passes agreeing')
def step_judgment(context, category, agreeing, passes):
    judgment = context.tf_finding["judgment"]
    assert (judgment["category"], judgment["agreeing"], judgment["passes"]) == (category, agreeing, passes), judgment


@then('the "{policy}" finding has status "{status}" with {agreeing:d} of {passes:d} passes agreeing')
def step_review(context, policy, status, agreeing, passes):
    (finding,) = _findings(context, policy)
    assert finding["status"] == status, finding
    assert (finding["judgment"]["agreeing"], finding["judgment"]["passes"]) == (agreeing, passes), finding


@then("the judge was asked {count:d} times, each time with both blocks and the response schema")
def step_judge_asked(context, count):
    assert len(context.tf_prompts) == count, len(context.tf_prompts)
    for number, prompt in enumerate(context.tf_prompts, start=1):
        assert prompt["pass"] == number
        assert context.tf_source["text"].strip() in prompt["user"] and context.tf_content["text"].strip() in prompt["user"]
        assert prompt["responseSchema"]["required"] == ["issues"]
        assert "certainty-changed" in prompt["system"]


@then("the judge lane reports {count:d} rejected answers")
def step_rejected(context, count):
    assert context.tf_result["lanes"]["judge"].get("rejected") == count, context.tf_result["lanes"]["judge"]


@then('the judge lane is "{status}" and its reason says "{text}"')
def step_judge_lane(context, status, text):
    lane = context.tf_result["lanes"]["judge"]
    assert lane["status"] == status and text in lane["reason"], lane


@then("the parity lane ran")
def step_parity_ran(context):
    lane = context.tf_result["lanes"]["parity"]
    assert lane["status"] == "ran" and lane["detectors"] > 0 and "notRun" not in lane, lane


@then('the parity lane names "{detector}" as not run because "{reason}"')
def step_parity_not_run(context, detector, reason):
    not_run = context.tf_result["lanes"]["parity"].get("notRun", [])
    assert any(item["detectorId"] == detector and reason in item["reason"] for item in not_run), not_run


# --- refusals and the result -----------------------------------------------------------


def _refused_at(context, location: str) -> None:
    assert context.tf_error is not None, "the check was not refused"
    assert context.tf_error.location == location, (context.tf_error.location, str(context.tf_error))
    assert context.tf_result is None


# The longer step first: behave takes the first pattern that matches.
@then('the check is refused at "{location}" and the message names "{name}"')
def step_refused_names(context, location, name):
    _refused_at(context, location)
    assert name in str(context.tf_error), str(context.tf_error)


@then('the check is refused at "{location}"')
def step_refused_at(context, location):
    _refused_at(context, location)


@then('the result names the source language pack "{tag}"')
def step_source_language(context, tag):
    assert context.tf_error is None, context.tf_error
    assert context.tf_result["source"]["language"]["tag"] == tag, context.tf_result["source"]
    validate_payload("check-result-v1", context.tf_result)


@then('every finding is a valid "finding-v1" with category "faithfulness" and spans that select its excerpts')
def step_every_finding(context):
    findings = _findings(context)
    assert findings
    for finding in findings:
        validate_payload("finding-v1", finding)
        assert finding["category"] == "faithfulness"
        _assert_spans(context, finding, finding["source"]["excerpt"], finding["excerpt"])


@then('the result has the lanes "rules" and "classifier" only')
def step_lanes_only(context):
    assert context.tf_error is None, context.tf_error
    assert sorted(context.tf_result["lanes"]) == ["classifier", "rules"], context.tf_result["lanes"]


@then('the result has no "source"')
def step_no_source(context):
    assert "source" not in context.tf_result


@when('the "{name}" starter pack is loaded')
def step_load_pack(context, name):
    context.tf_pack = load_policy_pack(builtin_pack(name))


@then('it is written for every language ("*")')
def step_any_language(context):
    assert context.tf_pack.language == "*"


@then("every policy carries an evidence grade")
def step_evidence(context):
    for policy in context.tf_pack.policies:
        assert policy.evidence and policy.evidence["grade"] in {"measured", "normative", "folk"}, policy.id
