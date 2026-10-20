from __future__ import annotations

import sys
from pathlib import Path

from behave import given, then, when

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from humanus.check import check  # noqa: E402
from humanus.contracts import validate_payload  # noqa: E402
from humanus.suggest import (  # noqa: E402
    SuggestRequestValidationError,
    SuggestUnavailableError,
    draft_questions,
    suggest,
)


class FakeGenerator:
    def __init__(self) -> None:
        self.reply: dict = {"options": []}
        self.calls: list[dict] = []

    def generate(self, **kwargs) -> dict:
        self.calls.append(kwargs)
        return self.reply


def _generator(context) -> FakeGenerator:
    if not hasattr(context, "generator"):
        context.generator = FakeGenerator()
    return context.generator


@given('a policy pack with a "{policy_id}" phrase rule for "{phrase}" and rewrite guidance "{rewrite}"')
def step_suggest_pack(context, policy_id, phrase, rewrite):
    context.suggest_pack = {
        "schemaVersion": 1,
        "packId": "suggest-example",
        "version": "1",
        "guidance": "Plain engineering voice.",
        "policies": [
            {
                "id": policy_id,
                "version": 1,
                "title": "No hype",
                "guidance": "Describe the change instead of calling it game-changing.",
                "severity": "warn",
                "rewriteGuidance": rewrite,
                "detectors": [{"id": "hype", "lane": "rules", "kind": "phrase", "phrases": [phrase]}],
            }
        ],
    }


@given("the draft:")
def step_draft(context):
    context.draft = context.text


@given("the rewrite model will propose:")
def step_model_proposes(context):
    _generator(context).reply = {
        "options": [
            {
                "replacement": row["replacement"].strip(),
                "rationale": row["rationale"].strip(),
                "factVerificationRequired": False,
                "unresolvedQuestions": [],
            }
            for row in context.table
        ]
    }


@given("no rewrite model is configured")
def step_no_generator(context):
    context.generator = None


def _suggest(context, **target) -> None:
    request = {"schemaVersion": 1, "content": {"format": "markus", "text": context.draft}, "pack": context.suggest_pack, **target}
    context.suggest_error = None
    try:
        context.suggest_result = suggest(request, generator=_generator(context) if getattr(context, "generator", 1) is not None else None)
    except (SuggestRequestValidationError, SuggestUnavailableError) as error:
        context.suggest_error = error


def _utf16_span(text: str, needle: str) -> dict:
    start = text.index(needle)
    to16 = lambda index: len(text[:index].encode("utf-16-le")) // 2  # noqa: E731
    return {"start": to16(start), "end": to16(start + len(needle))}


@when('I ask for rewrites of the "{policy_id}" finding')
def step_suggest_finding(context, policy_id):
    result = check({"schemaVersion": 1, "content": {"format": "markus", "text": context.draft}, "pack": context.suggest_pack}, decision_model=None)
    context.finding = next(f for f in result["findings"] if f["policyId"] == policy_id)
    _suggest(context, finding=context.finding)


@when('I select "{text}" and ask for rewrites with the note "{note}"')
def step_suggest_selection_note(context, text, note):
    context.selection = _utf16_span(context.draft, text)
    context.selected_text = text
    _suggest(context, selection=context.selection, options={"instructions": note})


@when('I select "{text}" and ask for rewrites')
def step_suggest_selection(context, text):
    context.selection = _utf16_span(context.draft, text)
    _suggest(context, selection=context.selection)


@then('the suggest result is a valid "{schema_name}" document')
def step_suggest_valid(context, schema_name):
    assert context.suggest_error is None, context.suggest_error
    validate_payload(schema_name, context.suggest_result)


@then("there are {count:d} rewrite options")
def step_option_count(context, count):
    assert context.suggest_error is None, context.suggest_error
    assert len(context.suggest_result["options"]) == count, context.suggest_result


@then("every option replaces the whole sentence that contains the finding")
def step_option_spans(context):
    sentence = _utf16_span(context.draft, "This release is game-changing for teams.")
    assert context.suggest_result["target"]["span"] == sentence, context.suggest_result["target"]
    for option in context.suggest_result["options"]:
        assert option["span"] == sentence, option


@then("the rewrite prompt marked the flagged words inside the target")
def step_prompt_flag(context):
    assert "[[FLAG]]game-changing[[/FLAG]]" in context.generator.calls[-1]["user_prompt"]


def _prompt(context) -> str:
    call = context.generator.calls[-1]
    return call["system_prompt"] + "\n" + call["user_prompt"]


@then("the rewrite prompt included the policy guidance and its rewrite guidance")
def step_prompt_policy(context):
    prompt = _prompt(context)
    assert "Describe the change instead of calling it game-changing." in prompt
    assert "Say what changed and by how much." in prompt


@then("the rewrite prompt included the surrounding paragraph")
def step_prompt_paragraph(context):
    assert "Builds finish in 4 minutes instead of 9." in context.generator.calls[-1]["user_prompt"]


@then("the rewrite prompt told the model not to add facts")
def step_prompt_facts(context):
    assert "Do not add facts" in context.generator.calls[-1]["system_prompt"]


@then("the suggest target is the selected text")
def step_target_selected(context):
    target = context.suggest_result["target"]
    assert target["excerpt"] == context.selected_text and target["span"] == context.selection, target
    assert "findingId" not in target


@then('the rewrite prompt included the editor note "{note}"')
def step_prompt_note(context, note):
    assert f"Editor's note: {note}" in context.generator.calls[-1]["user_prompt"]


@then("{count:d} options were dropped with reasons")
def step_dropped(context, count):
    dropped = context.suggest_result.get("dropped", [])
    assert len(dropped) == count and all(d["reason"] for d in dropped), dropped


@then('suggesting fails with a request error mentioning "{text}"')
def step_request_error(context, text):
    assert isinstance(context.suggest_error, SuggestRequestValidationError), context.suggest_error
    assert text in str(context.suggest_error), str(context.suggest_error)


@then('suggesting fails with an unavailable error mentioning "{text}"')
def step_unavailable_error(context, text):
    assert isinstance(context.suggest_error, SuggestUnavailableError), context.suggest_error
    assert text in str(context.suggest_error)


@given("the rewrite model will draft these detectors:")
def step_model_drafts(context):
    _generator(context).reply = {
        "detectors": [
            {
                "id": row["id"].strip(),
                "scope": row["scope"].strip(),
                "questionType": "noul",
                "instructions": row["instructions"].strip(),
                "violationAnswer": "yes",
                "why": f"Proposed {row['id'].strip()}.",
            }
            for row in context.table
        ]
    }


@when('I ask for classifier questions for the guideline "{guideline}"')
def step_draft_questions(context, guideline):
    context.draft_result = draft_questions(
        {"schemaVersion": 1, "policy": {"title": "No hype", "guidance": guideline}},
        generator=context.generator,
    )


@then('the draft questions result is a valid "{schema_name}" document')
def step_draft_valid(context, schema_name):
    validate_payload(schema_name, context.draft_result)


@then("{count:d} detector was drafted with default threshold {threshold:g} and review band from {review:g}")
def step_drafted(context, count, threshold, review):
    detectors = context.draft_result["detectors"]
    assert len(detectors) == count, detectors
    assert all(d["threshold"] == threshold and d["reviewAt"] == review for d in detectors)


@then('the notes explain that "{detector_id}" was rejected')
def step_rejected_note(context, detector_id):
    assert any(detector_id in note and "rejected" in note for note in context.draft_result["notes"]), context.draft_result["notes"]
