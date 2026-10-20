from __future__ import annotations

import re
import sys
from pathlib import Path

from behave import given, then, when

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from humanus.check import check  # noqa: E402
from humanus.packs import builtin_pack  # noqa: E402
from humanus.policy_pack import load_policy_pack  # noqa: E402


def _detector(row) -> dict:
    detector = {"id": row["detector"].strip(), "lane": "rules", "kind": row["kind"].strip()}
    for item in (part.strip() for part in row["config"].split(";")):
        if not item:
            continue
        key, _, value = item.partition("=")
        if key == "phrases":
            detector["phrases"] = [p.strip() for p in value.split(",")]
        elif key == "ignoreCase":
            detector["ignoreCase"] = True
        else:
            detector[key] = value
    return detector


@given("a policy pack with these rules policies:")
def step_rules_pack(context):
    context.rules_pack = {
        "schemaVersion": 1,
        "packId": "rules-example",
        "version": "1",
        "policies": [
            {
                "id": row["policy"].strip(),
                "version": 1,
                "title": row["policy"].strip(),
                "guidance": f"Guidance for {row['policy'].strip()}.",
                "severity": row["severity"].strip(),
                "detectors": [_detector(row)],
            }
            for row in context.table
        ],
    }


@given("the document to check is:")
def step_document_to_check(context):
    context.document_text = context.text


@given('policies "{first}" and "{second}" are disabled')
def step_disable_policies(context, first, second):
    for policy in context.rules_pack["policies"]:
        if policy["id"] in {first, second}:
            policy["enabled"] = False


@given('detector "{detector_id}" applies only to "{block}" blocks')
def step_detector_blocks(context, detector_id, block):
    for policy in context.rules_pack["policies"]:
        for detector in policy["detectors"]:
            if detector["id"] == detector_id:
                detector["blocks"] = [block]


def _run_check(context, text: str) -> dict:
    return check({"schemaVersion": 1, "content": {"format": "markus", "text": text}, "pack": context.rules_pack})


@when("the document is checked")
def step_document_checked(context):
    context.check_request = {"schemaVersion": 1, "content": {"format": "markus", "text": context.document_text}, "pack": context.rules_pack}
    context.check_error = None
    context.check_result = _run_check(context, context.document_text)


@when('the second paragraph is replaced with "{replacement}" and the document is checked again')
def step_check_again(context, replacement):
    context.first_result = context.check_result
    paragraphs = context.document_text.split("\n\n")
    paragraphs[1] = replacement
    context.check_result = _run_check(context, "\n\n".join(paragraphs))


def _findings(context, policy_id: str) -> list[dict]:
    return [f for f in context.check_result["findings"] if f["policyId"] == policy_id]


@then('there is {count:d} finding for policy "{policy_id}"')
def step_finding_count(context, count, policy_id):
    findings = _findings(context, policy_id)
    assert len(findings) == count, context.check_result["findings"]
    context.finding = findings[0]


@then('that finding\'s excerpt is "{excerpt}" with severity "{severity}" and replacement "{replacement}"')
def step_finding_excerpt_replacement(context, excerpt, severity, replacement):
    assert (context.finding["excerpt"], context.finding["severity"], context.finding.get("replacement")) == (
        excerpt,
        severity,
        replacement,
    ), context.finding


@then('that finding\'s excerpt is "{excerpt}" with severity "{severity}"')
def step_finding_excerpt(context, excerpt, severity):
    assert (context.finding["excerpt"], context.finding["severity"]) == (excerpt, severity), context.finding


@then("every finding's UTF-16 span selects its excerpt")
def step_spans_select_excerpt(context):
    utf16 = context.document_text.encode("utf-16-le")
    for finding in context.check_result["findings"]:
        span = finding["span"]
        assert utf16[span["start"] * 2 : span["end"] * 2].decode("utf-16-le") == finding["excerpt"], finding


@then("every finding sits in the sentence that contains it")
def step_finding_in_sentence(context):
    segments = {s["id"]: s for s in context.check_result["segments"]}
    for finding in context.check_result["findings"]:
        segment = segments[finding["segmentId"]]
        assert segment["kind"] == "sentence", segment
        assert segment["start"] <= finding["span"]["start"] and finding["span"]["end"] <= segment["end"]


@then("there are no findings")
def step_no_findings(context):
    assert context.check_result["findings"] == [], context.check_result["findings"]


@then('the findings for policy "{policy_id}" have replacements "{replacements}"')
def step_replacements(context, policy_id, replacements):
    actual = [f.get("replacement") for f in sorted(_findings(context, policy_id), key=lambda f: f["span"]["start"])]
    assert actual == [r.strip() for r in replacements.split(",")], actual


@then('the rules lane reports status "{status}" with {count:d} detectors')
def step_rules_lane_status(context, status, count):
    lane = context.check_result["lanes"]["rules"]
    assert (lane["status"], lane.get("detectors")) == (status, count), lane


@then('that finding is in a "{block}" block')
def step_finding_block(context, block):
    segments = {s["id"]: s for s in context.check_result["segments"]}
    assert segments[context.finding["segmentId"]]["block"] == block


@then('the "{policy_id}" finding has the same id in both results')
def step_same_id(context, policy_id):
    before = [f["id"] for f in context.first_result["findings"] if f["policyId"] == policy_id]
    after = [f["id"] for f in _findings(context, policy_id)]
    assert before and before == after, (before, after)


@when('I load the built-in policy pack "{name}"')
def step_load_builtin(context, name):
    context.builtin_payload = builtin_pack(name)


@then("it is a valid policy pack")
def step_builtin_valid(context):
    context.builtin_loaded = load_policy_pack(context.builtin_payload)


def _check_with_builtin(context, text: str) -> dict:
    return check({"schemaVersion": 1, "content": {"format": "text", "text": text}, "pack": context.builtin_payload})


@then("every policy's violating examples produce a finding for that policy")
def step_violating_examples(context):
    misses = []
    for policy in context.builtin_payload["policies"]:
        for example in policy.get("examples", {}).get("violates", []):
            found = {f["policyId"] for f in _check_with_builtin(context, example)["findings"]}
            if policy["id"] not in found:
                misses.append((policy["id"], example))
    assert not misses, misses


@then("no policy's complying examples produce any finding")
def step_complying_examples(context):
    hits = []
    for policy in context.builtin_payload["policies"]:
        for example in policy.get("examples", {}).get("complies", []):
            findings = _check_with_builtin(context, example)["findings"]
            if findings:
                hits.append((policy["id"], example, [(f["policyId"], f["excerpt"]) for f in findings]))
    assert not hits, hits


@then('the command output lists "{name}"')
def step_output_lists(context, name):
    assert re.search(rf"^{re.escape(name)}\b", context.cli.stdout, re.M), context.cli.stdout
