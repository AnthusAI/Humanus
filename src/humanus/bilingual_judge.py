"""The judge lane: a bilingual model reads each source block beside its translation.

Humanus calls no model here. The caller supplies a :class:`BilingualJudge`,
any callable that takes the prompt :func:`judge_prompt` builds (a system
message, a user message and the JSON Schema its answer must follow) and
returns that answer as parsed JSON. Papyrus wires its own model; tests pass a
scripted fake.

The judge marks problems by MQM category and must quote both sides. Code
confirms every quote is in the text it claims to quote; an answer whose quote
is not there is dropped and counted (``rejected``). Each block is read in
``passes`` independent passes: a problem every pass reports is a violation,
one that only some passes report is for review, so a block counts as clean
only when the passes agree that it is.
"""
from __future__ import annotations

import json
from collections import defaultdict
from typing import Any, Callable, Mapping

from jsonschema import Draft202012Validator

from .languages import Language
from .parity import Bitext, ParityCannotRun, Unit
from .policy_pack import JudgeDetector, Policy, PolicyPack
from .rules_lane import Hit
from .segmentation import normalize_text

BilingualJudge = Callable[[Mapping[str, Any]], Mapping[str, Any]]

CATEGORY_DEFINITIONS = {
    "mistranslation": "the translation says something different from the source",
    "omission": "something the source says is missing from the translation",
    "addition": "the translation says something the source does not",
    "certainty-changed": "a hedge was dropped or certainty added or removed (may / will, reportedly / did)",
    "terminology": "a term is rendered with the wrong word for this field or against the glossary",
    "attribution-changed": "who says or claims something changed, or an attribution was dropped",
}


class JudgeAnswerError(ValueError):
    """The judge's answer does not follow the response schema it was given."""


def response_schema(categories: tuple[str, ...]) -> dict[str, Any]:
    """The JSON Schema a judge's answer must follow."""
    return {
        "type": "object",
        "additionalProperties": False,
        "required": ["issues"],
        "properties": {
            "issues": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["category", "sourceQuote", "targetQuote", "explanation"],
                    "properties": {
                        "category": {"enum": list(categories)},
                        "sourceQuote": {"type": "string", "description": "Exact words copied from the source block; empty only for an addition."},
                        "targetQuote": {"type": "string", "description": "Exact words copied from the translated block; empty only for an omission."},
                        "explanation": {"type": "string", "minLength": 1, "description": "One sentence, in English."},
                    },
                },
            }
        },
    }


def judge_prompt(
    *,
    source_language: Language,
    target_language: Language,
    source_block: str,
    target_block: str,
    context: list[tuple[str, str]],
    categories: tuple[str, ...],
    glossary: tuple[tuple[str, tuple[str, ...]], ...] = (),
    pass_number: int = 1,
) -> dict[str, Any]:
    """The prompt for one block: what a bilingual judge reads and the schema its answer follows."""
    definitions = "\n".join(f"- {name}: {CATEGORY_DEFINITIONS[name]}" for name in categories)
    system = (
        f"You compare a translation from {source_language.name} ({source_language.tag}) into {target_language.name} "
        f"({target_language.tag}) with its source, block by block, and report only faithfulness problems: places where the "
        f"translation does not say what the source says. Do not report style, fluency or typography. The target language's own "
        f"conventions of naming, register and number or date format are not problems; a dropped or changed claim always is.\n\n"
        f"Categories:\n{definitions}\n\n"
        "For each problem copy the exact words from the source block (sourceQuote) and from the translated block (targetQuote); "
        "leave sourceQuote empty only for an addition and targetQuote empty only for an omission. Quotes are checked against the "
        "text and an answer whose quote is not there is discarded. Report no issues when the block is faithful."
    )
    parts = []
    if context:
        parts.append("Neighbouring blocks, for reference only (do not judge them):")
        for source, target in context:
            parts.append(f"SOURCE: {source}\nTRANSLATION: {target}")
    if glossary:
        parts.append("Glossary (approved renderings):\n" + "\n".join(f"- {term}: {' / '.join(forms) or '(keep unchanged)'}" for term, forms in glossary))
    parts.append(f"Block to judge.\nSOURCE ({source_language.tag}):\n{source_block}\n\nTRANSLATION ({target_language.tag}):\n{target_block}")
    return {
        "system": system,
        "user": "\n\n".join(parts),
        "responseSchema": response_schema(categories),
        "pass": pass_number,
    }


