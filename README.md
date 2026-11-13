# Humanus

Humanus is a configurable editorial compliance engine. A publication sends its
own editorial policies with each request; Humanus marks every place a draft
breaks them, says how sure it is, and offers rewrites when an editor asks.

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
humanus check --draft draft.md --pack pack.json --language en   # findings, segments, lanes (check-result-v1)
humanus pack builtin translation-faithfulness > faithful.json
humanus check --draft es.md --language es-419 --source en.md --source-language en --pack faithful.json   # a translation against its source
humanus suggest --request suggest-request.json         # rewrite options for a finding or selection
humanus draft-questions --request draft-request.json   # classifier detectors for a prose policy
humanus calibrate --labels labels.json                 # calibration from editors' decisions
humanus schema policy-pack-v1                          # print any contract schema
```

```python
from humanus import check, suggest

result = check({"schemaVersion": 1, "content": {"format": "markus", "language": "en", "text": text}, "pack": pack})
for finding in result["findings"]:
    print(finding["severity"], finding["policyId"], finding["excerpt"], finding.get("probability"))
```

## Contracts

The payloads are JSON Schemas packaged with Humanus (`humanus schema <name>`);
callers in any language validate against the same files.

| Schema | Purpose |
| --- | --- |
| `policy-pack-v1` | Policies: prose guidance, severity (`info`/`warn`/`error`), examples, rewrite guidance and detectors — `rules` (`regex`, `phrase`, `builtin`) or `classifier` (a zero-shot question at sentence, paragraph or document scope, with threshold, review band and optional calibration) |
| `check-request-v1` / `check-result-v1` | Content (`markus`, `markdown` or `text`, with its `language`) plus a pack in, and for a translation its `source` and an optional `glossary`; the language pack used, segments, protected regions, findings, coverage and lane status out |
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

## Languages

Every check request states the language of its content (`content.language`, a
BCP 47 tag) and every policy pack states the language its policies are written
for (`language`, or `"*"` for language-neutral policies). Humanus reads the text
with that language's **language pack** (`src/humanus/languages/*.yml`): where
sentences end (Chinese `。！？` with no space or capital after them; Spanish
`¿…?` and `¡…!`), what a unit of length is (words, or characters in Chinese),
how a phrase matches (on word boundaries, or anywhere in a script written
without spaces), which quotation marks enclose someone else's words, which
built-in checks the language can run, its word classes, its native baseline
rates and its typography data. Shipped: `en`, `es`, `es-419` (an overlay on
`es`: only what differs, such as quotation marks and number forms) and
`zh-Hans` (also served for `zh-CN`, `zh-SG`, `zh-MY`).

- A language with no pack is **refused** with an error that names it; text is
  never checked as if it were English. Tags match exactly (or a documented
  alias): `es-AR` is refused, not read as `es`.
- A pack written for another language is refused: English policies never run
  on Chinese text. A pack for a base language (`es`) applies to its variants
  (`es-419`); a pack for one variant never applies to another.
- A rules detector the language cannot run (an English built-in on Chinese, a
  word class needing a tagger the pack lacks) is listed in
  `lanes.rules.notRun` with the reason.

Generic built-ins take everything from the language pack: `frame` (ordered
parts with a bounded gap in one sentence, such as `不是 … 而是`), `density` (a
word class per paragraph against the pack's native rate, reported when the
count would be improbable at that rate) and `typography` (a named mechanical
rule: `punctuation-width`, `quotation-marks`, `ellipsis`,
`space-beside-full-width`, `latin-spacing`, `number-words`, `number-format`).
Length checks count in the language's unit.

## Translations: source against target

A check request may carry the text the content was translated from:
`source` (`text`, `format`, `language`, each required) and, optionally, a
`glossary` for the content's language. The pack's **parity** detectors then
compare the two texts by code and its **judge** detectors ask a bilingual
model judge about each block. Their findings carry `category: "faithfulness"`,
a `span` in the translation and a `source.span` in the source, and a
`replacement` when the repair is certain. In the design, a faithfulness finding
at `error` holds publication; monolingual findings never do.

```python
result = check({
    "schemaVersion": 1,
    "content": {"format": "markus", "language": "zh-Hans", "text": translation},
    "source": {"format": "markus", "language": "en", "text": english},
    "glossary": {"language": "zh-Hans", "entries": [
        {"term": "disclosure", "translations": ["披露"]},
        {"term": "ETH Zurich", "translations": ["苏黎世联邦理工学院"]},
        {"term": "Hugging Face", "doNotTranslate": True},
    ]},
    "pack": builtin_pack("translation-faithfulness"),
}, bilingual_judge=my_judge)   # optional; Humanus calls no model itself
```

The `translation-faithfulness` starter pack (language `"*"`) holds one policy
per check:

| Parity check | What must match |
| --- | --- |
| `structure` | The same blocks in the same order: paragraphs, headings by level, list items, table cells, block quotes, code, directives |
| `links`, `citations`, `code` | Link and image targets, citation keys, inline code, code blocks and raw HTML, byte for byte |
| `directives` | Directive names and attributes; only the attributes in `params.translatable` (the pack lists `alt`, `caption`, `title`) and a `[label]` may change, so a translated `credit` is restored |
| `numbers` | Every value, read with each language pack's number forms, words, scales and months: `50 million` = `5000 万`, `December 2025` = `2025 年 12 月`, `1,200` = `1.200`. A changed value names both sides and offers the source's value in the target's form |
| `iso_dates` | A `YYYY-MM-DD` date (a byline) kept as written (`warn`) |
| `names` | Names (capitalized words, acronyms, `OpenAI`, `GPT-6`) unchanged unless the glossary approves a local form |
| `glossary` | Each glossary term in an approved form; a do-not-translate term unchanged |
| `quotations` | No quoted passage lost (more quotation marks is a convention, not a defect) |
| `emphasis` | Emphasis that renders in the source renders in the translation; a closer stuck to the next word gets a space, or a full-width mark moves outside it |
| `hedges`, `attributions` | Per block, no fewer hedges or attributions and no added certainty, by each language pack's word lists (`warn` until measured) |
| `sentence_count` | A block with fewer sentences than its source is pointed out (`info`) |

Block-by-block checks need the blocks to line up. When they do not, the
`structure` finding says where they part and each block-by-block check is
listed in `lanes.parity.notRun` with that reason. The **judge** lane builds a
prompt per block (`humanus.bilingual_judge.judge_prompt`: system and user
messages and the JSON Schema of the answer), asks the caller's judge
`passes` times, checks that every quote is in the text it quotes (`rejected`
counts the ones that are not) and reports a problem every pass found as a
violation and one only some passes found for review. Without a judge the lane
reports `unavailable`. Back-translation is not an input to any check.

A request missing either language, a source in a language with no pack, a
glossary for another language, a faithfulness pack without a source and a
source with nothing to compare it are all refused.

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
  Direct quotations are someone else's words: a rules finding that lies
  entirely inside a double-quoted passage (straight or curly) or a block quote
  is not reported. A detector or its policy sets `quotations: "check"` to opt
  back in (the detector wins); the starter pack does so for placeholder leaks,
  chatbot artifacts, chat citation markup and AI-tool tracking parameters.
  `passive_voice` also ignores a passive clause inside a quotation when the
  rest of the sentence is not passive. The classifier lane still reads quotations.
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
  - `typography-zh-hans`, `typography-es`: mechanical punctuation, quotation
    mark and number-form rules, each finding with its deterministic replacement.
  - `ai-writing-tells-zh-hans`, `translationese-zh-hans`, `ai-writing-tells-es`:
    small advisory starter sets (all `info`), each policy marked with its
    `evidence` grade (`measured`, `normative` or `folk`).
  - `word-choice-es-419`: Latin American word choice (computadora, falla).
  - `translation-faithfulness`: source-against-translation checks (see above).

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
