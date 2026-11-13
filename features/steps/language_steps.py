from __future__ import annotations

import json
import sys
from pathlib import Path

from behave import given, then, when

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from humanus.check import CheckRequestValidationError, Utf16Offsets, check  # noqa: E402
from humanus.languages import resolve_language  # noqa: E402
from humanus.packs import builtin_pack  # noqa: E402
from humanus.segmentation import segment_document  # noqa: E402

MULTILINGUAL = REPO_ROOT / "features" / "fixtures" / "multilingual"
GOLDEN = MULTILINGUAL / "english-regression-0.34.0.json"
TYPOGRAPHY_PACKS = {"typography-zh-hans", "typography-es"}


def _pack(language: str, policies: list[dict]) -> dict:
    return {"schemaVersion": 1, "packId": "example", "version": "1", "language": language, "policies": policies}


def _policy(policy_id: str, detector: dict) -> dict:
    return {"id": policy_id, "version": 1, "title": policy_id, "guidance": f"Guidance for {policy_id}.", "severity": "info", "detectors": [detector]}


def _check(text: str, language: str, pack: dict) -> dict:
    request = {"schemaVersion": 1, "content": {"format": "markus", "language": language, "text": text}, "pack": pack}
    return check(request, decision_model=None)


def _run(context, packs: list[dict]) -> None:
    context.ml_results = None
    context.ml_error = None
    try:
        context.ml_results = [_check(context.ml_text, context.ml_language, pack) for pack in packs]
    except CheckRequestValidationError as exc:
        context.ml_error = exc


def _findings(context) -> list[dict]:
    assert context.ml_error is None, context.ml_error
    return sorted((f for r in context.ml_results for f in r["findings"]), key=lambda f: (f["span"]["start"], f["span"]["end"]))


def _apply(text: str, findings: list[dict]) -> str:
    offsets = Utf16Offsets(text)
    edits = sorted(
        ((offsets.to_index(f["span"]["start"]), offsets.to_index(f["span"]["end"]), f["replacement"]) for f in findings if "replacement" in f),
        reverse=True,
    )
    for (start, end, _), (next_start, _, _) in zip(edits, edits[1:]):
        assert next_start <= start, "replacements overlap"
    for start, end, replacement in edits:
        text = text[:start] + replacement + text[end:]
    return text


# --- drafts and packs ---------------------------------------------------------------


@given('a draft in "{language}":')
def step_draft_in(context, language):
    context.ml_language = language
    context.ml_text = context.text


@given('the Chinese draft "{name}" from the multilingual design')
def step_design_draft(context, name):
    context.ml_language = "zh-Hans"
    context.ml_text = (MULTILINGUAL / name).read_text(encoding="utf-8")


@given('a "{language}" policy that lists the phrase "{phrase}"')
def step_phrase_policy(context, language, phrase):
    context.ml_pack = _pack(language, [_policy("phrase", {"id": "p", "lane": "rules", "kind": "phrase", "phrases": [phrase]})])


@given('a "{language}" policy for the frame "{frame}"')
def step_frame_policy(context, language, frame):
    parts = [part.strip() for part in frame.split("…")]
    context.ml_pack = _pack(language, [_policy("frame", {"id": "f", "lane": "rules", "kind": "builtin", "check": "frame", "params": {"parts": parts}})])


@given('the "{language}" language pack records how often native writing uses the passive marker "{marker}"')
def step_baseline_recorded(context, language, marker):
    pack = resolve_language(language)
    assert marker in pack.lexicon("passiveMarkers")
    assert pack.baseline["passiveMarkers"]["per1000"] > 0


@given('a "{language}" policy that flags a paragraph using "{lexicon}" far more often than that')
def step_density_policy(context, language, lexicon):
    detector = {"id": "d", "lane": "rules", "kind": "builtin", "check": "density", "params": {"lexicon": lexicon}}
    context.ml_pack = _pack(language, [_policy("density", detector)])


