# Humanus

Humanus is a configurable editorial compliance engine. A publication sends its
own editorial policies with each request; Humanus marks every place a draft
breaks them, says how sure it is, and offers rewrites when an editor asks.

Humanus was called Limatus until version 0.33. `pip install limatus` still
works: it installs Humanus and keeps `import limatus` and the `limatus` command
working with a deprecation warning.

## Press Release

**Anthus AI Solutions introduces Humanus, an open-source engine that checks writing against a publication's own editorial policies — and only rewrites when an editor asks**

Every publication has rules: words it avoids, claims it will not make without a
source, a voice it keeps. Most are enforced by an editor's memory. Humanus makes
them executable. A CMS sends a draft and a *policy pack* — the publication's
policies, each written in plain words and backed by detectors — and Humanus
returns the draft annotated with every finding, down to the exact words.

Two kinds of detector do the finding. Rules catch what a pattern can: banned
phrases, house style, the tells of AI-generated prose. A decision model, TypeSafe
Jev, judges what a pattern cannot — "does this sentence make a claim without
saying who or how much?" — sentence by sentence, with a probability attached.
Rewrites come from a generative model only when an editor asks for them, for a
flagged passage or any passage they select, and they never add facts.

"We wanted editorial policy to be something you can read, test and change, not
something one editor carries in their head," said the Humanus team at Anthus AI
Solutions. Humanus runs inside Papyrus, Anthus's newsroom system, and is
available as an MIT-licensed Python package.

## FAQ

**Is Humanus an AI-content detector?** No. It checks text against policies you
define, whoever wrote it. The starter pack of AI-writing tells is a set of
editable policies like any other.

**Can it enforce a published standard?** Yes. Starter packs implement ASD-STE100
Simplified Technical English (`asd-ste100`) and the Federal Plain Language
Guidelines (`plain-language`); copy one and adjust its limits and word lists.

**Does it rewrite my content?** Only when asked, and never by itself: `suggest`
returns options for a finding or a selection, and a person chooses.

**Where do policies live?** In the caller. Humanus is stateless; the CMS stores
policies, settings and editors' decisions and sends a pack with every request.

## Installation

```bash
pip install humanus          # rules lane, contracts, suggest
pip install "humanus[jev]"   # adds the TypeSafe Jev classifier lane
```

Set `TYPESAFE_API_KEY` for the classifier lane and `OPENAI_API_KEY` for
rewrite suggestions and drafted questions (`gpt-6-luna` by default).

## Usage

```bash
humanus pack builtin ai-writing-tells > pack.json      # a starter pack to edit
humanus pack import --profile style-profile.yml > pack.json   # or convert a legacy style profile
humanus check --draft draft.md --pack pack.json        # findings, segments, lanes (check-result-v1)
humanus suggest --request suggest-request.json         # rewrite options for a finding or selection
humanus draft-questions --request draft-request.json   # classifier detectors for a prose policy
humanus calibrate --labels labels.json                 # calibration from editors' decisions
humanus schema policy-pack-v1                          # print any contract schema
```

```python
from humanus import check, suggest

result = check({"schemaVersion": 1, "content": {"format": "markus", "text": text}, "pack": pack})
for finding in result["findings"]:
    print(finding["severity"], finding["policyId"], finding["excerpt"], finding.get("probability"))
```

## Contracts

The payloads are JSON Schemas packaged with Humanus (`humanus schema <name>`);
callers in any language validate against the same files.

