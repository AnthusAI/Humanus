# Limatus

Limatus is a diagnose-and-steer quality loop for AI-generated content — prose today, web pages soon — built to catch generic AI slop and enforce a specific publication or product's own style rules, not just generic patterns.

## Press Release

**Anthus AI Solutions introduces Limatus, an open-source tool that tells writers exactly where AI-generated prose sounds generic — without rewriting it for them**

Teams publishing AI-assisted content face a recurring problem: drafts that are technically correct but sound like every other AI-generated draft — hedge words, empty lead-ins, uniform sentence cadence, unsupported certainty, and a voice that matches no one's actual house style. Fixing this by hand doesn't scale, and letting a model "just rewrite it" trades one set of generic patterns for another.

Limatus is a command-line tool that closes this gap in two separate steps. `limatus diagnose` reads a draft against a publication's own style profile — its voice, its lexicon, its banned phrases and patterns — and returns a structured list of findings: vague claims, empty lead-ins, uniform cadence, list-shaped prose, unsupported certainty, redundancy, and voice mismatches. It never rewrites anything; findings are signal, not verdicts. A human or agent then marks each finding skip, rewrite, delete, or keep, and only for the findings marked "rewrite" does `limatus options` generate a small set of constrained rewrite candidates — never a single mandated replacement, and never a fabricated fact, statistic, or anecdote.

"We built this because we were publishing AI-assisted content ourselves and got tired of the same tells showing up in every draft," said the Limatus team at Anthus AI Solutions. "The insight wasn't that AI writing is bad — it's that treating every publication's voice as the same generic 'professional tone' is what makes it read as AI-generated. Limatus makes house style an explicit, versioned, machine-checkable artifact instead of something an editor has to remember and enforce by hand every time."

