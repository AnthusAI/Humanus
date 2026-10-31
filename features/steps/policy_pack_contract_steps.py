from __future__ import annotations

import copy
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

from behave import given, then, when

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = REPO_ROOT / "src"
IMPORT_PROFILE = REPO_ROOT / "features" / "fixtures" / "policy-pack" / "style-profile.yml"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from humanus.check import CheckRequestValidationError, check  # noqa: E402
from humanus.contracts import validate_payload  # noqa: E402
from humanus.finding_ids import finding_id  # noqa: E402
from humanus.policy_pack import PolicyPackValidationError, load_policy_pack  # noqa: E402
from humanus.segmentation import segment_document  # noqa: E402
from humanus.style_profile_import import policy_pack_from_style_profile  # noqa: E402


def _base_pack() -> dict:
    return {
        "schemaVersion": 1,
        "packId": "example-publication",
        "version": "2026-10-19.1",
        "title": "Example publication policies",
        "policies": [
            {
                "id": "no-hype",
                "version": 3,
                "title": "No hype words",
                "guidance": "Describe what changed instead of calling it game-changing.",
                "severity": "warn",
                "detectors": [
                    {
                        "id": "hype-words",
                        "lane": "rules",
                        "kind": "phrase",
                        "phrases": ["game-changing", "revolutionary"],
                        "message": "Say what changed instead.",
                    }
                ],
            },
            {
                "id": "concrete-claims",
                "version": 1,
                "title": "Claims are concrete",
                "guidance": "Every claim names who, what, or how much.",
                "severity": "error",
                "detectors": [
                    {
                        "id": "vague-claim",
                        "lane": "classifier",
                        "scope": "sentence",
                        "question": {
                            "type": "noul",
                            "instructions": "Does the target sentence make a claim without saying who, what, or how much?",
                        },
                        "violation": {"answer": "yes"},
                        "threshold": 0.8,
                        "reviewAt": 0.5,
                    }
                ],
            },
        ],
    }


def _run_humanus(*args: str) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["PYTHONPATH"] = f"{SRC_ROOT}:{REPO_ROOT}"
    env.pop("OPENAI_API_KEY", None)
    env.pop("TYPESAFE_API_KEY", None)
    return subprocess.run(
        [sys.executable, "-m", "humanus", *args],
        cwd=REPO_ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )


# --- policy packs -----------------------------------------------------------


@given("a policy pack payload with a rules policy and a classifier policy")
def step_pack_rules_and_classifier(context):
    context.pack_payload = _base_pack()


@given("a policy pack payload with a guidance-only policy")
def step_pack_guidance_only(context):
    pack = _base_pack()
    pack["policies"].append(
        {
            "id": "plain-language",
            "version": 1,
            "title": "Plain language",
            "guidance": "Prefer ordinary words to jargon.",
            "severity": "info",
            "detectors": [],
        }
    )
    context.pack_payload = pack


@given("a policy pack payload whose classifier detector has no question")
def step_pack_classifier_without_question(context):
    pack = _base_pack()
    del pack["policies"][1]["detectors"][0]["question"]
    context.pack_payload = pack


@given('a policy pack payload with two policies named "{policy_id}"')
def step_pack_duplicate_ids(context, policy_id):
    pack = _base_pack()
    duplicate = copy.deepcopy(pack["policies"][0])
    duplicate["id"] = policy_id
    pack["policies"][0]["id"] = policy_id
    pack["policies"].append(duplicate)
    context.pack_payload = pack


@given('a policy pack payload with the regex pattern "{pattern}"')
def step_pack_bad_regex(context, pattern):
    pack = _base_pack()
    pack["policies"][0]["detectors"].append(
        {"id": "broken", "lane": "rules", "kind": "regex", "pattern": pattern}
    )
    context.pack_payload = pack


@when("the policy pack payload is loaded")
def step_load_pack(context):
    context.pack_error = None
    context.loaded_pack = None
    try:
        context.loaded_pack = load_policy_pack(context.pack_payload)
    except PolicyPackValidationError as exc:
        context.pack_error = exc


@then('the loaded pack has the policies "{first}" and "{second}"')
def step_pack_has_policies(context, first, second):
    assert context.pack_error is None, context.pack_error
    assert [p.id for p in context.loaded_pack.policies] == [first, second]


@then('policy "{policy_id}" has a "{lane}" detector of kind "{kind}"')
def step_policy_has_rules_detector(context, policy_id, lane, kind):
    policy = context.loaded_pack.policy(policy_id)
    assert [(d.lane, d.kind) for d in policy.detectors] == [(lane, kind)]


