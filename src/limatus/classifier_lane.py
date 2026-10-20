"""The classifier lane: zero-shot decisions from a decision model (TypeSafe Jev).

Each segment costs one request carrying every question that applies to it, so
adding policies is nearly free: the segment's text is paid for once. Answers
are cached by model, question set and segment content, so a rescan after an
edit only asks about the text that changed.

A sentence is judged with its paragraph as context; a paragraph or the whole
document is judged on its own. A policy's examples travel with its question.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import os
import re
from collections import OrderedDict
from dataclasses import dataclass, field
from typing import Any, Mapping, Protocol

from .policy_pack import ClassifierDetector, Policy, PolicyPack
from .rules_lane import Hit
from .segmentation import Segment, SegmentedDocument

DEFAULT_MODEL = "jev-latest"
DEFAULT_MAX_CONCURRENCY = 16

SENTENCE_TASK = "Answer every question about `target` only. `context` is the paragraph around it, for reference."
SEGMENT_TASK = "Answer every question about `target`."


@dataclass(frozen=True)
class DecisionAnswers:
    """What one request returned: answers by question name, and its billable input tokens."""

    answers: Mapping[str, Mapping[str, Any]]
    input_tokens: int = 0


class DecisionModel(Protocol):
    async def ask(self, state: Mapping[str, Any], questions: Mapping[str, Any], model: str) -> DecisionAnswers: ...


class ClassifierCache(Protocol):
    def get(self, key: str) -> Mapping[str, Mapping[str, Any]] | None: ...

    def set(self, key: str, answers: Mapping[str, Mapping[str, Any]]) -> None: ...


class InMemoryClassifierCache:
    """A bounded LRU cache of answers, keyed by content fingerprints (no raw text)."""

    def __init__(self, max_entries: int = 50_000) -> None:
        self._entries: OrderedDict[str, Mapping[str, Mapping[str, Any]]] = OrderedDict()
        self._max_entries = max_entries

    def get(self, key: str) -> Mapping[str, Mapping[str, Any]] | None:
        answers = self._entries.get(key)
        if answers is not None:
            self._entries.move_to_end(key)
        return answers

    def set(self, key: str, answers: Mapping[str, Mapping[str, Any]]) -> None:
        self._entries[key] = answers
        self._entries.move_to_end(key)
        while len(self._entries) > self._max_entries:
            self._entries.popitem(last=False)


class TypeSafeDecisionModel:
    """Jev through the TypeSafe SDK. The API key comes from ``TYPESAFE_API_KEY`` only."""

    def __init__(self) -> None:
        from typesafe_sdk import AsyncTypeSafeClient, RetryPolicy

        self._client = AsyncTypeSafeClient(retry=RetryPolicy(max_retries=4, backoff_max=10.0))

    async def ask(self, state: Mapping[str, Any], questions: Mapping[str, Any], model: str) -> DecisionAnswers:
        response = await self._client.system_one(state=dict(state), questions=dict(questions), model=model)
        answers = {name: _plain_answer(answer) for name, answer in (response.answers or {}).items()}
        usage = getattr(response, "usage", None)
        return DecisionAnswers(answers=answers, input_tokens=(getattr(usage, "input_tokens", 0) or 0) if usage else 0)


def default_decision_model() -> DecisionModel | None:
    """Jev when the SDK is installed and ``TYPESAFE_API_KEY`` is set; otherwise none."""
    if not os.environ.get("TYPESAFE_API_KEY"):
        return None
    try:
        return TypeSafeDecisionModel()
    except ImportError:
        return None


_PROCESS_CACHE = InMemoryClassifierCache()


def process_cache() -> InMemoryClassifierCache:
    """The cache shared by checks in this process unless the caller supplies one."""
    return _PROCESS_CACHE


@dataclass
class ClassifierOutcome:
    hits: list[Hit] = field(default_factory=list)
    coverage: list[dict[str, Any]] = field(default_factory=list)
    status: dict[str, Any] = field(default_factory=dict)
    requests: int = 0
    input_tokens: int = 0
    cache_hits: int = 0


@dataclass(frozen=True)
class _Job:
    segment: Segment
    state: Mapping[str, Any]
    detectors: tuple[tuple[str, Policy, ClassifierDetector], ...]  # (question name, policy, detector)


def run_classifier_lane(
    document: SegmentedDocument,
    pack: PolicyPack,
    *,
    decision_model: DecisionModel | None,
    cache: ClassifierCache,
    options: Mapping[str, Any],
) -> ClassifierOutcome:
    detectors = [
        (policy, detector)
        for policy in pack.enabled_policies
        for detector in policy.detectors
        if isinstance(detector, ClassifierDetector)
    ]
    outcome = ClassifierOutcome()
    if not detectors:
        outcome.status = {"status": "ran", "detectors": 0}
        return outcome
    if decision_model is None:
        outcome.status = {
            "status": "unavailable",
            "reason": "no decision model is configured (set TYPESAFE_API_KEY and install limatus[jev])",
            "detectors": 0,
        }
        return outcome
    jobs = _plan_jobs(document, detectors)
    return asyncio.run(_run_jobs(jobs, len(detectors), decision_model, cache, options, outcome))


def _plan_jobs(document: SegmentedDocument, detectors: list[tuple[Policy, ClassifierDetector]]) -> list[_Job]:
    names = {(policy.id, detector.id): _question_name(policy.id, detector.id) for policy, detector in detectors}
    paragraphs = {p.id: p for p in document.paragraphs}
    candidates: list[tuple[Segment, Mapping[str, Any]]] = []
    for segment in document.sentences():
        candidates.append((segment, {"task": SENTENCE_TASK, "target": segment.text, "context": paragraphs[segment.parent_id].text}))
    for segment in document.paragraphs:
        candidates.append((segment, {"task": SEGMENT_TASK, "target": segment.text}))
    document_segment = document.segments[0]
    candidates.append((document_segment, {"task": SEGMENT_TASK, "target": "\n\n".join(p.text for p in document.paragraphs)}))

    jobs: list[_Job] = []
    for segment, state in candidates:
        scope = segment.kind
        applicable = tuple(
            (names[(policy.id, detector.id)], policy, detector)
            for policy, detector in detectors
            if detector.scope == scope and (detector.blocks is None or scope == "document" or segment.block in detector.blocks)
        )
        if applicable and state["target"]:
            jobs.append(_Job(segment, state, applicable))
    return jobs


async def _run_jobs(
    jobs: list[_Job],
    detector_count: int,
    decision_model: DecisionModel,
    cache: ClassifierCache,
    options: Mapping[str, Any],
    outcome: ClassifierOutcome,
) -> ClassifierOutcome:
    model = options.get("model", DEFAULT_MODEL)
    budget = options.get("maxInputTokens")
    semaphore = asyncio.Semaphore(options.get("maxConcurrency", DEFAULT_MAX_CONCURRENCY))
    meter = _BudgetMeter(budget)
    failures: list[str] = []
    skipped = 0

    async def run(job: _Job) -> None:
        nonlocal skipped
        questions = {name: _question_payload(policy, detector) for name, policy, detector in job.detectors}
        key = _cache_key(model, questions, job.state)
        answers = cache.get(key)
        if answers is not None:
            outcome.cache_hits += 1
        else:
            async with semaphore:
                if not await meter.reserve():
                    skipped += 1
                    return
                try:
                    reply = await decision_model.ask(job.state, questions, model)
                except Exception as error:  # the lane degrades; the check still returns
                    meter.release()
                    failures.append(f"{type(error).__name__}: {error}")
                    return
                meter.spend(reply.input_tokens)
                outcome.requests += 1
                outcome.input_tokens += reply.input_tokens
                answers = {name: _plain_answer(answer) for name, answer in reply.answers.items()}
                cache.set(key, answers)
        _record(job, answers, outcome)

    await asyncio.gather(*(run(job) for job in jobs))

    if failures and outcome.requests == 0 and outcome.cache_hits == 0:
        outcome.status = {"status": "failed", "reason": failures[0], "detectors": detector_count}
    elif failures or skipped:
        reasons = []
        if skipped:
            reasons.append(f"{skipped} segment(s) skipped: input-token budget of {budget} reached")
        if failures:
            reasons.append(f"{len(failures)} request(s) failed: {failures[0]}")
        outcome.status = {"status": "partial", "reason": "; ".join(reasons), "detectors": detector_count}
    else:
        outcome.status = {"status": "ran", "detectors": detector_count}
    outcome.coverage.sort(key=lambda c: (c["segmentId"], c["policyId"], c["detectorId"]))
    return outcome


def _record(job: _Job, answers: Mapping[str, Mapping[str, Any]], outcome: ClassifierOutcome) -> None:
    for name, policy, detector in job.detectors:
        answer = answers.get(name)
        if answer is None:
            continue
        probability = round(violation_probability(detector, answer), 4)
        outcome.coverage.append(
            {"segmentId": job.segment.id, "policyId": policy.id, "detectorId": detector.id, "probability": probability}
        )
        if probability >= detector.threshold:
            status = "violation"
        elif detector.review_at is not None and probability >= detector.review_at:
            status = "review"
        else:
            continue
        outcome.hits.append(
            Hit(
                policy,
                detector,
                job.segment.start,
                job.segment.end,
                detector.message or policy.title,
                segment=job.segment,
                status=status,
                probability=probability,
            )
        )


def violation_probability(detector: ClassifierDetector, answer: Mapping[str, Any]) -> float:
    """Probability that the answer means the segment violates the policy."""
    violation = detector.violation
    if "answer" in violation:
        yes = float(answer["noul"])
        return yes if violation["answer"] == "yes" else 1.0 - yes
    probabilities = {str(k): float(v) for k, v in (answer.get("probabilities") or {}).items()}
    if "labels" in violation:
        return min(1.0, sum(probabilities.get(label, 0.0) for label in violation["labels"]))
    below = violation["scoreBelow"]
    return min(1.0, sum(p for level, p in probabilities.items() if float(level) < below))


class _BudgetMeter:
    """Sends a request only while spent + in-flight + this one fits the budget.

    Request cost is estimated as the largest cost seen so far; until one request
    has completed, only one is allowed in flight.
    """

    def __init__(self, budget: int | None) -> None:
        self.budget = budget
        self.spent = 0
        self.in_flight = 0
        self.largest: int | None = None
        self._first_done = asyncio.Event()

    async def reserve(self) -> bool:
        if self.budget is None:
            return True
        while self.largest is None and self.in_flight:
            await self._first_done.wait()
        estimate = self.largest or 0
        if self.largest is not None and self.spent + (self.in_flight + 1) * estimate > self.budget:
            return False
        self.in_flight += 1
        return True

    def spend(self, tokens: int) -> None:
        if self.budget is None:
            return
        self.in_flight -= 1
        self.spent += tokens
        self.largest = max(self.largest or 0, tokens)
        self._first_done.set()

    def release(self) -> None:
        if self.budget is not None:
            self.in_flight -= 1
            self._first_done.set()


def _question_name(policy_id: str, detector_id: str) -> str:
    return re.sub(r"[^A-Za-z0-9_]", "_", f"{policy_id}__{detector_id}")


def _question_payload(policy: Policy, detector: ClassifierDetector) -> dict[str, Any]:
    question = detector.question
    instructions: Any = question.instructions
    if policy.violating_examples or policy.complying_examples:
        instructions = {
            "question": question.instructions,
            "policy": policy.guidance,
            "examples": {
                "violates the policy": list(policy.violating_examples),
                "complies with the policy": list(policy.complying_examples),
            },
        }
    payload: dict[str, Any] = {"type": question.type, "instructions": instructions}
    if question.criteria is not None:
        payload["criteria"] = list(question.criteria) if isinstance(question.criteria, tuple) else dict(question.criteria)
    return payload


def _cache_key(model: str, questions: Mapping[str, Any], state: Mapping[str, Any]) -> str:
    material = json.dumps({"model": model, "questions": questions, "state": state}, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def _plain_answer(answer: Any) -> dict[str, Any]:
    if hasattr(answer, "model_dump"):
        answer = answer.model_dump()
    answer = dict(answer.get("root", answer)) if isinstance(answer, Mapping) else dict(answer)
    if isinstance(answer.get("probabilities"), Mapping):
        answer["probabilities"] = {str(k): v for k, v in answer["probabilities"].items()}
    return answer