@given('a "{language}" policy that limits sentences to {limit:d} units')
def step_length_policy(context, language, limit):
    detector = {"id": "l", "lane": "rules", "kind": "builtin", "check": "sentence_length", "params": {"maxWords": limit}}
    context.ml_pack = _pack(language, [_policy("length", detector)])


@given('a "{language}" policy that needs the word class tagged "{tag}"')
def step_tag_policy(context, language, tag):
    detector = {"id": "t", "lane": "rules", "kind": "builtin", "check": "density", "params": {"tag": tag}}
    context.ml_pack = _pack(language, [_policy("pronoun-density", detector)])


@given('a language-neutral policy that uses the built-in check "{name}"')
def step_neutral_builtin(context, name):
    context.ml_pack = _pack("*", [_policy("builtin", {"id": "b", "lane": "rules", "kind": "builtin", "check": name})])


# --- checking ------------------------------------------------------------------------


@when('Humanus checks it with the "{name}" starter pack')
def step_check_starter(context, name):
    _run(context, [builtin_pack(name)])


@when('Humanus checks it with the "{first}" and "{second}" starter packs')
def step_check_two_starters(context, first, second):
    _run(context, [builtin_pack(first), builtin_pack(second)])


@when("Humanus checks it with that policy")
def step_check_policy(context):
    _run(context, [context.ml_pack])


@when("Humanus checks it with a language-neutral policy pack")
def step_check_neutral(context):
    _run(context, [_pack("*", [_policy("placeholder", {"id": "todo", "lane": "rules", "kind": "regex", "pattern": "TODO"})])])


@when("every typography replacement is applied and the draft is checked again")
def step_apply_and_recheck(context):
    context.ml_text = _apply(context.ml_text, _findings(context))
    _run(context, [builtin_pack("typography-zh-hans")])


# --- results -------------------------------------------------------------------------


@then("the result has {count:d} sentence segments")
def step_sentence_count(context, count):
    sentences = [s for s in context.ml_results[0]["segments"] if s["kind"] == "sentence"]
    assert len(sentences) == count, [s["text"] for s in sentences]
    context.ml_sentences = sentences


@then("each sentence ends with a closing quotation mark")
def step_closing_quotes(context):
    assert all(s["text"].endswith("”") for s in context.ml_sentences), [s["text"] for s in context.ml_sentences]


@then("the sentences are:")
def step_sentences_are(context):
    sentences = [s["text"] for s in context.ml_results[0]["segments"] if s["kind"] == "sentence"]
    assert sentences == [row["sentence"] for row in context.table], sentences


@then('"{phrase}" is reported at UTF-16 offsets {start:d} to {end:d}')
def step_reported_at(context, phrase, start, end):
    findings = _findings(context)
    assert [(f["excerpt"], f["span"]["start"], f["span"]["end"]) for f in findings] == [(phrase, start, end)], findings


@then('the check is refused and the message names "{name}"')
def step_refused(context, name):
    assert context.ml_error is not None, "the check was not refused"
    assert f"'{name}'" in str(context.ml_error), str(context.ml_error)


@then("no findings are returned as if the draft were clean")
def step_no_result(context):
    assert context.ml_results is None


@then('the result names the language pack "{tag}"')
def step_names_language(context, tag):
    assert all(r["language"]["tag"] == tag for r in context.ml_results), [r["language"] for r in context.ml_results]


@then("the findings are, by policy, excerpt and replacement:")
def step_findings_table(context):
    actual = [(f["policyId"], f["excerpt"].strip(), f.get("replacement")) for f in _findings(context)]
    expected = [(row["policy"], row["excerpt"], row["replacement"]) for row in context.table]
    assert actual == expected, actual


@then('applying the replacements gives "{text}"')
def step_applied(context, text):
    assert _apply(context.ml_text, _findings(context)) == text, _apply(context.ml_text, _findings(context))


@then('"{excerpt}" is reported with "{replacement}"')
def step_reported_with(context, excerpt, replacement):
    assert any(f["excerpt"].strip() == excerpt and f.get("replacement") == replacement for f in _findings(context)), _findings(context)