@then('policy "{policy_id}" has a "{lane}" detector with scope "{scope}"')
def step_policy_has_classifier_detector(context, policy_id, lane, scope):
    policy = context.loaded_pack.policy(policy_id)
    assert [(d.lane, d.scope) for d in policy.detectors] == [(lane, scope)]


@then("each loaded policy keeps its version and severity")
def step_policy_versions(context):
    assert [(p.version, p.severity) for p in context.loaded_pack.policies] == [(3, "warn"), (1, "error")]


@then('the loaded policy "{policy_id}" has no detectors')
def step_policy_no_detectors(context, policy_id):
    assert context.pack_error is None, context.pack_error
    assert context.loaded_pack.policy(policy_id).detectors == ()


@then("loading fails with a policy pack validation error")
def step_pack_fails(context):
    assert context.pack_error is not None, "expected a PolicyPackValidationError"


@then('the policy pack error names the location "{location}"')
def step_pack_error_location(context, location):
    assert context.pack_error.location == location, (context.pack_error.location, str(context.pack_error))


@then('the policy pack error mentions "{text}"')
def step_pack_error_mentions(context, text):
    assert text in str(context.pack_error), str(context.pack_error)


# --- CLI --------------------------------------------------------------------


@when('I run the humanus command "{command}"')
def step_run_humanus_command(context, command):
    context.cli = _run_humanus(*command.split())


@then("the command succeeds")
def step_command_succeeds(context):
    assert context.cli.returncode == 0, context.cli.stderr


@then('the command prints a JSON Schema whose id ends with "{suffix}"')
def step_command_prints_schema(context, suffix):
    schema = json.loads(context.cli.stdout)
    assert schema["$schema"].startswith("https://json-schema.org/"), schema.get("$schema")
    assert schema["$id"].endswith(suffix), schema["$id"]


@then('the command prints a valid "{schema_name}" document')
def step_command_prints_valid(context, schema_name):
    validate_payload(schema_name, json.loads(context.cli.stdout))


# --- style profile import -----------------------------------------------------


@given("a style profile fixture with checks and rules")
def step_import_profile_fixture(context):
    import yaml

    context.profile_path = IMPORT_PROFILE
    context.profile_raw = yaml.safe_load(IMPORT_PROFILE.read_text(encoding="utf-8"))


@when("the style profile is imported as a policy pack")
def step_import_profile(context):
    context.imported = policy_pack_from_style_profile(context.profile_path)


@then('the imported pack is a valid "{schema_name}" document')
def step_imported_valid(context, schema_name):
    validate_payload(schema_name, context.imported)
    load_policy_pack(context.imported)


@then("the imported pack id is the profile's publication key")
def step_imported_pack_id(context):
    assert context.imported["packId"] == context.profile_raw["publicationKey"]


def _detectors(pack: dict) -> list[dict]:
    return [d for p in pack["policies"] for d in p["detectors"]]


@then('the avoid lexicon becomes a policy with a "phrase" detector')
def step_imported_lexicon(context):
    avoid = context.profile_raw["lexicon"]["avoid"]
    phrase_lists = [d["phrases"] for d in _detectors(context.imported) if d.get("kind") == "phrase"]
    assert avoid in phrase_lists, phrase_lists


@then('each banned pattern becomes a "regex" detector that keeps its message')
def step_imported_regex(context):
    banned = context.profile_raw.get("rules", {}).get("bannedPatterns", [])
    assert banned, "fixture should have banned patterns"
    regexes = {(d["pattern"], d.get("message")) for d in _detectors(context.imported) if d.get("kind") == "regex"}
    for item in banned:
        assert (item["pattern"], item["message"]) in regexes, regexes


@then('each enabled check becomes a "builtin" detector')
def step_imported_builtins(context):
    checks = context.profile_raw.get("checks", {})
    builtins = {d["check"] for d in _detectors(context.imported) if d.get("kind") == "builtin"}
    disabled = {name for name, on in checks.items() if not on}
    assert builtins, "expected builtin detectors"
    assert not (builtins & {_snake(name) for name in disabled}), builtins


def _snake(name: str) -> str:
    return "".join("_" + c.lower() if c.isupper() else c for c in name)