def run_judge_lane(bitext: Bitext, pack: PolicyPack, judge: BilingualJudge | None) -> tuple[list[Hit], dict[str, Any]]:
    """Ask the judge about every aligned block, ``passes`` times per detector; return the hits and the lane status."""
    detectors = [(p, d) for p in pack.enabled_policies for d in p.detectors if isinstance(d, JudgeDetector)]
    if not detectors:
        return [], {"status": "ran", "detectors": 0}
    if judge is None:
        return [], {
            "status": "unavailable",
            "reason": "no bilingual judge was supplied to this check; faithfulness was not judged, only the parity checks ran",
            "detectors": 0,
        }
    try:
        units = bitext.units()
    except ParityCannotRun as exc:
        not_run = [{"policyId": p.id, "detectorId": d.id, "reason": str(exc)} for p, d in detectors]
        return [], {"status": "ran", "detectors": 0, "notRun": not_run}
    hits: list[Hit] = []
    rejected = 0
    try:
        for policy, detector in detectors:
            for index, unit in enumerate(units):
                unit_hits, unit_rejected = _judge_unit(bitext, units, index, policy, detector, judge)
                hits.extend(unit_hits)
                rejected += unit_rejected
    except JudgeAnswerError as exc:
        return [], {"status": "failed", "reason": str(exc), "detectors": 0}
    status: dict[str, Any] = {"status": "ran", "detectors": len(detectors)}
    if rejected:
        status["rejected"] = rejected
    return hits, status


def _judge_unit(bitext: Bitext, units: tuple[Unit, ...], index: int, policy: Policy, detector: JudgeDetector, judge: BilingualJudge) -> tuple[list[Hit], int]:
    unit = units[index]
    source_block, target_block = bitext.source_text(unit), bitext.target_text(unit)
    context = [(bitext.source_text(u), bitext.target_text(u)) for u in units[max(0, index - 1) : index] + units[index + 1 : index + 2] if u.prose]
    glossary = tuple((e.term, e.translations) for e in bitext.glossary if e.term.lower() in source_block.lower())
    validator = Draft202012Validator(response_schema(detector.categories))
    reports: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    rejected = 0
    for pass_number in range(1, detector.passes + 1):
        prompt = judge_prompt(
            source_language=bitext.source.language,
            target_language=bitext.target.language,
            source_block=source_block,
            target_block=target_block,
            context=context,
            categories=detector.categories,
            glossary=glossary,
            pass_number=pass_number,
        )
        answer = judge(prompt)
        errors = sorted(validator.iter_errors(answer), key=lambda e: e.path)
        if errors:
            raise JudgeAnswerError(f"the bilingual judge's answer does not follow its response schema: {errors[0].message} ({json.dumps(answer, ensure_ascii=False)[:200]})")
        seen_this_pass: set[tuple[str, str, str]] = set()
        for issue in answer["issues"]:
            located = _locate(issue, source_block, target_block)
            if located is None:
                rejected += 1
                continue
            key = (issue["category"], normalize_text(issue["sourceQuote"]), normalize_text(issue["targetQuote"]))
            if key in seen_this_pass:
                continue
            seen_this_pass.add(key)
            reports[key].append({**issue, "_spans": located})
    hits = []
    for (category, _, _), issues in reports.items():
        (s_start, s_end), (t_start, t_end) = issues[0]["_spans"]
        agreeing = len(issues)
        hits.append(
            Hit(
                policy,
                detector,
                unit.target[0] + t_start,
                unit.target[0] + t_end,
                detector.message or f"{category}: {issues[0]['explanation']}",
                status="violation" if agreeing == detector.passes else "review",
                source_span=(unit.source[0] + s_start, unit.source[0] + s_end),
                judgment={
                    "category": category,
                    "passes": detector.passes,
                    "agreeing": agreeing,
                    "explanations": [issue["explanation"] for issue in issues],
                },
            )
        )
    return hits, rejected


def _locate(issue: Mapping[str, Any], source_block: str, target_block: str) -> tuple[tuple[int, int], tuple[int, int]] | None:
    """Spans of the two quotes in their blocks (a whole block for an empty quote), or None when a quote is not there."""
    source_quote, target_quote = issue["sourceQuote"].strip(), issue["targetQuote"].strip()
    if not source_quote and not target_quote:
        return None
    if not source_quote and issue["category"] != "addition":
        return None
    if not target_quote and issue["category"] != "omission":
        return None
    source_span = _find(source_block, source_quote)
    target_span = _find(target_block, target_quote)
    if source_span is None or target_span is None:
        return None
    return source_span, target_span


def _find(block: str, quote: str) -> tuple[int, int] | None:
    if not quote:
        return 0, len(block)
    at = block.find(quote)
    return None if at < 0 else (at, at + len(quote))
