from __future__ import annotations

import json
import sys
from pathlib import Path

from behave import given, then, when

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from humanus.check import check  # noqa: E402
from humanus.classifier_lane import DecisionAnswers, InMemoryClassifierCache, violation_probability  # noqa: E402
from humanus.policy_pack import load_policy_pack  # noqa: E402


class FakeDecisionModel:
    """Answers every noul question by trigger words found in the target text."""

    def __init__(self, triggers: list[tuple[str, float]], default: float, tokens: int = 100) -> None:
        self.triggers = triggers
        self.default = default
        self.tokens = tokens
        self.requests: list[dict] = []

    delay = 0.0

    async def ask(self, state, questions, model):
        self.requests.append({"state": state, "questions": questions, "model": model})
        if self.delay:
            import asyncio

            await asyncio.sleep(self.delay)
        target = state["target"].lower()
        p = next((value for word, value in self.triggers if word in target), self.default)
        return DecisionAnswers(answers={name: {"type": "noul", "noul": p} for name in questions}, input_tokens=self.tokens)


class FailingDecisionModel:
    async def ask(self, state, questions, model):
        raise RuntimeError("decision model is down")


@given('a fake decision model that answers "yes" with probability {high:g} for "{word_high}", {mid:g} for "{word_mid}" and {low:g} otherwise')
def step_fake_model(context, high, word_high, mid, word_mid, low):
    context.decision_model = FakeDecisionModel([(word_high, high), (word_mid, mid)], low)
    context.classifier_cache = InMemoryClassifierCache()
    context.classifier_options = {}


@given("a policy pack with these classifier policies:")
def step_classifier_pack(context):
    policies = []
    for row in context.table:
        detector = {
            "id": "judge",
            "lane": "classifier",
            "scope": row["scope"].strip(),
            "question": {"type": "noul", "instructions": row["question"].strip()},
            "violation": {"answer": "yes"},
            "threshold": float(row["threshold"]),
        }
        if row["reviewAt"].strip():
            detector["reviewAt"] = float(row["reviewAt"])
        policies.append(
            {
                "id": row["policy"].strip(),
                "version": 1,
                "title": row["policy"].strip(),
                "guidance": row["question"].strip(),
                "severity": row["severity"].strip(),
                "detectors": [detector],
            }
        )
    context.classifier_pack = {"schemaVersion": 1, "packId": "classifier-example", "version": "1", "policies": policies}


@given("the document to classify is:")
def step_document_to_classify(context):
    context.classify_text = context.text


@given("no decision model is configured")
def step_no_model(context):
    context.decision_model = None


@given('the pack also has a phrase rule for "{phrase}"')
def step_add_phrase_rule(context, phrase):
    context.classifier_pack["policies"].append(
        {
            "id": "phrase-rule",
            "version": 1,
            "title": "Phrase rule",
            "guidance": "No.",
            "severity": "warn",
            "detectors": [{"id": "phrase", "lane": "rules", "kind": "phrase", "phrases": [phrase]}],
        }
    )


@given("a decision model that fails every request")
def step_failing_model(context):
    context.decision_model = FailingDecisionModel()


@given("the classifier budget is {budget:d} input tokens with each request costing {cost:d}")
def step_budget(context, budget, cost):
    context.decision_model.tokens = cost
    context.classifier_options = {"maxInputTokens": budget}


def _classify(context, text: str) -> dict:
    request = {
        "schemaVersion": 1,
        "content": {"format": "markus", "text": text},
        "pack": context.classifier_pack,
        "options": {"classifier": context.classifier_options} if context.classifier_options else {},
    }
    context.check_request = request
    return check(request, decision_model=context.decision_model, classifier_cache=context.classifier_cache)


@when("the document is classified")
def step_classify(context):
    context.check_error = None
    context.check_result = _classify(context, context.classify_text)


@when('the second paragraph becomes "{replacement}" and the document is classified again with the same cache')
def step_classify_again(context, replacement):
    context.requests_before = len(context.decision_model.requests)
    paragraphs = context.classify_text.split("\n\n")
    paragraphs[1] = replacement
    context.check_result = _classify(context, "\n\n".join(paragraphs))


@then('the classifier lane reports status "{status}" with {count:d} detectors')
def step_classifier_status_count(context, status, count):
    lane = context.check_result["lanes"]["classifier"]
    assert (lane["status"], lane.get("detectors")) == (status, count), lane


@then('the classifier lane reports status "{status}"')
def step_classifier_status(context, status):
    lane = context.check_result["lanes"]["classifier"]
    assert lane["status"] == status, lane


@then("the findings are:")
def step_findings_table(context):
    actual = [(f["policyId"], f["excerpt"], f["status"], f["severity"]) for f in context.check_result["findings"]]
    expected = [
        (row["policy"].strip(), row["excerpt"].strip(), row["status"].strip(), row["severity"].strip())
        for row in context.table
    ]
    assert actual == expected, actual


