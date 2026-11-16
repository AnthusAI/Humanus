from __future__ import annotations

import sys
from pathlib import Path

from behave import given, then, when

SRC_ROOT = Path(__file__).resolve().parents[2] / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from humanus import UnsupportedLanguageError, diff, measure  # noqa: E402


def _measure(context, **extra):
    kwargs = {k: v for k, v in (("headline", getattr(context, "headline", None)), ("dek", getattr(context, "dek", None)), ("blurb", getattr(context, "blurb", None))) if v is not None}
    return measure(context.measure_text, context.measure_language, **kwargs, **extra)


@given('the language is "{tag}"')
def step_language(context, tag):
    context.measure_language = tag
    context.headline = context.dek = context.blurb = None
    context.measure_error = None


@given("the text to measure is:")
def step_text_block(context):
    context.measure_text = context.text


@given('the text to measure is "{text}"')
def step_text_inline(context, text):
    context.measure_text = text


@given("the text to measure is {count:d} repeated words")
def step_repeated(context, count):
    context.measure_text = " ".join(["word"] * count)


@given("the text to measure is empty")
def step_text_empty(context):
    context.measure_text = ""


@given("the dek is empty")
def step_dek_empty(context):
    context.dek = ""


@given('the headline is "{value}"')
def step_headline(context, value):
    context.headline = value


@given('the dek is "{value}"')
def step_dek(context, value):
    context.dek = value


@when("the text is measured")
def step_measured(context):
    context.measure_error = None
    try:
        context.measurement = _measure(context)
    except (UnsupportedLanguageError, NotImplementedError) as exc:
        context.measure_error = exc


@when("the text is measured twice")
def step_measured_twice(context):
    context.measurements = [_measure(context), _measure(context)]


@when("the text is measured with a concept list")
def step_measured_concepts(context):
    try:
        _measure(context, concepts=["cats"])
    except NotImplementedError as exc:
        context.measure_error = exc


@when('the change from nothing to "{new}" is measured')
def step_change_from_nothing(context, new):
    context.change = diff("", new, context.measure_language)


@when('the change from "{old}" to "{new}" is measured')
def step_change(context, old, new):
    context.change = diff(old, new, context.measure_language)


@then('the size unit is "{unit}"')
def step_unit(context, unit):
    assert context.measurement["size"]["unit"] == unit


@then("the size is {count:d} units")
def step_size(context, count):
    assert context.measurement["size"]["units"] == count, context.measurement["size"]


@then("the reading time is a positive number of minutes")
def step_reading_positive(context):
    assert context.measurement["size"]["readingMinutes"] > 0


@then("the reading time is {minutes:f} minutes")
def step_reading(context, minutes):
    assert context.measurement["size"]["readingMinutes"] == minutes, context.measurement["size"]


@then("the structure has {count:d} sections")
def step_sections(context, count):
    assert context.measurement["structure"]["sections"] == count


@then("the structure has {count:d} paragraphs")
def step_paragraphs(context, count):
    assert context.measurement["structure"]["paragraphs"] == count


@then("the longest paragraph is {count:d} units")
def step_longest_paragraph(context, count):
    assert context.measurement["structure"]["longestParagraph"] == count


@then("the longest sentence is {count:d} units")
def step_longest_sentence(context, count):
    assert context.measurement["structure"]["longestSentence"] == count


@then("the {name} is present with length {length:d}")
def step_present(context, name, length):
    assert context.measurement["structure"][name] == {"present": True, "length": length}


@then("the {name} is absent")
def step_absent(context, name):
    assert context.measurement["structure"][name]["present"] is False


@then("the {name} is not measured")
def step_not_measured(context, name):
    assert name not in context.measurement["structure"]


@then("there are {sources:d} sources in the text: {links:d} links and {citations:d} citations")
def step_sources(context, sources, links, citations):
    sourcing = context.measurement["sourcing"]
    assert (sourcing["sources"], sourcing["links"], sourcing["citations"]) == (sources, links, citations), sourcing


@then("the share of paragraphs without a source is {share:f}")
def step_share(context, share):
    assert abs(context.measurement["sourcing"]["shareParagraphsWithoutSource"] - share) < 0.00005, context.measurement["sourcing"]


@then("the sources per 500 units are close to {value:f}")
def step_per500(context, value):
    assert abs(context.measurement["sourcing"]["per500"] - value) < 0.05, context.measurement["sourcing"]


@then("the sources per 500 units are not defined")
def step_per500_none(context):
    assert context.measurement["sourcing"]["per500"] is None


@then("both measurements are identical")
def step_identical(context):
    assert context.measurements[0] == context.measurements[1]


@then('measuring is refused naming "{tag}"')
def step_refused(context, tag):
    assert isinstance(context.measure_error, UnsupportedLanguageError) and tag in str(context.measure_error)


@then("measuring is refused because concepts are not supported yet")
def step_refused_concepts(context):
    assert isinstance(context.measure_error, NotImplementedError)


@then("the change has {rewritten:d} rewritten, {added:d} added, {removed:d} removed and {unchanged:d} unchanged")
def step_change_counts(context, rewritten, added, removed, unchanged):
    c = context.change
    assert (c["rewritten"], c["added"], c["removed"], c["unchanged"]) == (rewritten, added, removed, unchanged), c


@then("the change share is {share:f}")
def step_change_share(context, share):
    assert context.change["shareChanged"] == share, context.change


@then('the change unit is "{unit}"')
def step_change_unit(context, unit):
    assert context.change["unit"] == unit


def _cli(context, *args):
    import json
    import subprocess
    import tempfile

    env = {"PYTHONPATH": str(SRC_ROOT), "PATH": "/usr/bin:/bin"}
    completed = subprocess.run([sys.executable, "-m", "humanus", *args], capture_output=True, text=True, env=env)
    context.cli_status = completed.returncode
    context.cli_output = json.loads(completed.stdout) if completed.returncode == 0 else None


@when("the text is measured on the command line")
def step_cli_measure(context):
    import tempfile

    with tempfile.TemporaryDirectory() as directory:
        draft = Path(directory) / "draft.md"
        draft.write_text(context.measure_text, encoding="utf-8")
        _cli(context, "measure", "--draft", str(draft), "--language", context.measure_language)


@when("two files are compared on the command line")
def step_cli_diff(context):
    import tempfile

    with tempfile.TemporaryDirectory() as directory:
        old, new = Path(directory) / "old.md", Path(directory) / "new.md"
        old.write_text("One two three.", encoding="utf-8")
        new.write_text("Four five six.", encoding="utf-8")
        _cli(context, "diff", "--old", str(old), "--new", str(new), "--language", context.measure_language)


@then("the command succeeds and prints a size of {count:d} units")
def step_cli_size(context, count):
    assert context.cli_status == 0 and context.cli_output["size"]["units"] == count


@then("the command succeeds and prints a share changed of {share:f}")
def step_cli_share(context, share):
    assert context.cli_status == 0 and context.cli_output["shareChanged"] == share
