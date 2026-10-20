from __future__ import annotations

import random
import sys
from pathlib import Path

from behave import given, then, when

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from limatus.calibration import apply_calibration, calibrate, expected_calibration_error  # noqa: E402
from limatus.check import check  # noqa: E402
from limatus.classifier_lane import DecisionAnswers, InMemoryClassifierCache  # noqa: E402
from limatus.policy_pack import load_policy_pack  # noqa: E402


def _labels(count: int) -> list[dict]:
    """A model that is overconfident: true probability is p pulled 70% toward 0.5."""
    rng = random.Random(7)
    labels = []
    for _ in range(count):
        p = rng.random()
        truth = 0.5 + (p - 0.5) * 0.3
        labels.append({"policyId": "claims", "detectorId": "vague", "probability": round(p, 2), "violates": rng.random() < truth})
    return labels


@given("{count:d} editor decisions on an overconfident detector")
def step_decisions(context, count):
    context.labels = _labels(count)


@when("I calibrate the detector on the first {count:d} decisions")
def step_calibrate_first(context, count):
    context.train, context.test = context.labels[:count], context.labels[count:]
    context.calibration_result = calibrate({"schemaVersion": 1, "labels": context.train})
    context.calibration = context.calibration_result["detectors"][0].get("calibration")


@when("I calibrate the detector on all of them")
def step_calibrate_all(context):
    context.calibration_result = calibrate({"schemaVersion": 1, "labels": context.labels})
    context.calibration = context.calibration_result["detectors"][0].get("calibration")


@then('the calibration method is "{method}"')
def step_method(context, method):
    assert context.calibration["method"] == method, context.calibration


@then("the calibration is valid inside a policy pack")
def step_valid_in_pack(context):
    detector = {
        "id": "vague",
        "lane": "classifier",
        "scope": "sentence",
        "question": {"type": "noul", "instructions": "?"},
        "violation": {"answer": "yes"},
        "threshold": 0.8,
        "calibration": context.calibration,
    }
    load_policy_pack({"schemaVersion": 1, "packId": "p", "version": "1", "policies": [
        {"id": "claims", "version": 1, "title": "t", "guidance": "g", "severity": "warn", "detectors": [detector]}]})


@then("the expected calibration error on the last {count:d} decisions drops by at least half")
def step_ece(context, count):
    ys = [label["violates"] for label in context.test]
    raw = expected_calibration_error([label["probability"] for label in context.test], ys)
    calibrated = expected_calibration_error([apply_calibration(context.calibration, label["probability"]) for label in context.test], ys)
    assert calibrated <= raw / 2, (raw, calibrated)


@then('the calibration result is "{result}"')
def step_result(context, result):
    detector = context.calibration_result["detectors"][0]
    if result == "not enough labels":
        assert "calibration" not in detector and "not enough" in detector["note"], detector
    else:
        assert detector["calibration"]["method"] == result, detector


class OneAnswerModel:
    def __init__(self, probability: float) -> None:
        self.probability = probability
        self.requests: list[dict] = []

    async def ask(self, state, questions, model):
        self.requests.append({"state": state, "questions": questions})
        return DecisionAnswers(answers={name: {"type": "noul", "noul": self.probability} for name in questions}, input_tokens=10)


def _calibration_pack(context) -> dict:
    detector = {
        "id": "vague",
        "lane": "classifier",
        "scope": "sentence",
        "question": {"type": "noul", "instructions": "Is the target sentence vague?"},
        "violation": {"answer": "yes"},
        "threshold": 0.8,
        "reviewAt": 0.5,
    }
    if getattr(context, "detector_calibration", None):
        detector["calibration"] = context.detector_calibration
    return {"schemaVersion": 1, "packId": "p", "version": "1", "policies": [
        {"id": "claims", "version": 1, "title": "Claims", "guidance": "Be specific.", "severity": "warn", "detectors": [detector]}]}


@given("a sentence detector with threshold 0.8 and review from 0.5 whose model says {probability:g}")
def step_detector_model(context, probability):
    context.one_model = OneAnswerModel(probability)


@given("its calibration maps 0.95 down to 0.6")
def step_calibration_map(context):
    context.detector_calibration = {"method": "isotonic", "points": [[0.0, 0.0], [0.95, 0.6], [1.0, 0.65]], "labels": 200}


@when("the sentence is checked")
def step_sentence_checked(context):
    context.check_result = check(
        {"schemaVersion": 1, "content": {"format": "markus", "text": "It is very good."}, "pack": _calibration_pack(context)},
        decision_model=context.one_model,
        classifier_cache=InMemoryClassifierCache(),
    )


@then('the finding has status "{status}" with probability {probability:g} and raw probability {raw:g}')
def step_calibrated_finding(context, status, probability, raw):
    finding = next(f for f in context.check_result["findings"] if f["segmentId"].startswith("s-"))
    assert (finding["status"], finding["probability"], finding["rawProbability"]) == (status, probability, raw), finding


@given('past decisions for detector "{detector_id}" with texts:')
def step_past_decisions(context, detector_id):
    context.past_examples = [
        {"policyId": "claims", "detectorId": detector_id, "text": row["text"].strip(), "violates": row["violates"].strip() == "yes"}
        for row in context.table
    ]


@given("at most {count:d} examples per question")
def step_max_examples(context, count):
    context.max_examples = count


@when('the sentence "{sentence}" is checked with those examples')
def step_checked_with_examples(context, sentence):
    context.one_model = OneAnswerModel(0.1)
    context.check_result = check(
        {
            "schemaVersion": 1,
            "content": {"format": "text", "text": sentence},
            "pack": _calibration_pack(context),
            "options": {"classifier": {"examples": context.past_examples, "maxExamplesPerQuestion": context.max_examples}},
        },
        decision_model=context.one_model,
        classifier_cache=InMemoryClassifierCache(),
    )


def _sentence_question(context) -> dict:
    request = next(r for r in context.one_model.requests if "context" in r["state"])
    return next(iter(request["questions"].values()))


@then('the question for detector "{detector_id}" carried {count:d} examples')
def step_examples_count(context, detector_id, count):
    examples = _sentence_question(context)["instructions"]["examples"]
    assert sum(len(v) for v in examples.values()) == count, examples


@then('the examples were "{first}" and "{second}"')
def step_examples_were(context, first, second):
    examples = _sentence_question(context)["instructions"]["examples"]
    assert sorted(t for v in examples.values() for t in v) == sorted([first, second]), examples
