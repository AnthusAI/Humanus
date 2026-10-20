"""Generative help for editors: rewrite options and draft classifier questions.

These are the only operations that call a generative model (Luna by default).
Neither one finds problems: ``suggest`` rewrites a span the editor chose (a
finding or any selection), and ``draft_questions`` proposes classifier
detectors that an editor reviews before saving them to a policy.
"""
from __future__ import annotations

import hashlib
import os
import re
from typing import Any, Mapping, Protocol

from .check import Utf16Offsets
from .contracts import ContractValidationError, validate_payload
from .editorial_llm import call_structured_responses_api
from .editorial_rewrite_options import _EVASION_INSTRUCTION_PATTERNS
from .policy_pack import Policy, PolicyPack, PolicyPackValidationError, load_policy_pack
from .rules_lane import run_rules_lane
from .segmentation import SegmentedDocument, normalize_text, segment_document

DEFAULT_GENERATIVE_MODEL = "gpt-6-luna"
DEFAULT_THRESHOLD = 0.8
DEFAULT_REVIEW_AT = 0.5
MAX_POLICIES_IN_PROMPT = 30
VOICE_SAMPLE_CHARS = 800


class SuggestRequestValidationError(ContractValidationError):
    """The request is not valid, or does not fit the content it refers to."""


class SuggestUnavailableError(RuntimeError):
    """No generative model is configured."""


class Generator(Protocol):
    def generate(
        self, *, model: str, system_prompt: str, user_prompt: str, schema_name: str, schema: dict[str, Any]
    ) -> dict[str, Any]: ...


class OpenAIGenerator:
    """OpenAI Responses API with structured output. Reads ``OPENAI_API_KEY``."""

    def generate(
        self, *, model: str, system_prompt: str, user_prompt: str, schema_name: str, schema: dict[str, Any]
    ) -> dict[str, Any]:
        return call_structured_responses_api(
            model=model,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            schema_name=schema_name,
            schema=schema,
            max_output_tokens=4000,
        )


def default_generator() -> Generator | None:
    return OpenAIGenerator() if os.environ.get("OPENAI_API_KEY", "").strip() else None


_DEFAULT = object()
_UNAVAILABLE = "No rewrite model is configured: set OPENAI_API_KEY (model defaults to gpt-6-luna)."


# --- suggest ----------------------------------------------------------------------

_OPTIONS_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["options"],
    "properties": {
        "options": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["replacement", "rationale", "factVerificationRequired", "unresolvedQuestions"],
                "properties": {
                    "replacement": {"type": "string"},
                    "rationale": {"type": "string"},
                    "factVerificationRequired": {"type": "boolean"},
                    "unresolvedQuestions": {"type": "array", "items": {"type": "string"}},
                },
            },
        }
    },
}

_SUGGEST_SYSTEM = """You are a senior copy editor{publication}. Rewrite only the TARGET text marked in the draft.

Rules:
- Do not add facts, numbers, names, quotes, sources or experiences that the draft does not contain. If a good fix needs information the draft lacks, keep the claim honest and ask for it in unresolvedQuestions.
- Keep the author's voice, tense, person and register.
- Keep any inline markup inside the target (links, inline code, citations such as [@key], emphasis).
- Each replacement substitutes for the target exactly, so it must read correctly between the text before and after it.
- Offer {count} clearly different option(s). Set factVerificationRequired to true when an option changes what a factual claim says.
- Never suggest changes meant to evade AI detection or to add fake imperfections."""


