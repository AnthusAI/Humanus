# Limatus

Limatus is a configurable editorial compliance engine. A publication sends its
own editorial policies with each request; Limatus marks every place a draft
breaks them, says how sure it is, and offers rewrites when an editor asks.

## Press Release

**Anthus AI Solutions introduces Limatus, an open-source engine that checks writing against a publication's own editorial policies — and only rewrites when an editor asks**

Every publication has rules: words it avoids, claims it will not make without a
source, a voice it keeps. Most are enforced by an editor's memory. Limatus makes
them executable. A CMS sends a draft and a *policy pack* — the publication's
policies, each written in plain words and backed by detectors — and Limatus
returns the draft annotated with every finding, down to the exact words.

Two kinds of detector do the finding. Rules catch what a pattern can: banned
phrases, house style, the tells of AI-generated prose. A decision model, TypeSafe
Jev, judges what a pattern cannot — "does this sentence make a claim without
saying who or how much?" — sentence by sentence, with a probability attached.
Rewrites come from a generative model only when an editor asks for them, for a
flagged passage or any passage they select, and they never add facts.

"We wanted editorial policy to be something you can read, test and change, not
something one editor carries in their head," said the Limatus team at Anthus AI
Solutions. Limatus runs inside Papyrus, Anthus's newsroom system, and is
available as an MIT-licensed Python package.

## FAQ

**Is Limatus an AI-content detector?** No. It checks text against policies you
define, whoever wrote it. The starter pack of AI-writing tells is a set of
editable policies like any other.

**Does it rewrite my content?** Only when asked, and never by itself: `suggest`
returns options for a finding or a selection, and a person chooses.

**Where do policies live?** In the caller. Limatus is stateless; the CMS stores
policies, settings and editors' decisions and sends a pack with every request.

## Installation

```bash
pip install limatus          # rules lane, contracts, suggest
pip install "limatus[jev]"   # adds the TypeSafe Jev classifier lane
```

Set `TYPESAFE_API_KEY` for the classifier lane and `OPENAI_API_KEY` for
rewrite suggestions and drafted questions (`gpt-6-luna` by default).

## Usage

```bash
limatus pack builtin ai-writing-tells > pack.json      # a starter pack to edit
limatus pack import --profile style-profile.yml > pack.json   # or convert a legacy style profile
limatus check --draft draft.md --pack pack.json        # findings, segments, lanes (check-result-v1)
limatus suggest --request suggest-request.json         # rewrite options for a finding or selection
limatus draft-questions --request draft-request.json   # classifier detectors for a prose policy
limatus calibrate --labels labels.json                 # calibration from editors' decisions
limatus schema policy-pack-v1                          # print any contract schema
```

```python
from limatus import check, suggest

result = check({"schemaVersion": 1, "content": {"format": "markus", "text": text}, "pack": pack})
for finding in result["findings"]:
    print(finding["severity"], finding["policyId"], finding["excerpt"], finding.get("probability"))
```

## Contracts

The payloads are JSON Schemas packaged with Limatus (`limatus schema <name>`);
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
can place findings. Front matter, code, Markus directives, block quotes, tables
and raw HTML are protected regions and never checked. Paragraph, sentence and
finding ids derive from text, so they survive edits elsewhere.

## Lanes

- **Rules** (deterministic): phrase and regex detectors run on prose only;
  built-in checks cover empty lead-ins, unsupported certainty, missing
  attribution, passive voice, redundancy, uniform cadence, information density,
  overused words, uncontracted forms, contrast caps and emoji. `limatus pack
  builtin ai-writing-tells` prints 24 starter policies adapted from
  [avoid-ai-writing](https://github.com/conorbronsdon/avoid-ai-writing) (MIT; see
  `limatus/packs/NOTICE.md`).
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
limatus usability scan --page page.html --profile usability-profile.yml
```

## For agents

`limatus skill` prints an Agent Skill describing the check → suggest → choose
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