| Schema | Purpose |
| --- | --- |
| `policy-pack-v1` | Policies: prose guidance, severity (`info`/`warn`/`error`), examples, rewrite guidance and detectors — `rules` (`regex`, `phrase`, `builtin`) or `classifier` (a zero-shot question at sentence, paragraph or document scope, with threshold, review band and optional calibration) |
| `check-request-v1` / `check-result-v1` | Content (`markus`, `markdown` or `text`) plus a pack in; segments, protected regions, findings, coverage and lane status out |
| `finding-v1` | One located problem, with an id that is stable across rescans |
| `suggest-request-v1` / `suggest-result-v1` | Rewrite options for a finding (rewritten as its sentence) or an editor's selection |
| `draft-questions-request-v1` / `draft-questions-result-v1` | Classifier detectors drafted from a prose policy |
| `feedback-labels-v1` / `calibration-v1` | Editors' decisions in, per-detector calibration out |

**Offsets** count UTF-16 code units, as JavaScript string indexes do.
**Segments** are the document, its prose paragraphs (paragraphs, headings, list
items) and their sentences; each carries its plain text so a rendered preview
can place findings. Front matter, code, Markus directives, block quotes and raw
HTML are protected regions and never checked. Table cells are prose: each cell
that has words in it is a paragraph segment with block `tableCell`, split into
sentences like any other paragraph, so both lanes read it and findings point at
the cell text; pipes and the alignment row stay out of detection, and cells that
hold only numbers or code are skipped. Set `options.tables` to `false` to make
tables a protected region again. Whole-document measures (average sentence
length, reading grade, information density, paragraph length, uniform cadence,
overused words) leave table cells out. Paragraph, sentence and
finding ids derive from text, so they survive edits elsewhere.

## Lanes

- **Rules** (deterministic): phrase and regex detectors run on prose only;
  built-in checks cover empty lead-ins, unsupported certainty, missing
  attribution, passive voice, redundancy, uniform cadence, information density,
  overused words, uncontracted forms, contrast caps and emoji. Checks for writing
  standards cover sentence length (by procedure or description), average
  sentence length, paragraph length, Flesch-Kincaid grade, double negatives,
  undefined acronyms, one instruction per step, imperative steps, -ing forms,
  missing articles and one meaning per word. Phrase detectors take `exceptions`,
  such as technical names, inside which a match is not a finding.
- **Starter packs** (`humanus pack builtin <name>`):
  - `ai-writing-tells`: 24 policies adapted from
    [avoid-ai-writing](https://github.com/conorbronsdon/avoid-ai-writing) (MIT).
  - `asd-ste100`: ASD-STE100 Simplified Technical English. The official
    dictionary is licensed by ASD, so the pack ships a small seed of
    unapproved words, nouns and one-meaning words; extend them with yours.
  - `plain-language`: the Federal Plain Language Guidelines (public domain),
    with simple-word and excess-word replacements, "must" for "shall", hidden
    verbs, length and readability limits, and Jev questions for addressing the
    reader as "you", putting the main point first and avoiding jargon.

  See `humanus/packs/NOTICE.md` for sources and licenses.
- **Classifier** (TypeSafe Jev, zero-shot): one request per segment carries
  every question that applies to it; sentences are judged with their paragraph
  as context. Answers are cached by content, so a rescan only asks about changed
  text. `options.classifier` sets the model, concurrency, an input-token budget,
  a deadline (to stay inside an API timeout) and few-shot examples from past
  decisions. Without a decision model the lane reports `unavailable` and rules
  findings are still returned.

Editors' decisions improve the classifier: `calibrate` fits Platt scaling (from
10 labels) or isotonic regression (from 50) per detector; store it on the
detector as `calibration` and thresholds apply to the calibrated probability.

## HTML usability

A separate, read-only scan for rendered HTML pages (contrast, tap targets, focus
visibility, alt text, generic AI-page patterns):

```bash
humanus usability scan --page page.html --profile usability-profile.yml
```

## For agents

`humanus skill` prints an Agent Skill describing the check → suggest → choose
workflow.

## Testing

Specifications are Gherkin, run with [Behave](https://behave.readthedocs.io/);
unit tests use pytest. Neither needs network access or API keys.

```bash
behave
python -m pytest tests -q
```

## License

MIT — see [LICENSE](LICENSE).