@then("every classifier finding carries its probability")
def step_findings_probability(context):
    for finding in context.check_result["findings"]:
        assert finding["lane"] == "classifier" and 0 <= finding["probability"] <= 1, finding


@then("coverage has a probability for every sentence and paragraph against each of its detectors")
def step_coverage(context):
    segments = context.check_result["segments"]
    sentences = [s["id"] for s in segments if s["kind"] == "sentence"]
    paragraphs = [s["id"] for s in segments if s["kind"] == "paragraph"]
    expected = {(s, p) for s in sentences for p in ("concrete-claims", "no-unearned-trust")} | {
        (p, "focused") for p in paragraphs
    }
    actual = {(c["segmentId"], c["policyId"]) for c in context.check_result["coverage"]}
    assert actual == expected, actual ^ expected


@then("the decision model received {count:d} requests")
def step_request_count(context, count):
    assert len(context.decision_model.requests) == count, len(context.decision_model.requests)


@then("each sentence request asked {sentence_q:d} questions and the paragraph request asked {paragraph_q:d}")
def step_question_counts(context, sentence_q, paragraph_q):
    counts = sorted(len(r["questions"]) for r in context.decision_model.requests)
    assert counts == sorted([sentence_q, sentence_q, paragraph_q]), counts


@then("each sentence request's state includes its paragraph as context")
def step_sentence_context(context):
    sentence_requests = [r for r in context.decision_model.requests if "context" in r["state"]]
    assert len(sentence_requests) == 2
    for request in sentence_requests:
        assert request["state"]["context"] == "First sentence. Second sentence."
        assert request["state"]["target"] in request["state"]["context"]


@then("the second check sent {count:d} requests to the decision model")
def step_second_requests(context, count):
    assert len(context.decision_model.requests) - context.requests_before == count


@then("the second check reports {count:d} cache hits")
def step_cache_hits(context, count):
    assert context.check_result["usage"]["classifierCacheHits"] == count, context.check_result["usage"]


def _detector(question_type: str, criteria, violation: dict):
    pack = {
        "schemaVersion": 1,
        "packId": "p",
        "version": "1",
        "policies": [
            {
                "id": "x",
                "version": 1,
                "title": "x",
                "guidance": "x",
                "severity": "info",
                "detectors": [
                    {
                        "id": "d",
                        "lane": "classifier",
                        "scope": "sentence",
                        "question": {"type": question_type, "instructions": "?", "criteria": criteria},
                        "violation": violation,
                        "threshold": 0.5,
                    }
                ],
            }
        ],
    }
    return load_policy_pack(pack).policies[0].detectors[0]


def _parse_probabilities(text: str) -> dict:
    return {key.strip(): float(value) for key, value in (item.split("=") for item in text.split(","))}


@given('the decision model answers a "choice" question with probabilities "{probabilities}"')
def step_choice_answer(context, probabilities):
    context.choice_answer = {"type": "choice", "probabilities": _parse_probabilities(probabilities)}


@given('the decision model answers a "score" question with probabilities "{probabilities}"')
def step_score_answer(context, probabilities):
    context.score_answer = {"type": "score", "probabilities": _parse_probabilities(probabilities)}


@when('a choice detector with violation labels "{labels}" is evaluated')
def step_choice_eval(context, labels):
    detector = _detector(
        "choice",
        {"neutral": None, "hype": None, "plain": None},
        {"labels": [label.strip() for label in labels.split(",")]},
    )
    context.choice_probability = violation_probability(detector, context.choice_answer)


@when('a score detector with violation "scoreBelow {level:d}" is evaluated')
def step_score_eval(context, level):
    detector = _detector("score", ["poor", "fair", "good"], {"scoreBelow": level})
    context.score_probability = violation_probability(detector, context.score_answer)


@then("the choice detector's probability of violation is {value:g}")
def step_choice_probability(context, value):
    assert abs(context.choice_probability - value) < 1e-9, context.choice_probability


@then("the score detector's probability of violation is {value:g}")
def step_score_probability(context, value):
    assert abs(context.score_probability - value) < 1e-9, context.score_probability


@then("the rules lane still reports its finding")
def step_rules_still(context):
    assert [f["policyId"] for f in context.check_result["findings"]] == ["phrase-rule"], json.dumps(
        context.check_result["findings"]
    )


@given("each decision takes {delay:g} seconds and the lane may run {concurrency:d} request at a time with a {deadline:g} second deadline")
def step_deadline(context, delay, concurrency, deadline):
    context.decision_model.delay = delay
    context.classifier_options = {"maxConcurrency": concurrency, "deadlineSeconds": deadline}


@then("the decision model received fewer than {count:d} requests")
def step_fewer_requests(context, count):
    assert len(context.decision_model.requests) < count, len(context.decision_model.requests)