Limatus is extracted from the editorial engine Anthus AI Solutions built and ran across dozens of real articles on its own Anth.us and Pilobolus publications, and is available today as an MIT-licensed, publication-agnostic Python package at [github.com/AnthusAI/Limatus](https://github.com/AnthusAI/Limatus).

## FAQ

**Is Limatus an AI-content detector?**
No. Limatus doesn't try to guess whether text was written by a model — it checks text against a style profile you define, regardless of who or what wrote it. It deliberately refuses to accept "detector scores" as part of a style profile; the goal is to enforce your voice, not to pass someone else's AI-detection heuristic.

**Does Limatus rewrite my content for me?**
Not automatically, and not without a human or agent explicitly opting each finding in. `limatus diagnose` only reports findings — it never touches the draft file. `limatus options` only generates rewrite *candidates* for findings you've separately marked "rewrite," and always offers more than one option so the choice of which to accept stays with an editor.

**What does a "style profile" look like?**
A YAML file naming a publication's voice, audience, tone, sentence style, structure, a preferred/avoided lexicon, evidence rules, and five to ten reference samples of real approved prose. It's the same profile used to catch drift, so it's meant to be version-controlled alongside the content it governs.

**Why is this a separate package from Papyrus?**
Papyrus is Anthus AI Solutions' own content and newsroom system, tightly coupled to Anth.us's publishing pipeline. Limatus is the general-purpose diagnose engine underneath it, extracted so any publication or product — not just Anthus's own — can adopt it without adopting the rest of Papyrus.

**What's next?**
A second capability is planned: a usability and accessibility diagnose loop for AI-generated web pages, built on Playwright and axe-core, checking WCAG 2.2 A/AA compliance across themes, viewports, and interactive states — the same diagnose-first, never-auto-fix philosophy applied to markup instead of prose.

**Is it on PyPI yet?**
Not yet — see Status below.

## Status

This package was newly extracted from Anth.us's Papyrus content system and is under active development. It is not yet on PyPI.

## Installation

```bash
pip install -e ".[dev]"
```

(PyPI installation via `pip install limatus` will be available once the package is published — see Status above.)

## Usage

```bash
limatus scan --draft path/to/draft.md --profile path/to/style-profile.yml
limatus decide --finding-id finding-0123456789abcdef --decision rewrite \
  --note "needs concrete options" --decisions path/to/decisions.json
limatus options --draft path/to/draft.md --profile path/to/style-profile.yml \
  --diagnosis path/to/diagnosis.json --decisions path/to/decisions.json \
  --skill path/to/rewrite-skill.yml
limatus compare --profile path/to/style-profile.yml --baseline path/to/draft.md \
  --candidate path/to/candidate-a.md --candidate path/to/candidate-b.md
limatus apply --original path/to/original.md --working-copy path/to/working.md \
  --options path/to/options.json --finding-id finding-... --option-id option-... \
  --anchor "exact span text"
limatus headline options --job title --working-copy path/to/working.md \
  --profile path/to/style-profile.yml --skill path/to/rewrite-skill.yml
limatus headline options --job subtitle --working-copy path/to/working.md \
  --profile path/to/style-profile.yml --skill path/to/rewrite-skill.yml
limatus eval --manifest features/fixtures/editorial-diagnosis/editorial-corpus/manifest.yml
limatus canary --manifest features/fixtures/editorial-canary/manifest.yml
```

From Python, the same read-only diagnose step is available without touching the draft file:

```python
from limatus import load_config, diagnose

config = load_config("path/to/style-profile.yml")
result = diagnose(open("draft.md").read(), config=config)
```

`diagnose` returns structured findings only; it does not modify the draft.

For a copy-editing agent, the intended loop is: **scan** (findings only, no steering decisions) → record **decisions** (`skip` / `rewrite` / `delete` / `keep` / `add`, via SDK or a decisions JSON file) → **options** for rewrite findings only → **compare** full-draft previews of each patch option (or regression compare after a trial edit) → **apply** exactly one human-chosen option to a working copy. When the style profile defines a `headline` pass (`when: afterBody`), run **headline** options for `title` then `subtitle` on the working copy after body edits are applied — each pass replaces only that YAML field. Nothing auto-applies a compare winner.

Run `limatus --help` for the full command reference.

### Advisory revision verification

After a human explicitly applies a selected option to a separate working copy,
`limatus verify` compares the original and working drafts without changing,
publishing, or automatically applying either one. It reports four quality
dimensions (specificity, clarity, audience fit, and voice match), penalties for
redundancy, unsupported claims, and factual-change risk, plus evidence-backed
findings for deleted claims, duplicated ideas, residual boilerplate, and new
unsupported or factual claims.

The result includes inspectable weights: each positive quality dimension is
weighted `0.25`; redundancy is `-0.10`; unsupported claims and factual-change
risk are each `-0.20`. The default acceptance threshold is `0.05` normalized
net improvement. The recommendation is advisory and is `accept` only when
the threshold is met and the working draft has no more unsupported claims than
the original. No detector score is accepted as input or emitted in output.

## Policy packs and `check`

Limatus is becoming a configurable editorial compliance engine: the caller
(for example a CMS) sends its editorial policies as a **policy pack** with each
request, and `check` returns the document as **standoff annotation** —
segments, protected regions and findings with offsets into the submitted text.
The contracts are JSON Schemas packaged with Limatus:

| Schema | Purpose |
| --- | --- |
| `policy-pack-v1` | Policies, each with prose guidance, severity (`info`/`warn`/`error`) and detectors (`rules` lane: `regex`, `phrase`, `builtin`; `classifier` lane: a zero-shot question at sentence, paragraph or document scope) |
| `check-request-v1` / `check-result-v1` | Content (`markus`, `markdown` or `text`) plus a pack in; segments, protected regions, findings, coverage and lane status out |
| `finding-v1` | One located problem, with an id that is stable across rescans |
| `suggest-request-v1` / `suggest-result-v1` | Rewrite options for one finding |

```bash
limatus schema policy-pack-v1                 # print a contract schema
limatus pack import --profile style-profile.yml > pack.json
limatus pack validate pack.json
limatus check --draft draft.md --pack pack.json
```

```python
from limatus import check

result = check({"schemaVersion": 1, "content": {"format": "markus", "text": text}, "pack": pack})
```

Result offsets count **UTF-16 code units**, as JavaScript string indexes do.
Front matter, code, Markus directives, block quotes, tables and raw HTML are
protected regions, never prose. Paragraph and sentence ids derive from their
text, so they survive edits elsewhere in the document.

Two lanes find problems:

- **Rules** (deterministic): `phrase`, `regex` and `builtin` detectors run on
  prose only. `limatus pack builtin ai-writing-tells` prints a starter pack of
  24 policies adapted from [avoid-ai-writing](https://github.com/conorbronsdon/avoid-ai-writing)
  (MIT; see `limatus/packs/NOTICE.md`) for a CMS to copy and edit.
- **Classifier** (TypeSafe Jev, zero-shot): install `limatus[jev]` and set
  `TYPESAFE_API_KEY`. Each sentence, paragraph or document segment costs one
  request carrying every question that applies to it; answers are cached by
  content, so a rescan after an edit only asks about changed text. Findings
  carry the model's probability; those between `reviewAt` and `threshold`
  have status `review`. `options.classifier.maxInputTokens` caps spend. If no
  decision model is configured the lane reports `unavailable` and rules
  findings are still returned.

Generative help never finds problems; it only helps an editor fix them
(OpenAI `gpt-6-luna` by default, via `OPENAI_API_KEY`):

- `suggest` (`limatus suggest --request`) returns up to three rewrite options
  for a finding — rewritten as its whole sentence — or for any span the editor
  selects, with an optional editor note. Options that change nothing, aim at
  evading AI detection, or still break the triggering rule are dropped and
  reported.
- `draft_questions` (`limatus draft-questions --request`) turns a policy written
  in prose into proposed classifier detectors for an editor to review.

Editors' decisions make the classifier better:

- `calibrate` (`limatus calibrate --labels`) fits a per-detector calibration
  from accepted/fixed (violates) and dismissed (does not) findings — Platt
  scaling from 10 labels, isotonic from 50. Store it on the detector as
  `calibration`; thresholds then apply to the calibrated probability and
  findings also report `rawProbability` (use that one in new labels).
- `options.classifier.examples` passes past decisions with their text; the most
  similar ones travel with each question as few-shot examples.

## Portable style profiles

A profile is a versioned YAML or JSON document. The profile below is complete:
required fields describe the publication voice and evidence policy, while
`checks`, `rules`, and `density` make the optional controls explicit.

```yaml
schemaVersion: 1
publicationKey: example-publication
voice:
  name: Practical engineering voice
audience: Engineers evaluating tools and operational risk.
tone:
  - Conversational but precise.
sentenceStyle:
  - Prefer active voice and concrete nouns.
voicePatterns:
  - Lead with the practical stake.
structure:
  - State the claim, then its evidence and limits.
lexicon:
  prefer: [inspect, verify, latency]
  avoid: [game-changing, leverage synergies]
evidenceRules:
  - Cite primary sources and label uncertainty.
referenceSamples:
  - id: sample-one
    title: Approved sample one
    url: https://example.com/articles/one
    path: reference-samples/sample-one.md
  - id: sample-two
    title: Approved sample two
    url: https://example.com/articles/two
    path: reference-samples/sample-two.md
  - id: sample-three
    title: Approved sample three
    url: https://example.com/articles/three
    path: reference-samples/sample-three.md
  - id: sample-four
    title: Approved sample four
    url: https://example.com/articles/four
    path: reference-samples/sample-four.md
  - id: sample-five
    title: Approved sample five
    url: https://example.com/articles/five
    path: reference-samples/sample-five.md
checks:
  informationDensity: true
  uniformCadence: false
rules:
  bannedPhrases: [at the end of the day]
  bannedIntensifiers: [very]
  bannedPatterns:
    - pattern: "\\bseamless\\b"
      message: Prefer a concrete description of the integration.
  contrastCap: 2
density:
  minWords: 400
  minLexicalDensity: 0.45
  maxGzipRatio: 0.35
```

Reference `path` values are resolved relative to the profile file, not the
shell's current directory. Keep five to ten approved samples beside the
profile (or use paths such as `../samples/approved.md`). YAML and JSON use the
same field names; `features/fixtures/editorial-style-profile/portable-profile.json`
is a checked-in JSON example.

The `checks` mapping can enable or disable individual diagnose checks. If it is
omitted, every check is enabled. `rules` is optional and defaults to no custom
rules. `density` is optional and defaults to `minWords: 400`,
`minLexicalDensity: 0.45`, and `maxGzipRatio: 0.35`. Unknown control names and
invalid values fail profile validation before a draft is analyzed.

Optional `editorialAim` is a non-empty string describing how the publication
balances priorities (for example, cite-first versus ordinary-language clarity).
When set, judge and rewrite-option prompts include it so steering can reflect
that tradeoff.

Optional `compare` controls candidate ranking hard disqualifiers. If `compare` is
omitted, `compare.hardConstraints` defaults to
`unsupported_claims_increase` (candidates that add unsupported claims cannot
rank first). Set `compare.hardConstraints` to an empty list to disable hard
disqualification on those axes. Only constraint names listed in the profile are
applied; unknown names fail validation at load time.

Limatus is style-focused, not an AI detector. Profile documents must not
contain detector scores or detector-related fields; the loader rejects those
keys, including nested keys.

From the repository root, run the portable fixture against a checked-in draft:

```bash
limatus diagnose \
  --draft features/fixtures/editorial-diagnosis/sloppy-draft.md \
  --profile features/fixtures/editorial-style-profile/portable-profile.json \
  --output /tmp/limatus-diagnosis.json
cat /tmp/limatus-diagnosis.json
```

The command leaves the draft unchanged and writes validated diagnostic JSON.
The same command works with a YAML profile by changing only the `--profile`
path, for example `features/fixtures/editorial-diagnosis/style-profile.yml`.

## Offline editorial eval corpus

`limatus eval` runs a deterministic, network-free regression over checked-in drafts
listed in a YAML manifest. Each row names a draft path, expected finding kinds
(`expectKinds`), optional `maxFindings`, and option-safety checks so diagnose output
never embeds rewrite payloads. The default smoke corpus lives at
`features/fixtures/editorial-diagnosis/editorial-corpus/manifest.yml`.

```bash
limatus eval --manifest features/fixtures/editorial-diagnosis/editorial-corpus/manifest.yml
```

CI runs the same command on every pull request (see `.github/workflows/ci.yml`).

### Aggregate metrics

After each row, `limatus eval` prints kind-level **precision** and **recall** by
comparing diagnosis finding kinds to each manifest row's `expectKinds` (gold positives
for that draft). True positives are expected kinds present in the diagnosis; false
negatives are expected kinds missing (those still fail the row); false positives are
extra diagnosis kinds not listed in `expectKinds` (they do not fail sloppy `mustFail`
rows, but they lower precision). On `mustPass` rows with empty `expectKinds`, every
surfaced kind counts as a false positive. Micro-averaged ratios use the usual
TP/(TP+FP) and TP/(TP+FN) formulas; when both numerator and denominator are zero,
the metric is reported as `1.0` (a clean negative with zero findings is perfect).

When the manifest includes an `options` list pointing at checked-in options JSON,
the summary also reports **unsupportedClaimRate**: the fraction of rewrite option
candidates with `factVerificationRequired: true`. Those fixtures are validated
with the same option-safety forbidden-key checks as diagnosis output. The summary
line `judgePromptVersion=…` pins the editorial judge prompt revision used elsewhere
in the product, even though offline eval never calls a live judge.

### Turning a reject into a fixture

When copy-edit is rejected or a false positive is confirmed in production:

1. Copy the draft (or a minimized excerpt that still reproduces the behavior) into
   `features/fixtures/editorial-diagnosis/` — for example `must-fail/` for drafts
   that must surface specific findings, or beside the corpus under
   `editorial-corpus/` for clean negatives.
2. Add a `mustFail` or `mustPass` row to the manifest with `id`, `path`,
   `expectKinds`, and for failures a non-empty `expectTerms` list that appears in
   the diagnosis JSON. Set `maxFindings: 0` on `mustPass` rows that should stay clean.
3. Run `limatus eval --manifest …` locally until the new row passes.
4. Commit the draft and manifest change together.

Agents should follow the same loop when editorial diagnosis regresses in the field.

## Testing

Limatus's test suite is written in Gherkin and run with [Behave](https://behave.readthedocs.io/):

```bash
behave
```

Pytest unit tests:

```bash
python -m pytest tests -q
```

Judge calibration canary (fixture judge, no API key):

```bash
limatus canary --manifest features/fixtures/editorial-canary/manifest.yml
```

## License

MIT — see [LICENSE](LICENSE).
