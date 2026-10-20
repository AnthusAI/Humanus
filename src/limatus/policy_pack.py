"""Policy packs: the caller-supplied editorial policies Limatus enforces.

A pack arrives as a payload (dict, JSON or YAML) with every request. It is
validated against ``policy-pack-v1`` and then against the rules a schema
cannot express (unique ids, compilable regexes, coherent thresholds).
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping, Union

import yaml

from .contracts import ContractValidationError, validate_payload

SCHEMA_NAME = "policy-pack-v1"


class PolicyPackValidationError(ContractValidationError):
    """The policy pack payload is not a valid ``policy-pack-v1`` document."""


@dataclass(frozen=True)
class RegexDetector:
    id: str
    pattern: str
    ignore_case: bool = False
    exceptions: tuple[str, ...] = ()
    message: str | None = None
    blocks: tuple[str, ...] | None = None
    lane: str = field(default="rules", init=False)
    kind: str = field(default="regex", init=False)


@dataclass(frozen=True)
class PhraseDetector:
    id: str
    phrases: tuple[str, ...]
    case_sensitive: bool = False
    replacement: str | None = None
    exceptions: tuple[str, ...] = ()
    message: str | None = None
    blocks: tuple[str, ...] | None = None
    lane: str = field(default="rules", init=False)
    kind: str = field(default="phrase", init=False)


@dataclass(frozen=True)
class BuiltinDetector:
    id: str
    check: str
    params: Mapping[str, Any] = field(default_factory=dict)
    message: str | None = None
    blocks: tuple[str, ...] | None = None
    lane: str = field(default="rules", init=False)
    kind: str = field(default="builtin", init=False)


@dataclass(frozen=True)
class Question:
    type: str
    instructions: str
    # noul: {"true": ..., "false": ...}; choice: label -> description; score: level descriptions
    criteria: Mapping[str, str | None] | tuple[str, ...] | None = None


@dataclass(frozen=True)
class ClassifierDetector:
    id: str
    scope: str
    question: Question
    violation: Mapping[str, Any]
    threshold: float
    review_at: float | None = None
    calibration: Mapping[str, Any] | None = None
    message: str | None = None
    blocks: tuple[str, ...] | None = None
    lane: str = field(default="classifier", init=False)
    kind: str = field(default="classifier", init=False)


Detector = Union[RegexDetector, PhraseDetector, BuiltinDetector, ClassifierDetector]


@dataclass(frozen=True)
class Policy:
    id: str
    version: int
    title: str
    guidance: str
    severity: str
    detectors: tuple[Detector, ...]
    enabled: bool = True
    tags: tuple[str, ...] = ()
    violating_examples: tuple[str, ...] = ()
    complying_examples: tuple[str, ...] = ()
    rewrite_guidance: str | None = None


@dataclass(frozen=True)
class ReferenceSample:
    id: str
    text: str
    title: str | None = None
    url: str | None = None


@dataclass(frozen=True)
class PolicyPack:
    pack_id: str
    version: str
    policies: tuple[Policy, ...]
    title: str | None = None
    guidance: str | None = None
    language: str = "en"
    reference_samples: tuple[ReferenceSample, ...] = ()

    def policy(self, policy_id: str) -> Policy:
        for policy in self.policies:
            if policy.id == policy_id:
                return policy
        raise KeyError(policy_id)

    @property
    def enabled_policies(self) -> tuple[Policy, ...]:
        return tuple(policy for policy in self.policies if policy.enabled)


def load_policy_pack(source: Mapping[str, Any] | str | Path, *, schema_checked: bool = False) -> PolicyPack:
    """Load and validate a policy pack from a payload or a JSON/YAML file path.

    ``schema_checked`` skips the JSON Schema pass when the caller already
    validated the payload as part of a larger document.
    """
    payload = _read_source(source)
    if not schema_checked:
        validate_payload(SCHEMA_NAME, payload, PolicyPackValidationError)
    pack = _parse_pack(payload)
    _check_semantics(pack)
    return pack


def _read_source(source: Mapping[str, Any] | str | Path) -> Any:
    if isinstance(source, Mapping):
        return dict(source)
    path = Path(source)
    try:
        text = path.read_text(encoding="utf-8")
        return json.loads(text) if path.suffix.lower() == ".json" else yaml.safe_load(text)
    except (OSError, json.JSONDecodeError, yaml.YAMLError, UnicodeDecodeError) as exc:
        raise PolicyPackValidationError(SCHEMA_NAME, f"could not read {path}: {exc}") from exc


def _parse_pack(raw: Mapping[str, Any]) -> PolicyPack:
    return PolicyPack(
        pack_id=raw["packId"],
        version=raw["version"],
        title=raw.get("title"),
        guidance=raw.get("guidance"),
        language=raw.get("language", "en"),
        policies=tuple(_parse_policy(item) for item in raw["policies"]),
        reference_samples=tuple(
            ReferenceSample(id=s["id"], text=s["text"], title=s.get("title"), url=s.get("url"))
            for s in raw.get("referenceSamples", ())
        ),
    )


def _parse_policy(raw: Mapping[str, Any]) -> Policy:
    examples = raw.get("examples", {})
    return Policy(
        id=raw["id"],
        version=raw["version"],
        title=raw["title"],
        guidance=raw["guidance"],
        severity=raw["severity"],
        enabled=raw.get("enabled", True),
        tags=tuple(raw.get("tags", ())),
        detectors=tuple(_parse_detector(item) for item in raw["detectors"]),
        violating_examples=tuple(examples.get("violates", ())),
        complying_examples=tuple(examples.get("complies", ())),
        rewrite_guidance=raw.get("rewriteGuidance"),
    )


def _parse_detector(raw: Mapping[str, Any]) -> Detector:
    common = {
        "id": raw["id"],
        "message": raw.get("message"),
        "blocks": tuple(raw["blocks"]) if "blocks" in raw else None,
    }
    if raw["lane"] == "classifier":
        question = raw["question"]
        return ClassifierDetector(
            scope=raw["scope"],
            question=Question(
                type=question["type"],
                instructions=question["instructions"],
                criteria=tuple(question["criteria"]) if isinstance(question.get("criteria"), list) else question.get("criteria"),
            ),
            violation=dict(raw["violation"]),
            threshold=raw["threshold"],
            review_at=raw.get("reviewAt"),
            calibration=raw.get("calibration"),
            **common,
        )
    if raw["kind"] == "regex":
        return RegexDetector(
            pattern=raw["pattern"],
            ignore_case=raw.get("ignoreCase", False),
            exceptions=tuple(raw.get("exceptions", ())),
            **common,
        )
    if raw["kind"] == "phrase":
        return PhraseDetector(
            phrases=tuple(raw["phrases"]),
            case_sensitive=raw.get("caseSensitive", False),
            replacement=raw.get("replacement"),
            exceptions=tuple(raw.get("exceptions", ())),
            **common,
        )
    return BuiltinDetector(check=raw["check"], params=dict(raw.get("params", {})), **common)


def _check_semantics(pack: PolicyPack) -> None:
    seen_policies: set[str] = set()
    for p_index, policy in enumerate(pack.policies):
        if policy.id in seen_policies:
            _fail(f"duplicate policy id '{policy.id}'", f"policies/{p_index}/id")
        seen_policies.add(policy.id)
        seen_detectors: set[str] = set()
        for d_index, detector in enumerate(policy.detectors):
            location = f"policies/{p_index}/detectors/{d_index}"
            if detector.id in seen_detectors:
                _fail(f"duplicate detector id '{detector.id}' in policy '{policy.id}'", f"{location}/id")
            seen_detectors.add(detector.id)
            if isinstance(detector, RegexDetector):
                for key, pattern in [("pattern", detector.pattern), *[("exceptions", e) for e in detector.exceptions]]:
                    try:
                        re.compile(pattern)
                    except re.error as exc:
                        _fail(f"regex '{pattern}' does not compile: {exc}", f"{location}/{key}")
            if isinstance(detector, ClassifierDetector):
                _check_classifier(detector, location)


def _check_classifier(detector: ClassifierDetector, location: str) -> None:
    if detector.review_at is not None and detector.review_at >= detector.threshold:
        _fail("reviewAt must be lower than threshold", f"{location}/reviewAt")
    question_type = detector.question.type
    violation = detector.violation
    expected = {"noul": "answer", "choice": "labels", "score": "scoreBelow"}[question_type]
    if expected not in violation:
        _fail(f"a {question_type} question needs a violation '{expected}'", f"{location}/violation")
    if question_type == "choice":
        unknown = set(violation["labels"]) - set(detector.question.criteria or {})
        if unknown:
            _fail(f"violation labels not among question criteria: {sorted(unknown)}", f"{location}/violation")
    if question_type == "score" and not 0 < violation["scoreBelow"] < len(detector.question.criteria or ()):
        _fail("scoreBelow must fall between the lowest and highest score level", f"{location}/violation")


def _fail(message: str, location: str) -> None:
    raise PolicyPackValidationError(SCHEMA_NAME, message, location)