def suggest(request: Mapping[str, Any], *, generator: Generator | None | object = _DEFAULT) -> dict[str, Any]:
    """Rewrite options for ``request["finding"]`` or ``request["selection"]``."""
    validate_payload("suggest-request-v1", request, SuggestRequestValidationError)
    pack = _load_pack(request["pack"], "suggest-request-v1")
    content = request["content"]
    text = content["text"]
    document = segment_document(text, content["format"])
    offsets = Utf16Offsets(text)
    finding = request.get("finding")
    span16 = finding["span"] if finding else request["selection"]
    start, end = _code_point_span(offsets, span16)
    _require_prose(document, start, end)
    excerpt = text[start:end]
    policy: Policy | None = None
    if finding:
        if not finding["excerpt"] or finding["excerpt"] != excerpt:
            raise SuggestRequestValidationError(
                "suggest-request-v1",
                "the finding no longer matches the content (or covers the whole document); run check again",
                "finding",
            )
        try:
            policy = pack.policy(finding["policyId"])
        except KeyError:
            raise SuggestRequestValidationError("suggest-request-v1", "the finding's policy is not in the pack", "finding/policyId") from None

    # A finding may flag a few words; rewriting them in isolation yields fragments,
    # so the rewrite target is the whole sentence that contains them. An editor's
    # own selection is rewritten exactly as selected.
    flag: tuple[int, int] | None = None
    if finding:
        sentence = next((s for s in document.sentences() if s.start <= start and end <= s.end), None)
        if sentence is not None and (sentence.start, sentence.end) != (start, end):
            flag = (start, end)
            start, end = sentence.start, sentence.end
            excerpt = text[start:end]
            span16 = {"start": offsets(start), "end": offsets(end)}

    options = request.get("options", {})
    model = options.get("model", DEFAULT_GENERATIVE_MODEL)
    count = options.get("count", 3)
    active = default_generator() if generator is _DEFAULT else generator
    if active is None:
        raise SuggestUnavailableError(_UNAVAILABLE)

    reply = active.generate(
        model=model,
        system_prompt=_SUGGEST_SYSTEM.format(publication=f" for {pack.title}" if pack.title else "", count=count),
        user_prompt=_suggest_prompt(pack, document, start, end, flag, policy, finding, options.get("instructions")),
        schema_name="rewrite_options",
        schema=_OPTIONS_SCHEMA,
    )

    target_key = finding["id"] if finding else f"selection:{normalize_text(excerpt)}"
    kept: list[dict[str, Any]] = []
    dropped: list[dict[str, str]] = []
    seen: set[str] = set()
    for option in reply.get("options", []):
        replacement = str(option.get("replacement", "")).strip()
        reason = _rejection(replacement, str(option.get("rationale", "")), excerpt, seen, document, start, end, policy, finding)
        if reason:
            dropped.append({"replacement": replacement, "reason": reason})
            continue
        seen.add(normalize_text(replacement))
        if len(kept) < count:
            kept.append(
                {
                    "id": "o-" + hashlib.sha256(f"{target_key}\x1f{replacement}".encode("utf-8")).hexdigest()[:12],
                    "span": dict(span16),
                    "replacement": replacement,
                    "rationale": str(option.get("rationale", "")).strip(),
                    "factVerificationRequired": bool(option.get("factVerificationRequired", False)),
                    "unresolvedQuestions": [str(q) for q in option.get("unresolvedQuestions", [])],
                }
            )

    target: dict[str, Any] = {"span": dict(span16), "excerpt": excerpt}
    if finding:
        target["findingId"] = finding["id"]
    result: dict[str, Any] = {"schemaVersion": 1, "offsetUnit": "utf16", "target": target, "model": model, "options": kept}
    if dropped:
        result["dropped"] = dropped
    return result


def _load_pack(payload: Mapping[str, Any], schema_name: str) -> PolicyPack:
    try:
        return load_policy_pack(payload, schema_checked=True)
    except PolicyPackValidationError as exc:
        raise SuggestRequestValidationError(schema_name, str(exc), "/".join(p for p in ("pack", exc.location) if p)) from exc


def _code_point_span(offsets: Utf16Offsets, span16: Mapping[str, int]) -> tuple[int, int]:
    try:
        start, end = offsets.to_index(span16["start"]), offsets.to_index(span16["end"])
    except ValueError as exc:
        raise SuggestRequestValidationError("suggest-request-v1", str(exc), "selection") from exc
    if start >= end:
        raise SuggestRequestValidationError("suggest-request-v1", "the span is empty", "selection")
    return start, end


def _require_prose(document: SegmentedDocument, start: int, end: int) -> None:
    in_prose = any(p.start < end and start < p.end for p in document.paragraphs)
    in_protected = any(r.start < end and start < r.end for r in document.protected)
    if in_protected or not in_prose:
        raise SuggestRequestValidationError(
            "suggest-request-v1",
            "the span must cover prose, not code, quotes, directives, tables or front matter",
            "selection",
        )