@then("tone, sentence style and evidence rules become guidance-only policies")
def step_imported_guidance(context):
    guidance_only = [p for p in context.imported["policies"] if not p["detectors"]]
    texts = "\n".join(p["guidance"] for p in guidance_only)
    for key in ("tone", "sentenceStyle", "evidenceRules"):
        for line in context.profile_raw[key]:
            assert line in texts, line


@then("the reference samples are embedded with their text")
def step_imported_samples(context):
    samples = context.imported["referenceSamples"]
    assert len(samples) == len(context.profile_raw["referenceSamples"])
    assert all(s["text"].strip() for s in samples)


# --- segmentation -------------------------------------------------------------


@given("the Markus document:")
def step_markus_document(context):
    context.markus_text = context.text


@when("the document is segmented")
def step_segment(context):
    context.segmented = segment_document(context.markus_text)


def _paragraphs(context):
    return [s for s in context.segmented.segments if s.kind == "paragraph"]


def _sentences_of(context, paragraph_number: int):
    parent = _paragraphs(context)[paragraph_number - 1]
    return [s for s in context.segmented.segments if s.kind == "sentence" and s.parent_id == parent.id]


@then("the paragraph segments are:")
def step_paragraph_segments(context):
    actual = [(s.block, s.source) for s in _paragraphs(context)]
    expected = [(row["block"].strip(), row["source"].strip()) for row in context.table]
    assert actual == expected, actual


@then("the sentence segments of paragraph {number:d} are:")
def step_sentence_segments(context, number):
    actual = [s.source for s in _sentences_of(context, number)]
    expected = [row["source"].strip() for row in context.table]
    assert actual == expected, actual


@then("every segment's offsets select its source from the document")
def step_offsets_select_source(context):
    text = context.segmented.text
    for segment in context.segmented.segments:
        assert text[segment.start : segment.end] == segment.source, segment


@then('the front matter is a protected "{kind}" region')
def step_front_matter_protected(context, kind):
    first = context.segmented.protected[0]
    assert first.kind == kind and first.start == 0, first


@then('the protected regions are "{kinds}"')
def step_protected_kinds(context, kinds):
    expected = [k.strip() for k in kinds.split(",")]
    assert [r.kind for r in context.segmented.protected] == expected, context.segmented.protected


@then("no segment overlaps a protected region")
def step_no_overlap(context):
    for segment in context.segmented.segments:
        if segment.kind == "document":
            continue
        for region in context.segmented.protected:
            assert segment.end <= region.start or segment.start >= region.end, (segment, region)


@then('the plain text of sentence {number:d} is "{plain}"')
def step_plain_text(context, number, plain):
    assert _sentences_of(context, 1)[number - 1].text == plain


@then("there are {count:d} paragraph segments")
def step_paragraph_count(context, count):
    assert len(_paragraphs(context)) == count


@then("paragraph {a:d} and paragraph {b:d} have different ids and different offsets")
def step_distinct_repeats(context, a, b):
    first, second = _paragraphs(context)[a - 1], _paragraphs(context)[b - 1]
    assert first.source == second.source
    assert first.id != second.id
    assert first.start != second.start


@when("the second paragraph is rewritten and the document is segmented again")
def step_rewrite_second(context):
    context.before = context.segmented
    edited = context.markus_text.replace("Edited paragraph.", "A completely different second paragraph. With two sentences.")
    context.segmented = segment_document(edited)


@then("the first paragraph and its sentences keep their ids")
def step_ids_survive(context):
    def first_ids(doc):
        paragraph = [s for s in doc.segments if s.kind == "paragraph"][0]
        return [paragraph.id] + [s.id for s in doc.segments if s.parent_id == paragraph.id]

    assert first_ids(context.before) == first_ids(context.segmented)


# --- check ------------------------------------------------------------------------

EMOJI_DOCUMENT = "# Launch 🚀\n\nWe shipped it. The 🎉 team celebrated.\n\nNext steps follow.\n"


def _check_request(text: str) -> dict:
    return {"schemaVersion": 1, "content": {"format": "markus", "text": text}, "pack": _base_pack()}


@given("a check request for a Markus document with an emoji before its prose")
def step_check_request_emoji(context):
    context.check_request = _check_request(EMOJI_DOCUMENT)


@given("a check request without content")
def step_check_request_no_content(context):
    request = _check_request(EMOJI_DOCUMENT)
    del request["content"]
    context.check_request = request


@when("Humanus checks the request")
def step_run_check(context):
    context.check_error = None
    context.check_result = None
    try:
        context.check_result = check(context.check_request)
    except CheckRequestValidationError as exc:
        context.check_error = exc


