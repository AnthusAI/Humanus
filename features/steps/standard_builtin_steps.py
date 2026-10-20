from __future__ import annotations

import json
import sys
from pathlib import Path

from behave import given, then

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))


def _pack(detector: dict) -> dict:
    return {
        "schemaVersion": 1,
        "packId": "standard-checks",
        "version": "1",
        "policies": [{"id": "standard", "version": 1, "title": "Standard", "guidance": "g", "severity": "info", "detectors": [detector]}],
    }


@given('a built-in "{check}" check with params {params}')
def step_builtin(context, check, params):
    detector = {"id": check.replace("_", "-"), "lane": "rules", "kind": "builtin", "check": check}
    parsed = json.loads(params)
    if parsed:
        detector["params"] = parsed
    context.rules_pack = _pack(detector)


@given('a phrase detector for "{phrase}" with the exception "{exception}"')
def step_phrase_exception(context, phrase, exception):
    context.rules_pack = _pack(
        {"id": "phrase", "lane": "rules", "kind": "phrase", "phrases": [phrase], "exceptions": [exception]}
    )


def _sorted_findings(context) -> list[dict]:
    return sorted(context.check_result["findings"], key=lambda f: f["span"]["start"])


@then('the built-in findings are on "{excerpts}"')
def step_findings_on(context, excerpts):
    expected = [e.strip() for e in excerpts.split("|")]
    actual = [f["excerpt"] for f in _sorted_findings(context)]
    assert actual == expected, actual


@then("the first finding's message mentions \"{text}\"")
def step_message_mentions(context, text):
    message = _sorted_findings(context)[0]["message"]
    assert text in message, message


@then("there is {count:d} built-in finding covering the whole document")
def step_whole_document(context, count):
    findings = context.check_result["findings"]
    assert len(findings) == count, findings
    whole = {"start": 0, "end": len(context.document_text.encode("utf-16-le")) // 2}
    assert all(f["span"] == whole for f in findings), findings


@then('the only finding starts after "{prefix}"')
def step_finding_after(context, prefix):
    findings = _sorted_findings(context)
    assert len(findings) == 1, findings
    assert findings[0]["span"]["start"] >= context.document_text.index(prefix) + len(prefix), findings