def _suggest_prompt(
    pack: PolicyPack,
    document: SegmentedDocument,
    start: int,
    end: int,
    flag: tuple[int, int] | None,
    policy: Policy | None,
    finding: Mapping[str, Any] | None,
    note: str | None,
) -> str:
    parts: list[str] = []
    if pack.guidance:
        parts.append(f"House guidance: {pack.guidance}")
    house = [p for p in pack.enabled_policies if p is not policy][:MAX_POLICIES_IN_PROMPT]
    if house:
        parts.append("Policies the rewrite must also respect:\n" + "\n".join(f"- {p.title}: {_one_line(p.guidance)}" for p in house))
    if policy is not None:
        lines = [f"The target breaks this policy: {policy.title}. {policy.guidance}"]
        if finding and finding.get("message"):
            lines.append(f"Why it was flagged: {finding['message']}")
        if policy.rewrite_guidance:
            lines.append(f"How to fix it: {policy.rewrite_guidance}")
        if policy.complying_examples:
            lines.append("Examples that comply: " + " | ".join(policy.complying_examples))
        parts.append("\n".join(lines))
    if note:
        parts.append(f"Editor's note: {note}")
    if pack.reference_samples:
        parts.append(f"Approved writing in the house voice:\n{pack.reference_samples[0].text[:VOICE_SAMPLE_CHARS]}")

    paragraphs = document.paragraphs
    touched = [i for i, p in enumerate(paragraphs) if p.start < end and start < p.end]
    first, last = max(touched[0] - 1, 0), min(touched[-1] + 1, len(paragraphs) - 1)
    text = document.text
    context_start, context_end = paragraphs[first].start, paragraphs[last].end
    target = text[start:end]
    if flag is not None:
        flag_start, flag_end = flag[0] - start, flag[1] - start
        target = target[:flag_start] + "[[FLAG]]" + target[flag_start:flag_end] + "[[/FLAG]]" + target[flag_end:]
    marked = text[context_start:start] + "[[TARGET]]" + text[start:end] + "[[/TARGET]]" + text[end:context_end]
    parts.append(f"Draft excerpt, with the target marked:\n{marked}")
    parts.append(f"Target text{' (the flagged words are marked [[FLAG]])' if flag else ''}:\n{target}")
    parts.append("Each replacement must replace the whole target text, without the markers.")
    return "\n\n".join(parts)


def _one_line(text: str) -> str:
    return normalize_text(text)[:300]


def _rejection(
    replacement: str,
    rationale: str,
    excerpt: str,
    seen: set[str],
    document: SegmentedDocument,
    start: int,
    end: int,
    policy: Policy | None,
    finding: Mapping[str, Any] | None,
) -> str | None:
    if normalize_text(replacement) == normalize_text(excerpt):
        return "identical to the original"
    if normalize_text(replacement) in seen:
        return "duplicate of another option"
    if any(pattern.search(rationale) or pattern.search(replacement) for pattern in _EVASION_INSTRUCTION_PATTERNS):
        return "aims at evading AI detection or adding fake imperfections"
    if policy is not None and finding is not None and finding.get("lane") == "rules":
        if _still_breaks(document, start, end, replacement, policy, finding["detectorId"]):
            return f"still breaks policy '{policy.id}'"
    return None


def _still_breaks(
    document: SegmentedDocument, start: int, end: int, replacement: str, policy: Policy, detector_id: str
) -> bool:
    new_text = document.text[:start] + replacement + document.text[end:]
    detector = next(d for d in policy.detectors if d.id == detector_id)
    single = PolicyPack(pack_id="recheck", version="1", policies=(Policy(
        id=policy.id, version=policy.version, title=policy.title, guidance=policy.guidance,
        severity=policy.severity, detectors=(detector,),
    ),))
    hits, _ = run_rules_lane(segment_document(new_text), single)
    new_end = start + len(replacement)
    return any(hit.start < new_end and start < hit.end and (hit.end - hit.start) < len(new_text) for hit in hits)


# --- draft questions -------------------------------------------------------------