@then('the check result is a valid "{schema_name}" document')
def step_check_result_valid(context, schema_name):
    assert context.check_error is None, context.check_error
    validate_payload(schema_name, context.check_result)


@then('the check result reports offsets in "{unit}" code units')
def step_offset_unit(context, unit):
    assert context.check_result["offsetUnit"] == unit


@then("every result segment's UTF-16 span selects its text as JavaScript would")
def step_utf16_spans(context):
    text = context.check_request["content"]["text"]
    utf16 = text.encode("utf-16-le")
    segmented = {s.id: s for s in segment_document(text).segments}
    for segment in context.check_result["segments"]:
        selected = utf16[segment["start"] * 2 : segment["end"] * 2].decode("utf-16-le")
        assert selected == segmented[segment["id"]].source, (segment, selected)
    assert context.check_result["document"]["length"] == len(utf16) // 2


@then("the check result names the policy pack id and version")
def step_pack_named(context):
    assert context.check_result["pack"] == {"packId": "example-publication", "version": "2026-10-19.1"}


@then("the check result includes one document segment and its paragraph and sentence segments")
def step_segment_kinds(context):
    kinds = [s["kind"] for s in context.check_result["segments"]]
    assert kinds.count("document") == 1
    assert kinds.count("paragraph") == 3
    assert kinds.count("sentence") == 4


@then("every lane reports a status")
def step_lane_status(context):
    lanes = context.check_result["lanes"]
    assert set(lanes) == {"rules", "classifier"}
    assert all(lane["status"] for lane in lanes.values())


@then("checking fails with a check request validation error")
def step_check_fails(context):
    assert context.check_error is not None, "expected a CheckRequestValidationError"


@then('the check request error names the location "{location}"')
def step_check_error_location(context, location):
    assert location in context.check_error.location or location in str(context.check_error), str(context.check_error)


@given("a check request file for a Markus document")
def step_check_request_file(context):
    handle = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8")
    json.dump(_check_request(EMOJI_DOCUMENT), handle)
    handle.close()
    context.check_request_path = handle.name


@when('I run the humanus command "check --request" with the request file')
def step_run_check_cli(context):
    context.cli = _run_humanus("check", "--request", context.check_request_path)


# --- finding ids --------------------------------------------------------------------


@given('a finding for policy "{policy_id}" on "{excerpt}" in the sentence "{sentence}"')
def step_finding(context, policy_id, excerpt, sentence):
    context.finding = {"policy_id": policy_id, "detector_id": "hype-words", "excerpt": excerpt}
    context.finding_sentence = sentence
    context.first_id = finding_id(segment_text=sentence, **context.finding)


@when("another sentence in the same paragraph is edited and the finding is identified again")
def step_edit_other_sentence(context):
    context.second_id = finding_id(segment_text=context.finding_sentence, **context.finding)


@when('the sentence becomes "{sentence}" and the finding is identified again')
def step_edit_same_sentence(context, sentence):
    context.second_id = finding_id(segment_text=sentence, **context.finding)


@when("both occurrences of the excerpt are identified")
def step_both_occurrences(context):
    context.first_id = finding_id(segment_text=context.finding_sentence, occurrence=0, **context.finding)
    context.second_id = finding_id(segment_text=context.finding_sentence, occurrence=1, **context.finding)


@then("the finding id is unchanged")
def step_id_unchanged(context):
    assert context.first_id == context.second_id


@then("the finding id changes")
def step_id_changes(context):
    assert context.first_id != context.second_id


@then("the two finding ids differ")
def step_ids_differ(context):
    assert context.first_id != context.second_id


@given('a check request whose pack flags "{phrase}" in:')
def step_request_flagging(context, phrase):
    pack = _base_pack()
    pack["policies"][0]["detectors"][0]["phrases"] = [phrase]
    context.check_request = {"schemaVersion": 1, "content": {"format": "markus", "text": context.text}, "pack": pack}


@then('the paragraph and sentence segments carry the plain text "{text}"')
def step_segments_plain(context, text):
    prose = [s for s in context.check_result["segments"] if s["kind"] in {"paragraph", "sentence"}]
    assert prose and all(s.get("text") == text for s in prose), prose


@then('the finding\'s excerpt text is "{text}"')
def step_excerpt_text(context, text):
    assert [f.get("excerptText") for f in context.check_result["findings"]] == [text], context.check_result["findings"]


@then("the document has no protected regions")
def step_no_protected(context):
    assert context.segmented.protected == (), context.segmented.protected