@then('the rules lane names "{detector}" as not run because "{reason}"')
def step_detector_not_run(context, detector, reason):
    not_run = [entry for r in context.ml_results for entry in r["lanes"]["rules"].get("notRun", [])]
    assert any(entry["detectorId"] == detector and reason in entry["reason"] for entry in not_run), not_run


@then('the rules lane names the policy as not run because "{reason}"')
def step_policy_not_run(context, reason):
    not_run = context.ml_results[0]["lanes"]["rules"].get("notRun", [])
    policy_id = context.ml_pack["policies"][0]["id"]
    assert any(entry["policyId"] == policy_id and reason in entry["reason"] for entry in not_run), not_run


@then("no typography finding is reported")
def step_no_typography(context):
    assert _findings(context) == [], _findings(context)


@then("no finding is reported")
def step_no_finding(context):
    assert _findings(context) == [], _findings(context)


@then('the paragraph is reported with the message containing "{text}"')
def step_message_containing(context, text):
    findings = _findings(context)
    assert len(findings) == 1 and text in findings[0]["message"], findings
    context.ml_message = findings[0]["message"]


@then('the message names the native rate "{text}"')
def step_native_rate(context, text):
    assert f"native writing averages {text}" in context.ml_message, context.ml_message


@then('exactly one finding is reported, with the excerpt "{excerpt}"')
def step_one_excerpt(context, excerpt):
    assert [f["excerpt"] for f in _findings(context)] == [excerpt], _findings(context)


@then('exactly one finding is reported, with the message "{message}"')
def step_one_message(context, message):
    assert [f["message"] for f in _findings(context)] == [message], _findings(context)


# --- regression and the design experiment ---------------------------------------------


@given("the English drafts in the regression suite")
def step_english_drafts(context):
    context.ml_golden = json.loads(GOLDEN.read_text(encoding="utf-8"))


@when("Humanus checks them with the English starter packs")
def step_check_english(context):
    context.ml_actual = {}
    for key in context.ml_golden:
        pack, path, fmt = key.split("|")
        text = (REPO_ROOT / path).read_text(encoding="utf-8")
        result = check({"schemaVersion": 1, "content": {"format": fmt, "language": "en", "text": text}, "pack": builtin_pack(pack)}, decision_model=None)
        context.ml_actual[key] = {
            "segments": [[s["id"], s["start"], s["end"]] for s in result["segments"]],
            "findings": [
                {k: f[k] for k in ("id", "policyId", "detectorId", "severity", "span", "excerpt", "message", "replacement") if k in f}
                for f in result["findings"]
            ],
        }


@then("every finding is the same as before the language layer")
def step_same_as_before(context):
    changed = [key for key in context.ml_golden if context.ml_golden[key] != context.ml_actual[key]]
    assert not changed, changed
    assert sum(len(v["findings"]) for v in context.ml_golden.values()) > 0


@given("the experiment drafts from the multilingual design")
def step_experiment_drafts(context):
    context.ml_experiment = {}


@when("each is checked in its language with its starter packs:")
def step_check_experiment(context):
    for row in context.table:
        text = (MULTILINGUAL / row["draft"]).read_text(encoding="utf-8")
        language = row["language"]
        document = segment_document(text, "markus", language=language)
        findings = [f for name in row["packs"].split(",") for f in _check(text, language, builtin_pack(name.strip()))["findings"]]
        context.ml_experiment[row["draft"]] = {
            "paragraphs": len(document.paragraphs),
            "sentences": len(document.sentences()),
            "findings": findings,
        }


@then("the drafts have these counts:")
def step_experiment_counts(context):
    for row in context.table:
        got = context.ml_experiment[row["draft"]]
        actual = (got["paragraphs"], got["sentences"], len(got["findings"]))
        assert actual == (int(row["paragraphs"]), int(row["sentences"]), int(row["findings"])), (row["draft"], actual)


@then('in "{draft}" each of these phrases is reported: {phrases}')
def step_experiment_phrases(context, draft, phrases):
    excerpts = [f["excerpt"] for f in context.ml_experiment[draft]["findings"]]
    missing = [p.strip() for p in phrases.split(",") if p.strip() not in excerpts]
    assert not missing, missing