_QUESTIONS_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["detectors"],
    "properties": {
        "detectors": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["id", "scope", "questionType", "instructions", "violationAnswer", "why"],
                "properties": {
                    "id": {"type": "string"},
                    "scope": {"type": "string", "enum": ["sentence", "paragraph", "document"]},
                    "questionType": {"type": "string", "enum": ["noul"]},
                    "instructions": {"type": "string"},
                    "violationAnswer": {"type": "string", "enum": ["yes", "no"]},
                    "why": {"type": "string"},
                },
            },
        }
    },
}

_QUESTIONS_SYSTEM = """You help editors turn an editorial policy written in prose into questions for a zero-shot decision model.

The decision model answers yes/no questions about a `target` text and returns a probability. It can judge:
- a sentence (it also sees the surrounding paragraph as context),
- a paragraph,
- the whole document.

Write at most {max_detectors} atomic questions. Each question checks one thing the policy forbids or requires. Phrase it about "the target sentence", "the target paragraph" or "the target document", so that the violating answer is unambiguous. Prefer sentence scope for wording problems, paragraph scope for structure and argument, and document scope only for whole-piece properties. Do not restate the whole policy in one question. Give each a short kebab-case id."""


def draft_questions(request: Mapping[str, Any], *, generator: Generator | None | object = _DEFAULT) -> dict[str, Any]:
    """Draft classifier detectors for a policy; an editor reviews them before saving."""
    validate_payload("draft-questions-request-v1", request, SuggestRequestValidationError)
    policy = request["policy"]
    options = request.get("options", {})
    model = options.get("model", DEFAULT_GENERATIVE_MODEL)
    max_detectors = options.get("maxDetectors", 3)
    active = default_generator() if generator is _DEFAULT else generator
    if active is None:
        raise SuggestUnavailableError(_UNAVAILABLE)

    prompt = [f"Policy: {policy['title']}", f"Guidance: {policy['guidance']}"]
    examples = policy.get("examples", {})
    if examples.get("violates"):
        prompt.append("Text that violates it: " + " | ".join(examples["violates"]))
    if examples.get("complies"):
        prompt.append("Text that complies: " + " | ".join(examples["complies"]))
    reply = active.generate(
        model=model,
        system_prompt=_QUESTIONS_SYSTEM.format(max_detectors=max_detectors),
        user_prompt="\n".join(prompt),
        schema_name="classifier_questions",
        schema=_QUESTIONS_SCHEMA,
    )

    detectors: list[dict[str, Any]] = []
    notes: list[str] = []
    for proposal in reply.get("detectors", []):
        detector_id = re.sub(r"[^a-z0-9._-]+", "-", str(proposal.get("id", "")).lower()).strip("-") or f"question-{len(detectors) + 1}"
        detector = {
            "id": detector_id,
            "lane": "classifier",
            "scope": proposal.get("scope"),
            "question": {"type": "noul", "instructions": str(proposal.get("instructions", "")).strip()},
            "violation": {"answer": proposal.get("violationAnswer", "yes")},
            "threshold": DEFAULT_THRESHOLD,
            "reviewAt": DEFAULT_REVIEW_AT,
        }
        problem = _detector_problem(detector, [d["id"] for d in detectors])
        if problem:
            notes.append(f"Detector '{detector_id}' rejected: {problem}")
            continue
        if len(detectors) >= max_detectors:
            notes.append(f"Detector '{detector_id}' rejected: more than {max_detectors} proposed")
            continue
        detectors.append(detector)
        if proposal.get("why"):
            notes.append(f"{detector_id}: {proposal['why']}")
    return {"schemaVersion": 1, "model": model, "detectors": detectors, "notes": notes}


def _detector_problem(detector: dict[str, Any], taken: list[str]) -> str | None:
    if detector["id"] in taken:
        return "duplicate id"
    probe = {
        "schemaVersion": 1,
        "packId": "probe",
        "version": "1",
        "policies": [{"id": "probe", "version": 1, "title": "probe", "guidance": "probe", "severity": "info", "detectors": [detector]}],
    }
    try:
        load_policy_pack(probe)
    except PolicyPackValidationError as exc:
        return str(exc)
    return None
