from __future__ import annotations

import sys
from pathlib import Path

from behave import given, then, when

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from humanus.check import check  # noqa: E402
from humanus.packs import builtin_pack  # noqa: E402


def _set_detector(context, detector_id: str, **values) -> None:
    for policy in context.rules_pack["policies"]:
        for detector in policy["detectors"]:
            if detector["id"] == detector_id:
                detector.update(values)


@given('detector "{detector_id}" checks quotations')
def step_detector_checks(context, detector_id):
    _set_detector(context, detector_id, quotations="check")


@given('detector "{detector_id}" exempts quotations')
def step_detector_exempts(context, detector_id):
    _set_detector(context, detector_id, quotations="exempt")


@given('policy "{policy_id}" checks quotations')
def step_policy_checks(context, policy_id):
    for policy in context.rules_pack["policies"]:
        if policy["id"] == policy_id:
            policy["quotations"] = "check"


@given("the average sentence length limit is {limit:d} words")
def step_average_limit(context, limit):
    _set_detector(context, "average", params={"maxWords": limit})


@given('the built-in policy pack "{name}" is loaded')
def step_builtin_loaded(context, name):
    context.builtin_payload = builtin_pack(name)


@when("the document is checked with table checking off")
def step_checked_tables_off(context):
    context.check_result = check(
        {
            "schemaVersion": 1,
            "content": {"format": "markus", "text": context.document_text},
            "pack": context.rules_pack,
            "options": {"tables": False},
        }
    )


@when("the document is checked with the built-in pack:")
def step_checked_builtin(context):
    context.document_text = context.text
    context.check_result = check(
        {"schemaVersion": 1, "content": {"format": "markus", "text": context.text}, "pack": context.builtin_payload}
    )


@then("the findings are, by policy and excerpt:")
def step_findings_policy_excerpt(context):
    actual = [(f["policyId"], f["excerpt"]) for f in context.check_result["findings"]]
    expected = [(row["policy"].strip(), row["excerpt"].strip()) for row in context.table]
    assert actual == expected, actual


@then('the findings include policies "{policies}"')
def step_findings_include(context, policies):
    wanted = {p.strip() for p in policies.split(",")}
    found = {f["policyId"] for f in context.check_result["findings"]}
    assert wanted <= found, (wanted, found)


@then("no finding excerpt contains table syntax")
def step_no_table_syntax(context):
    for finding in context.check_result["findings"]:
        assert "|" not in finding["excerpt"] and "---" not in finding["excerpt"], finding


@then("the check result has no protected regions")
def step_result_no_protected(context):
    assert context.check_result["protected"] == [], context.check_result["protected"]


@then('the check result has protected regions "{kinds}"')
def step_result_protected(context, kinds):
    actual = [r["kind"] for r in context.check_result["protected"]]
    assert actual == [k.strip() for k in kinds.split(",")], actual


@then('every finding sits in the "{label}" row')
def step_findings_in_row(context, label):
    text = context.document_text
    utf16 = text.encode("utf-16-le")
    for finding in context.check_result["findings"]:
        before = utf16[: finding["span"]["start"] * 2].decode("utf-16-le")
        line = text.split("\n")[before.count("\n")]
        assert line.lstrip("| ").startswith(label), (line, finding)
