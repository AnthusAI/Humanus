# CHANGELOG


## v0.33.1 (2026-10-20)

### Bug Fixes

- **release**: Build the limatus shim after reclaiming dist/
  ([#53](https://github.com/AnthusAI/Humanus/pull/53),
  [`6bce6fd`](https://github.com/AnthusAI/Humanus/commit/6bce6fd7807e40e836aca2c36adb0be994d14b90))

The semantic-release action builds as root, so dist/ was not writable and the shim build failed
  before anything was published.

Co-authored-by: Claude Opus 5.5 <noreply@anthropic.com>


## v0.33.0 (2026-10-20)

### Chores

- **board**: Record PR #45 status and a stranded local branch
  ([#50](https://github.com/AnthusAI/Humanus/pull/50),
  [`62d5b12`](https://github.com/AnthusAI/Humanus/commit/62d5b12870d96dbf0241346c3da223db5ffcb403))

File LIM-2f46c9 (ASD-STE100 work is done only on the unmerged, conflicting PR #45 branch; rebase
  onto 0.31.0 or close) and LIM-ed78ec (local branch codex/add-effective-story-writing-skill
  predates main's history rewrite; check its project/ files, then salvage or delete).

Co-authored-by: Claude Opus 5.5 <noreply@anthropic.com>

### Refactoring

- Rename Limatus to Humanus ([#52](https://github.com/AnthusAI/Humanus/pull/52),
  [`5751aff`](https://github.com/AnthusAI/Humanus/commit/5751aff11408ac78a2cd15dc5dcc411acccd853b))

* chore(kanbus): commit board state

* refactor!: rename Limatus to Humanus

The package, import name, CLI and schema ids are now humanus, and the repository moved to
  AnthusAI/Humanus. A limatus compatibility package (shim/limatus) depends on humanus, maps import
  limatus and the limatus command to it with a deprecation warning, and is published once by the
  release workflow.

BREAKING CHANGE: install humanus and import humanus; the limatus distribution is only a
  compatibility shim. Schema $id URLs move to humanus.anth.us.

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>

---------

Co-authored-by: Kanbus <kanbus@localhost>

Co-authored-by: Claude Opus 5.5 <noreply@anthropic.com>

### Breaking Changes

- Install humanus and import humanus; the limatus distribution is only a compatibility shim. Schema
  $id URLs move to humanus.anth.us.


## v0.32.0 (2026-10-20)

### Chores

- **kanbus**: Commit board state
  ([`c16fe37`](https://github.com/AnthusAI/Humanus/commit/c16fe37f98028573beef9ec6977a37742f6cfbc4))

- **kanbus**: Commit board state
  ([`38aa9ce`](https://github.com/AnthusAI/Humanus/commit/38aa9ce541146e586e401f257e0a17ec6c69f569))

- **kanbus**: File audit bugs 2026-10-20 ([#48](https://github.com/AnthusAI/Humanus/pull/48),
  [`c9f70c2`](https://github.com/AnthusAI/Humanus/commit/c9f70c2166f9f4297174b140a2e045abd8f7ceeb))

Co-authored-by: Claude Opus 5.5 <noreply@anthropic.com>

### Features

- Asd-ste100 and Federal Plain Language starter packs
  ([#49](https://github.com/AnthusAI/Humanus/pull/49),
  [`ab9b972`](https://github.com/AnthusAI/Humanus/commit/ab9b9720eccc800f7fa2d8a4d2b0fd0ef2b83874))

Add eleven built-in checks for published writing standards: sentence_length (with
  procedure/description topics), average_sentence_length, paragraph_length, reading_grade_level
  (Flesch-Kincaid), double_negative, undefined_acronym, multiple_instructions, imperative_steps,
  ing_form, missing_article and one_meaning. Phrase detectors take exceptions (technical names),
  passive_voice catches irregular participles, and the rules lane keeps one hit per policy and span,
  preferring the one with a replacement.

Ship two starter packs on them: asd-ste100 (ports PR #45 onto policy packs, with its gold drafts as
  regression tests) and plain-language (Federal Plain Language Guidelines, with Jev questions for
  audience, main point first and jargon).

Co-authored-by: Claude Opus 5.5 <noreply@anthropic.com>


## v0.31.0 (2026-10-20)

### Refactoring

- Retire the legacy scan/judge loop ([#47](https://github.com/AnthusAI/Humanus/pull/47),
  [`8747329`](https://github.com/AnthusAI/Humanus/commit/874732917b018610e886086e0714ba6b1c14692a))

BREAKING CHANGE: the legacy scan/judge loop, its commands, modules and limatus.sdk are removed. Use
  limatus check / suggest with a policy pack; convert style profiles with limatus pack import.

### Breaking Changes

- The legacy scan/judge loop, its commands, modules and limatus.sdk are removed. Use limatus check /
  suggest with a policy pack; convert style profiles with limatus pack import.


## v0.30.0 (2026-10-20)

### Features

- Configurable editorial compliance engine ([#46](https://github.com/AnthusAI/Humanus/pull/46),
  [`4e64a49`](https://github.com/AnthusAI/Humanus/commit/4e64a49e035674550c6818cc17027fea7c0d7bb4))

* feat(contracts): policy packs, Markus segmenter and check() (LIM-6a84be)

Introduce the contract layer for the configurable editorial compliance engine (LIM-a5828a):

- JSON Schemas packaged under limatus/schemas: policy-pack-v1, check-request-v1, check-result-v1,
  finding-v1, suggest-request-v1, suggest-result-v1; `limatus schema <name>` prints them. -
  load_policy_pack: schema plus semantic validation (unique ids, compilable regexes, coherent
  classifier thresholds). - policy_pack_from_style_profile and `limatus pack import|validate`. -
  Markus-aware segmenter (markdown-it-py): paragraph and sentence segments with exact offsets,
  content-derived stable ids, protected regions for front matter, code, directives, quotes, tables
  and HTML. - check(): standoff annotation with UTF-16 offsets and lane status; finding_id() for ids
  stable across rescans; `limatus check`.

Lanes report "unavailable" until LIM-dc05d2 and LIM-3f3065 land.

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>

* chore(kanbus): commit board state

* docs(wiki): record editorial compliance engine vision (LIM-a5828a)

* feat(check): rules lane, AI-writing tells pack and Jev classifier lane

Rules lane (LIM-dc05d2): phrase, regex and builtin detectors run on prose segments only (never code,
  quotes, directives or tables). Builtins reuse the always-lane heuristics on the new segmentation;
  uncontracted forms and emoji carry deterministic replacements. `voice_mismatch` is renamed
  `passive_voice`. Starter pack `ai-writing-tells` (24 policies, 108 detectors) adapted from
  avoid-ai-writing (MIT, see packs/NOTICE.md); `limatus pack builtin [name]`.

Classifier lane (LIM-3f3065): zero-shot decisions from TypeSafe Jev via the optional `limatus[jev]`
  extra. One request per segment with every applicable question; sentences judged with their
  paragraph as context; policy examples ride along with each question. Content-keyed answer cache,
  bounded concurrency, input-token budget (lane reports partial), review band, coverage of every
  decision, and graceful degradation when the model is missing or failing. Question criteria now
  match the Jev API (noul {true,false}, choice labels, score level list).

check() validates the request once and no longer re-validates its own result (specs assert the
  contract), cutting runtime by about 75%.

* feat(suggest): Luna rewrite options for findings and selections; draft classifier questions
  (LIM-7906a5)

- suggest(): rewrite options for a finding or any editor selection, with an optional editor note. A
  finding's target expands to its sentence (flagged words marked) so options are whole sentences,
  not fragments. The prompt carries the policy guidance, rewrite guidance, compliant examples, house
  policies and a voice sample; options that are identical, duplicated, evasion-motivated, or still
  break the triggering rule are dropped and reported. Spans must cover prose. - draft_questions():
  turns a prose policy into atomic noul classifier detectors (sentence/paragraph/document scope,
  threshold 0.8, review from 0.5), each validated against policy-pack-v1; rejects are noted. -
  Contracts: suggest-request accepts finding or selection; suggest-result reports target and dropped
  options; draft-questions-request/result-v1. - CLI: `limatus suggest --request`, `limatus
  draft-questions --request`. Defaults to gpt-6-luna through OPENAI_API_KEY.

* feat(calibration): learn from editor decisions (LIM-9ba0bf)

- calibrate(): per-detector calibration from feedback labels — none below 10 labels, Platt scaling
  from 10, isotonic (PAV) from 50. Synthetic overconfident detector: held-out ECE 0.19 -> 0.027. -
  Detectors carry an optional `calibration`; check() thresholds on the calibrated probability and
  reports rawProbability on findings and coverage. - Few-shot retrieval: options.classifier.examples
  (past decisions with text); the most similar per target (word Jaccard) ride along with each
  question, capped by maxExamplesPerQuestion. - Contracts feedback-labels-v1 and calibration-v1;
  `limatus calibrate`.

* feat(classifier): deadlineSeconds keeps synchronous checks under API timeouts (LIM-3f3065)

The classifier lane stops starting new requests once the deadline passes and reports partial, so a
  CMS can call check() inside a 30-second AppSync resolver.

* feat(check): plain text on segments and findings for rendered previews

Paragraph and sentence segments carry their plain text and findings their plain excerptText, so a
  CMS can place findings on a rendered preview, not only on the markup source.

---------

Co-authored-by: Claude Opus 5.5 <noreply@anthropic.com>

Co-authored-by: Kanbus <kanbus@localhost>


## v0.29.0 (2026-09-27)

### Features

- **skills**: Add effective story writing guidance
  ([`7920df6`](https://github.com/AnthusAI/Humanus/commit/7920df6f3c79a42de1fe952ada68adab5b7a0343))


## v0.28.0 (2026-09-12)

### Chores

- **kanbus**: Commit board state (issues)
  ([`f174b39`](https://github.com/AnthusAI/Humanus/commit/f174b398fb26a6c210c77c5d1099bd6c09ecefba))

### Features

- **usability**: Add generic_feature_row scan (LIM-d75641)
  ([#39](https://github.com/AnthusAI/Humanus/pull/39),
  [`6063025`](https://github.com/AnthusAI/Humanus/commit/606302546dab1a1b5d4d8c63bf43b7a08300de63))

Detect consecutive sibling feature cards with shared leading class and images; gate via
  template.flagFeatureRow (default true).


## v0.27.0 (2026-09-12)

### Chores

- **kanbus**: Commit board state (issues)
  ([`ee800ec`](https://github.com/AnthusAI/Humanus/commit/ee800ecf8edb6d18420b19f2649f255101006d74))

### Features

- **usability**: Add generic_gradient_hero scan (LIM-f9e7cf)
  ([#38](https://github.com/AnthusAI/Humanus/pull/38),
  [`09d74c2`](https://github.com/AnthusAI/Humanus/commit/09d74c2443aeffea02bbab51244b97975391b9ec))

Detect linear-gradient backgrounds on hero-region selectors when template.flagGradientHero is
  enabled (default true).


## v0.26.0 (2026-09-12)

### Chores

- **kanbus**: Commit board state (issues)
  ([`9d10e10`](https://github.com/AnthusAI/Humanus/commit/9d10e104837c63a4ed5390a040baa08217acfc7e))

### Features

- **usability**: Emoji_heading scan kind (LIM-f7bce7)
  ([#37](https://github.com/AnthusAI/Humanus/pull/37),
  [`8a3c345`](https://github.com/AnthusAI/Humanus/commit/8a3c345096801322d505e552a9fa6827d89fbbaf))

Extract shared EMOJI_PATTERN, add emoji.flagInHeadings profile toggle, and flag headings that
  contain emoji in usability scan.


## v0.25.0 (2026-09-12)

### Chores

- **kanbus**: Commit board state (issues)
  ([`8b1e5d2`](https://github.com/AnthusAI/Humanus/commit/8b1e5d22bceea655f3dbb58847c6ddda107f120a))

### Features

- **usability**: Add missing_lang scan kind (LIM-1d9020)
  ([#36](https://github.com/AnthusAI/Humanus/pull/36),
  [`a7f5aae`](https://github.com/AnthusAI/Humanus/commit/a7f5aaee8c500e095cb70ed297e0c73793b6e173))

Flag root html elements without a non-empty lang attribute, gated by lang.flagMissing in the
  usability profile (default true).


## v0.24.0 (2026-09-12)

### Chores

- **kanbus**: Commit board state (issues)
  ([`e4f33f8`](https://github.com/AnthusAI/Humanus/commit/e4f33f8e185431363521694ba1516e2e4244b0af))

- **kanbus**: Commit board state (issues)
  ([`1419eda`](https://github.com/AnthusAI/Humanus/commit/1419eda5ad32649e3fd5970ac071a70d212e1a74))

### Documentation

- **skill**: Lim-15fa45 document HTML usability scan in SKILL.md
  ([#35](https://github.com/AnthusAI/Humanus/pull/35),
  [`1c67317`](https://github.com/AnthusAI/Humanus/commit/1c67317e8cf865aed42fe47ff31b96ba58f4b83d))

### Features

- **usability**: Add missing_accessible_name scan (LIM-dbfe8e)
  ([#34](https://github.com/AnthusAI/Humanus/pull/34),
  [`f562257`](https://github.com/AnthusAI/Humanus/commit/f56225700fdd0c3ddd9c79afd80b21c6465d88a7))

Extend usability scan with accessibleName.flagMissing profile option and DOM checks for input,
  select, and textarea naming.


## v0.23.0 (2026-09-12)

### Chores

- **kanbus**: Commit board state (issues)
  ([`afcff2c`](https://github.com/AnthusAI/Humanus/commit/afcff2cfb3e186ca9f4e73d643ec190f49a929a1))

### Features

- **usability**: Flag suppressed focus outline (LIM-942618)
  ([#33](https://github.com/AnthusAI/Humanus/pull/33),
  [`0d669d7`](https://github.com/AnthusAI/Humanus/commit/0d669d739dffd3fe0e4dcd10afce1cb789a092a2))

Add suppressed_focus_outline scan for interactive controls when focus styles remove outline without
  a compensating box-shadow, with profile focus.flagSuppressedOutline (default true).


## v0.22.0 (2026-09-12)

### Chores

- **kanbus**: Commit board state (issues)
  ([`c60cac5`](https://github.com/AnthusAI/Humanus/commit/c60cac50b9d81b6f5e71a2231cb6622bb2fd1bf1))

### Features

- **usability**: Add small tap target scan (LIM-17723e)
  ([#32](https://github.com/AnthusAI/Humanus/pull/32),
  [`1d64ad0`](https://github.com/AnthusAI/Humanus/commit/1d64ad0a069832e6895f16f5a1804102293829e0))

Extend usability scan with small_tap_target findings, tapTarget.minPx profile default, and
  deterministic width/height resolution from attrs, inline styles, and embedded CSS rules.


## v0.21.0 (2026-09-12)

### Chores

- **kanbus**: Commit board state (issues)
  ([`599b7c2`](https://github.com/AnthusAI/Humanus/commit/599b7c25dc8dee7908f6f0f18e76206291b181d6))

- **kanbus**: Commit board state (issues)
  ([`4585a1c`](https://github.com/AnthusAI/Humanus/commit/4585a1c8304c79687e28038276696cd7a1732e08))

- **kanbus**: Commit board state (issues)
  ([`cb0c905`](https://github.com/AnthusAI/Humanus/commit/cb0c9059632462e145adf6b15a7e82a93502fc31))

### Features

- **usability**: Read-only HTML scan (LIM-274a81)
  ([#31](https://github.com/AnthusAI/Humanus/pull/31),
  [`c87ecaa`](https://github.com/AnthusAI/Humanus/commit/c87ecaae1c219c0e8ce96f59f5b2cf3f0517016f))

* feat(usability): add read-only HTML scan for LIM-274a81

Introduce `limatus usability scan` with a dedicated usability profile schema, WCAG contrast checks,
  and missing-alt detection without touching editorial scan output.

* fix(usability): void HTML elements and test hygiene (LIM-274a81)

Pop void tags off the parser stack so siblings are not nested under img, harden 3-digit hex parsing,
  and use temp dirs for CLI/profile tests plus a read-only page byte check.


## v0.20.0 (2026-09-11)

### Chores

- **kanbus**: Close rewrite-loop epic; start LIM-3863ed skill CLI
  ([`9d5914d`](https://github.com/AnthusAI/Humanus/commit/9d5914d6b8653e4a2093927d4979e21b34a0982f))

### Features

- **cli**: Print packaged SKILL.md via limatus skill
  ([#30](https://github.com/AnthusAI/Humanus/pull/30),
  [`7a4e197`](https://github.com/AnthusAI/Humanus/commit/7a4e197cfd35ced3b791bdc47ecb52113d48936f))

LIM-3863ed — Package copy-edit Agent Skill in the wheel and expose it through a
  progressive-disclosure `limatus skill` subcommand.


## v0.19.0 (2026-09-11)

### Chores

- **kanbus**: Close LIM-fc61e8; start preferredPhrasing LIM-74d5fb
  ([`8ffdbce`](https://github.com/AnthusAI/Humanus/commit/8ffdbcec719c30e1aa549ad3b73ff6394bd2b766))

### Features

- **style**: Preferredphrasing from/to profile reword hints
  ([#29](https://github.com/AnthusAI/Humanus/pull/29),
  [`22bbee6`](https://github.com/AnthusAI/Humanus/commit/22bbee6c37dce4cfdbb7a747dbd3873eb80d0d88))


## v0.18.0 (2026-09-11)

### Chores

- **kanbus**: Close evals epic (#28); start LIM-fc61e8 voice audit
  ([`341c374`](https://github.com/AnthusAI/Humanus/commit/341c3741b093d40ab3487117eae88fe0a8b1116e))

- **kanbus**: Close false HITL wait; start Papyrus SDK adapter
  ([`c6e4efc`](https://github.com/AnthusAI/Humanus/commit/c6e4efcd161576d92f81d7f698312f87252be0f1))

LIM-80209b was parked on a stale Ryan-option-id gate. LIM-3ff8d0 / LIM-209793 in progress.

- **kanbus**: Close LIM-3ff8d0 Papyrus SDK integration
  ([`a56a400`](https://github.com/AnthusAI/Humanus/commit/a56a40010914efc929d0859b39ca4b814c132017))

Papyrus #80 landed on develop. LIM-209793 and the epic are done.

- **kanbus**: Close LIM-81ecb1 (#27); start LIM-658c60 metrics
  ([`3d95571`](https://github.com/AnthusAI/Humanus/commit/3d95571941c5408ec94c4dba3fe21f8522fbd9a7))

- **kanbus**: Lim-fc61e8 Chatticus covered; Anth.us PPY-cc58ab
  ([`a9c3bb3`](https://github.com/AnthusAI/Humanus/commit/a9c3bb3819b538762c355bc4c08e415d4dd4fa6a))

- **kanbus**: Pr #80 revision for Tactus lockfile
  ([`67c8c0c`](https://github.com/AnthusAI/Humanus/commit/67c8c0c5cbe7ca051fdb5a6010ea11a9072bf24e))

- **kanbus**: Start LIM-81ecb1 eval CI and fixture corpus close-out
  ([`2196040`](https://github.com/AnthusAI/Humanus/commit/21960408536ea8970265aeb372b7ba46e60b31a5))

Offline runner already exists (LIM-c1a014). Remaining: CI, docs, more fixtures.

### Continuous Integration

- **eval**: Smoke pytest and offline corpus on PRs
  ([#27](https://github.com/AnthusAI/Humanus/pull/27),
  [`b1b6fbc`](https://github.com/AnthusAI/Humanus/commit/b1b6fbc371d16625b29d3ab39906d75d79ed73cc))

Add CI workflow for pytest, offline eval corpus, and Behave smoke. Expand editorial corpus fixtures,
  document eval workflow in README, and fix portable profile test to resolve reference samples.

### Features

- **eval**: Report finding precision/recall and option claim flags
  ([#28](https://github.com/AnthusAI/Humanus/pull/28),
  [`fd24784`](https://github.com/AnthusAI/Humanus/commit/fd2478476d043cb3fad63f0b24fa83fe4640715a))


## v0.17.1 (2026-09-11)

### Bug Fixes

- **diagnosis**: Lim-ed02c3 ignore image alts and blockquote redundancy
  ([#26](https://github.com/AnthusAI/Humanus/pull/26),
  [`974c12a`](https://github.com/AnthusAI/Humanus/commit/974c12a21a9c99d27d15c284b2e74271ffce4a7b))

* fix(diagnosis): ignore image markdown and blockquote refrain in redundancy

Mask Markdown/HTML image markup before 4-gram shingling and skip redundancy groups whose members all
  start on blockquote lines (LIM-ed02c3).

* fix(diagnosis): skip redundancy when all n-gram hits are quoted material

Per-occurrence quoted context: blockquote lines, emphasis spans, and Markus pull-quote bodies
  (LIM-ed02c3 revision).

### Chores

- **kanbus**: Close HITL apply gate, park usability epic, start LIM-ed02c3
  ([`e776b54`](https://github.com/AnthusAI/Humanus/commit/e776b5402dd9b784aad4a42ea627722393c08a33))

LIM-2d43b1 stays closed. LIM-30ca2a closed (CLI apply gate). LIM-e872b1 returned to open. LIM-ed02c3
  in progress as the last HITL WIP child. LIM-3ff8d0 left open, not started.

- **kanbus**: Close LIM-2d43b1 portable CLI+SDK epic
  ([`e6d3f26`](https://github.com/AnthusAI/Humanus/commit/e6d3f260eb60adbbc2d1df243e83a9124b60eb20))

Children are done on main. Papyrus adapter remains LIM-209793 under LIM-3ff8d0.

- **kanbus**: Close LIM-ed02c3 and HITL packets epic
  ([`ec2efe0`](https://github.com/AnthusAI/Humanus/commit/ec2efe0e38547e2b867c57c365f212532861ba24))

#26 landed on main. LIM-0b9d81 children are all closed.

- **kanbus**: Lim-ed02c3 revision for italic and pull-quote refrain
  ([`7ca27cc`](https://github.com/AnthusAI/Humanus/commit/7ca27ccb0d2c53bd67e78564c84bd2174248c73b))

PR #26 image mask stands; live confession liturgy still flagged.

- **kanbus**: Record LIM-ed02c3 worktree
  ([`3b53063`](https://github.com/AnthusAI/Humanus/commit/3b53063930055332dea72d355dff26ce10602a7d))

Composer worktree /tmp/limatus-ed02c3-redundancy on fix/LIM-ed02c3-redundancy-alts.


## v0.17.0 (2026-09-11)

### Features

- Explicit pass/fail verdict on the density block
  ([#24](https://github.com/AnthusAI/Humanus/pull/24),
  [`dad4a7f`](https://github.com/AnthusAI/Humanus/commit/dad4a7f74be5e54c69f070e7e89c88e41fb7fabe))

A diagnosis's `density` block reported raw numbers (wordCount, lexicalDensity, gzipRatio) with no
  verdict. A caller had to already know the profile's thresholds and cross-reference
  `generic_passages` by finding kind to know whether density actually passed.

Adds `skippedTooShort` and `withinThresholds` to `density_summary_as_dict`'s output.
  `withinThresholds` is deliberately `None`, not `True`, when the document is under the profile's
  `minWords` -- `analyze_density` suppresses both real checks in that case, so "too short to judge"
  and "judged and passed" need to stay distinguishable rather than collapsing into one boolean.

`density_summary_as_dict` now takes the profile's `DensityThresholds` and the analysis's findings
  alongside the summary; its one call site (editorial_diagnosis.py) is updated. No other code or
  test in the repo called this function directly, so nothing else needed touching.

Verified: a 2-word draft reports `skippedTooShort: true,

withinThresholds: null`; the real article this whole feedback pass came

from reports `skippedTooShort: false, withinThresholds: true`.

73 pytest tests pass (the same 1 pre-existing, unrelated fixture-path failure as PR #21). Behave: 30
  features / 64 scenarios / 256 steps, all passing, unchanged from #21.

Claude-Session: https://claude.ai/code/session_01VXT47sZM5anEmz8PmN8mbf

Co-authored-by: Claude <noreply@anthropic.com>

- Verify recognizes a reworded claim as preserved, not deleted
  ([#25](https://github.com/AnthusAI/Humanus/pull/25),
  [`63aa6f9`](https://github.com/AnthusAI/Humanus/commit/63aa6f948c317b5fd844917447fce5297a170226))

verify's diff was exact-string matching: any sentence whose normalized text didn't appear
  byte-for-byte in the working copy was flagged deleted_claim, and any new fact-pattern token
  (including a bare URL) was flagged factual_change_risk -- unconditionally. Every legitimate
  rewrite that touches a fact-bearing sentence looked identical to deleting a claim and inventing a
  new one, whether or not the claim actually survived.

Concretely, this is what motivated the fix: rewording a sentence to add a citation -- exactly what
  this profile's own evidenceRules ask writers to do -- registered as both a deleted_claim (old
  wording gone) and a factual_change_risk (the new URL is a new token). The tool was penalizing the
  edit it was supposed to encourage.

`_claim_preserved` now checks, for a sentence whose exact wording changed: does some working
  sentence contain almost all of the original's own concrete facts (numbers, years, links, absolute
  words), and share enough of its general vocabulary that this isn't a coincidental match between
  two unrelated claims. Both checks are containment (how much of the original survives in the
  candidate), not symmetric Jaccard -- Jaccard penalizes a candidate for containing MORE than the
  original, which is exactly what a citation-adding edit does, and exactly what sentence-merging
  does (two short original sentences folded into one longer working sentence dilutes symmetric
  overlap even when nearly every original word is still present). Verified on a real paragraph that
  both adds nothing but a citation and merges two sentences into one: zero false-positive findings,
  where the previous algorithm flagged it.

`factual_change_risk` (both the score and the finding) now diffs against `_RISK_FACT_PATTERN`, which
  is `_FACT_PATTERN` minus the bare-URL branch: adding a citation to an existing claim must never by
  itself read as introducing a new, unverified fact. A newly added number, year, or absolute word
  still does -- that is a real new claim.

Three new tests lock in the distinction this fix exists to draw: a reworded sentence with an added
  citation is not a deleted claim; adding a citation to an existing number is not a new risk; a
  sentence whose claim is actually different (not just reworded) is still flagged. All four
  pre-existing verifier tests are unchanged and still pass.

76 pytest tests pass (7 in test_verifier.py, up from 4; same 1 pre-existing, unrelated fixture-path
  failure as #21/#22). Behave: 30 features / 64 scenarios / 256 steps, all passing, unchanged.

Claude-Session: https://claude.ai/code/session_01VXT47sZM5anEmz8PmN8mbf

Co-authored-by: Claude <noreply@anthropic.com>


## v0.16.3 (2026-09-11)

### Bug Fixes

- Three quiet correctness gaps found using Limatus on a real draft
  ([#21](https://github.com/AnthusAI/Humanus/pull/21),
  [`f091f92`](https://github.com/AnthusAI/Humanus/commit/f091f9248fb55eb43f90cd46751f2112df9e5e2e))

Found while copy-editing a real Pilobolus article and diagnosed with the help of an Explore agent,
  which pinned exact file/line references for each before any change was made.

1. Silent judge skip. `run_default_judge_lane` returned an empty `JudgeLaneResult` with zero output
  when `OPENAI_API_KEY` was unset and `--require-judge` wasn't passed -- every voice/tone check that
  needs the judge silently did not run, and a diagnosis JSON from that path was indistinguishable
  from "the judge ran and found nothing." The sibling API-error branch already prints a stderr
  notice in this situation; the no-key branch now does too. Closes a real test gap:
  `judge-optional-at-runtime.feature`'s "No key" scenario captured stderr but never asserted on it
  -- it now does.

2. Blockquoted text treated as the narrator's own claim. A Markdown blockquote (quoted human speech,
  e.g. a Reddit comment reproduced in an article) was checked by `_check_unsupported_certainty` and
  `_check_required_facts` as if the *narrator* had asserted it. Added `_is_blockquote_line`, wired
  into both checks -- quoted material is never the narrator's certainty claim.

3. `verify`'s findings were unreadable. `duplication` findings always had `evidence: ""` because
  `_findings` read a `group["excerpt"]` key that repetition groups never set (only each `members[]`
  entry carries one) -- now pulls the actual repeated phrase and notes the repeat count.
  `deleted_claim` and `factual_change_risk` findings had no `rationale` at all, and
  `factual_change_risk`'s evidence was a bare token like "new factual token: 1993" with no context
  -- both now explain themselves, and the latter quotes the sentence that introduced the token when
  one is found.

Also: declares `pytest` in `dev` extras. `tests/` is a pytest suite (bare `assert`, `test_*`
  functions) with no way to run it from a fresh `pip install -e ".[dev]"` today.

Deliberately not touched, and written up separately as design decisions rather than bugs: `verify`'s
  exact-string diff treats every reworded sentence as delete-plus-new-claim (a real algorithm
  change, not a fix); `judge.provider` accepts only "openai" (an existing feature,
  `openai-only-judge-this-stage.feature`, tests specifically that other providers are *rejected* --
  "so we do not pretend multi-provider support exists"); and the `density` block in a diagnosis
  never states a pass/fail verdict, only raw numbers (a schema addition, not a defect).

Verified against the article that surfaced these: 0 findings changed except the three classes above
  (blockquote sentence dropped from `unsupported_claims`; stderr warning now printed; `verify`'s
  duplication findings now show the real repeated phrase).

76 pytest tests pass (1 pre-existing, unrelated failure in test_compare.py -- a fixture resolves
  reference-sample paths against a tempdir that doesn't contain them -- present before this change
  and untouched by it). Behave: 30 features / 64 scenarios / 256 steps, all passing (was 255 steps;
  the new stderr assertion is the added one).

Claude-Session: https://claude.ai/code/session_01VXT47sZM5anEmz8PmN8mbf

Co-authored-by: Claude <noreply@anthropic.com>


## v0.16.2 (2026-09-11)

### Bug Fixes

- **judge**: Body scan blanks YAML so title is a later pass
  ([#20](https://github.com/AnthusAI/Humanus/pull/20),
  [`88004fa`](https://github.com/AnthusAI/Humanus/commit/88004fa9cb81e3c48113a4a317dd66d09b8e7499))

LIM-530ec2: the OpenAI judge was scoring the YAML title. Mask frontmatter the same way the profile
  lane does, drop YAML-span findings/rubric evidence, and bump JUDGE_PROMPT_VERSION with the canary
  pin.

### Chores

- **kanbus**: Close LIM-530ec2 after PR #20
  ([`4e23177`](https://github.com/AnthusAI/Humanus/commit/4e231771b7fbe73b43652380394493bd33936396))

Judge body scan blanks YAML on main; title and subtitle stay a later pass.


## v0.16.1 (2026-09-11)

### Bug Fixes

- **headline**: Subtitle options must summarize the article under the title
  ([#19](https://github.com/AnthusAI/Humanus/pull/19),
  [`94c068d`](https://github.com/AnthusAI/Humanus/commit/94c068dd5c8887575840a846be332dc7c98cda29))


## v0.16.0 (2026-09-11)

### Chores

- **kanbus**: Close LIM-565ba8 after PR #18
  ([`beddd27`](https://github.com/AnthusAI/Humanus/commit/beddd2762bbd806f0d384b5658f2fc907cd9146a))

### Features

- **headline**: Profile-bound title/subtitle HITL after body (LIM-565ba8)
  ([#18](https://github.com/AnthusAI/Humanus/pull/18),
  [`665f79d`](https://github.com/AnthusAI/Humanus/commit/665f79d9d44f5a756e2ceba94e1feef255f26851))

Add headline schema and CLI options pass, YAML scalar spans for frontmatter fields, and
  suggest_rewrite frontmatter preservation for body-only candidates.


## v0.15.0 (2026-09-11)

### Bug Fixes

- **editorial**: Coalesce unread span prefix onto suffix-start replacements (LIM-af431b)
  ([#17](https://github.com/AnthusAI/Humanus/pull/17),
  [`311f58b`](https://github.com/AnthusAI/Humanus/commit/311f58be0dd2f0994486a71d1ac1c5f7c1358da2))

LLM rewrite options that align with a later substring of the span excerpt are prepended with the
  unread prefix before normalization skip checks and apply, so wiki-janitor options succeed without
  dropping below two options or failing closed at apply time.

### Chores

- **kanbus**: Article then title then subtitle (LIM-565ba8)
  ([`020f5ec`](https://github.com/AnthusAI/Humanus/commit/020f5eccf31dbcfe80d1b0dbbd7bdfb6b8930ceb))

- **kanbus**: Close LIM-54c503 after PR #16
  ([`b4d528e`](https://github.com/AnthusAI/Humanus/commit/b4d528ea19b3084c6ce5f93dd60d8cc6ee18add9))

- **kanbus**: Close LIM-af431b after PR #17
  ([`913af41`](https://github.com/AnthusAI/Humanus/commit/913af4180d079e77e95f6c659fec0eddb5e05662))

- **kanbus**: Start headline, compare-CLI, and prefix-coalesce slices
  ([`2eb0fa8`](https://github.com/AnthusAI/Humanus/commit/2eb0fa825ac443072b7155b80a58eee47c4cd40c))

- **kanbus**: Title and standfirst after body HITL (LIM-565ba8)
  ([`7e30682`](https://github.com/AnthusAI/Humanus/commit/7e30682389484326770cc608010fce0237ca9d93))

### Features

- **compare**: Wire default guideline alignment resolver (LIM-54c503)
  ([#16](https://github.com/AnthusAI/Humanus/pull/16),
  [`b74e976`](https://github.com/AnthusAI/Humanus/commit/b74e97681f82113452b6c8b0914cf63560cda598))

Add OpenAI-backed alignment resolution when OPENAI_API_KEY is set, and pass it through limatus
  compare CLI and SDK compare().


## v0.14.4 (2026-09-11)

### Bug Fixes

- **cli**: Publication editorialAim and profile compare constraints (LIM-edbde2)
  ([#15](https://github.com/AnthusAI/Humanus/pull/15),
  [`35b86fe`](https://github.com/AnthusAI/Humanus/commit/35b86fe48ded58af1bce32d2da46869bc004687f))

### Chores

- **kanbus**: Close LIM-edbde2 after PR #15
  ([`d28086c`](https://github.com/AnthusAI/Humanus/commit/d28086c3d12551334ff8051df3c68c7e303b57d2))

- **kanbus**: File publication-owned editorialAim for compare
  ([`3b83310`](https://github.com/AnthusAI/Humanus/commit/3b8331069612685170b4e02d9b62492ef3e8c72c))

- **kanbus**: Start LIM-edbde2 editorialAim compare layer
  ([`d642de6`](https://github.com/AnthusAI/Humanus/commit/d642de6784601e3aa1aaaf86f686ed630c94848c))


## v0.14.3 (2026-09-11)

### Bug Fixes

- **cli**: Retry rewrite options after prefix-skip drops (LIM-f634c3)
  ([#14](https://github.com/AnthusAI/Humanus/pull/14),
  [`b2c55b5`](https://github.com/AnthusAI/Humanus/commit/b2c55b5865369a3d5aa361198e6130e09e62e855))

When normalization filters prefix-skipping replacements below the two-option minimum, call the
  options resolver once more. The default LLM path adds an extra prompt instruction on retry;
  injected resolvers are invoked again with the same kwargs.

- **cli**: Treat apostrophes as word characters in judge spans (LIM-ce41d9)
  ([#13](https://github.com/AnthusAI/Humanus/pull/13),
  [`38e8c2c`](https://github.com/AnthusAI/Humanus/commit/38e8c2c88cb8463b9f8c2a37990e003a9e243515))

### Chores

- **kanbus**: Close LIM-ce41d9 after PR #13
  ([`dda809f`](https://github.com/AnthusAI/Humanus/commit/dda809fee8324c14d901f7bbff885f392041ea49))

- **kanbus**: Close LIM-f634c3 after PR #14
  ([`fc4067a`](https://github.com/AnthusAI/Humanus/commit/fc4067ad14140258d2ca091a36d6178cb93b86ba))

- **kanbus**: Start LIM-ce41d9 apostrophe word-boundary
  ([`1eb1355`](https://github.com/AnthusAI/Humanus/commit/1eb1355026a035dc42455c3cf6cbdb296b1fa8cc))

- **kanbus**: Start LIM-f634c3; file apostrophe span bug
  ([`b035511`](https://github.com/AnthusAI/Humanus/commit/b03551103ac0fb569b816248974dd893ec66af6e))


## v0.14.2 (2026-09-10)

### Bug Fixes

- **cli**: Reject replacements that skip the span prefix (LIM-073443)
  ([#12](https://github.com/AnthusAI/Humanus/pull/12),
  [`32b1d2a`](https://github.com/AnthusAI/Humanus/commit/32b1d2a4c872ed57d12cb17f0821fe1e64304013))

Fail closed on apply when a replacement aligns with a suffix of the span excerpt, and drop such
  options during rewrite normalization.

### Chores

- **kanbus**: Close LIM-073443 after PR #12
  ([`a747b94`](https://github.com/AnthusAI/Humanus/commit/a747b94dedb3ad4c5a63209d5026d6b66079a99f))

- **kanbus**: File apply span-prefix drop after wiki-janitor dogfood
  ([`3a84a68`](https://github.com/AnthusAI/Humanus/commit/3a84a681a98e4c19c335806709619b57438ed7fe))

- **kanbus**: File options retry after prefix-skip filter
  ([`7c907c4`](https://github.com/AnthusAI/Humanus/commit/7c907c46fd62b73f943c52c39ccc992ae8bb2984))

- **kanbus**: Start LIM-073443 span-prefix apply fail-closed
  ([`2f8227c`](https://github.com/AnthusAI/Humanus/commit/2f8227cdd183fda4997fc6b64b709d6307cb9df6))


## v0.14.1 (2026-09-10)

### Bug Fixes

- **cli**: Drop mid-word judge spans and upsert decisions
  ([#11](https://github.com/AnthusAI/Humanus/pull/11),
  [`7dedd1f`](https://github.com/AnthusAI/Humanus/commit/7dedd1f28d03944ae7f6c880545e33d116ebc93a))

Skip OpenAI judge findings whose spans cut inside a word so apply anchors stay on token boundaries.
  Replace prior decision rows for the same finding_id instead of appending duplicates. Document SDK
  diagnose in README.

### Chores

- **kanbus**: Close LIM-2a1ca5; file LIM-906fc9 dogfood edges
  ([`054f565`](https://github.com/AnthusAI/Humanus/commit/054f56537ad1156cb1e1c92de070f12b33375b85))

CLI apply on wiki-janitor working copy garbled a mid-word judge span.

- **kanbus**: Close LIM-906fc9 and LIM-c32c24 after PR #11
  ([`63eccec`](https://github.com/AnthusAI/Humanus/commit/63eccec966f68dbc6aded56853c87b101a3bbb30))

- **kanbus**: Note LIM-2d43b1 remaining Papyrus adapter DoD
  ([`d94c633`](https://github.com/AnthusAI/Humanus/commit/d94c633f2e9a8640abbf732a62709e9dc25ffa34))


## v0.14.0 (2026-09-10)

### Chores

- **kanbus**: Close LIM-0129cf after PR #10
  ([`bc208e0`](https://github.com/AnthusAI/Humanus/commit/bc208e04fe1a134c0801bac0ef07cc1e24fcddf8))

CLI scan → decide → apply/diff is on main.

- **kanbus**: Close LIM-79c9b2 and LIM-447936
  ([`9203703`](https://github.com/AnthusAI/Humanus/commit/92037030f8f50fd5f43c54ae91a86660b128e2cf))

Judge budget landed; scan packets include live Terra judge output.

- **kanbus**: Lim-0129cf Grok plan for CLI loop
  ([`b67c72a`](https://github.com/AnthusAI/Humanus/commit/b67c72a5bc528c69ef0da768bae8d812e997c571))

Composer 2.5 implements decide, __main__, and CLI apply Behave.

- **kanbus**: Lim-0129cf PR #10 opened
  ([`6527d07`](https://github.com/AnthusAI/Humanus/commit/6527d07f80603f02a9e9bb716902aaadc14c36c5))

CLI loop review ACCEPT; merge waits on worktree acceptance.

- **kanbus**: Lim-30ca2a blocked on Ryan option choice
  ([`ce5b319`](https://github.com/AnthusAI/Humanus/commit/ce5b319bc9aee9cad12c4e4934346d22357cd7bd))

HITL packets ready; no apply until a chosen option id.

- **kanbus**: Park HITL dogfood; start LIM-0129cf CLI
  ([`4c8c999`](https://github.com/AnthusAI/Humanus/commit/4c8c999d5cc5d0f3a3aa6fd2648c2b8a065b3e58))

Ryan will test after scan → decide → options → compare → apply works as a CLI.

### Features

- **cli**: Python -m limatus entry, decide subcommand, and CLI loop tests
  ([#10](https://github.com/AnthusAI/Humanus/pull/10),
  [`b84a4e4`](https://github.com/AnthusAI/Humanus/commit/b84a4e4a591f22799ab1648f6b70e8099e537e1f))

Add __main__ and limatus decide for offline steering decisions; route Behave apply/scan/compare
  steps through python -m limatus and document decide in README.


## v0.13.1 (2026-09-10)

### Bug Fixes

- **judge**: Bounded output token budget for rubric+findings (LIM-79c9b2)
  ([#9](https://github.com/AnthusAI/Humanus/pull/9),
  [`6cbee5b`](https://github.com/AnthusAI/Humanus/commit/6cbee5bcfae6f54e5495a38bed55d196f49a8269))

* fix(judge): raise bounded output token budget for rubric+findings

Hard-coded 2400 max_output_tokens truncated structured judge responses on long Pilobolus drafts with
  required rubric evidence. Use named DEFAULT/MAX judge budgets and draft-scaled helper; generalize
  truncation error wording for non-rewrite callers.

* fix(judge): use 16k floor and 32k cap for finding-heavy scans

Short drafts with dense judge output still truncated at ~8.4k budget because output scales with
  findings and rubric evidence, not draft length. Raise DEFAULT to 16384 for every article and MAX
  to 32768.

### Chores

- **kanbus**: Authorize LIM-79c9b2 judge output budget
  ([`733648e`](https://github.com/AnthusAI/Humanus/commit/733648edf802791064ea5c7ffd04c1d1f172423b))

Plan approved; implementer to use an isolated worktree off main.

- **kanbus**: File LIM-79c9b2 judge output budget
  ([`28d46d2`](https://github.com/AnthusAI/Humanus/commit/28d46d295de40a5cace32571f7a72170ff78ad24))

Live --require-judge HITL truncated at 2400 output tokens.

- **kanbus**: Lim-79c9b2 16k floor pushed, re-acceptance
  ([`94a121b`](https://github.com/AnthusAI/Humanus/commit/94a121bc75dbe5d53e6e55f02deae11cf5ca2523))

Confession article is the gate after the 8444 truncation reject.

- **kanbus**: Lim-79c9b2 live acceptance reject
  ([`18e7d67`](https://github.com/AnthusAI/Humanus/commit/18e7d67c3a4f954028c8f3951b8ade17bb45d227))

Confession article still truncated; budget must not key off draft length.

- **kanbus**: Lim-79c9b2 PR #9 opened, live acceptance
  ([`90dc7ec`](https://github.com/AnthusAI/Humanus/commit/90dc7ec3380ad5a957fd77a4c893f54c2aac8141))

Unit review passed; merge waits on --require-judge against published copy.


## v0.13.0 (2026-09-10)

### Chores

- **kanbus**: Close LIM-0cd8bf after PR #8 merge
  ([`305f428`](https://github.com/AnthusAI/Humanus/commit/305f42843b2920426157177a4b419dc9c3758e7a))

Judge prompt v2 landed on main; HITL re-scan can use house voice.

- **kanbus**: Close LIM-6a6da3 after Papyrus PR #75
  ([`5937dd6`](https://github.com/AnthusAI/Humanus/commit/5937dd6be804282e059c97359a65b606557fc3c0))

Judge enabled on the Pilobolus style profile via develop merge.

### Features

- **judge**: Send full voice config in judge prompt (v2)
  ([#8](https://github.com/AnthusAI/Humanus/pull/8),
  [`eaf54aa`](https://github.com/AnthusAI/Humanus/commit/eaf54aac9542d014b8fc0ca4f71cb11969d239a1))

Extend build_judge_user_prompt with sentenceStyle, voicePatterns, structure, and 500-character
  reference excerpts. Bump JUDGE_PROMPT_VERSION and canary pin; add Behave and unit tests without
  live OpenAI.


## v0.12.1 (2026-09-10)

### Bug Fixes

- **judge**: Include rubric in OpenAI structured output required fields
  ([#7](https://github.com/AnthusAI/Humanus/pull/7),
  [`684c5f3`](https://github.com/AnthusAI/Humanus/commit/684c5f34859f679d40df58d3b49b364edf112078))

OpenAI Responses rejects schemas when properties keys are missing from required. Align root required
  with findings and rubric; add unit test.

### Chores

- **kanbus**: Agent steers findings; human steers options and feel
  ([`0a50a06`](https://github.com/AnthusAI/Humanus/commit/0a50a0691a71e6a200180b0fd7eb727e6de13dba))

- **kanbus**: Authorize judge schema fix and voice prompt
  ([`7b1fb27`](https://github.com/AnthusAI/Humanus/commit/7b1fb2775a3a7068df545bf3c31b154a423e6c36))

- **kanbus**: Authorize Pilobolus judge profile implementation
  ([`7d6361d`](https://github.com/AnthusAI/Humanus/commit/7d6361de690098a6d8ffb964a4c1d98c85217b30))

- **kanbus**: Close LIM-c31ac3 after PR #7 merge
  ([`1d6ff93`](https://github.com/AnthusAI/Humanus/commit/1d6ff93253e81b39585084e3a2a69a9fc3c10dc4))

- **kanbus**: File HITL dogfood for published Pilobolus
  ([`2766bf5`](https://github.com/AnthusAI/Humanus/commit/2766bf5288d64218d7b03679df1ebd2791f43369))

- **kanbus**: Fill LIM-ed02c3 redundancy dogfood story
  ([`8e3a28e`](https://github.com/AnthusAI/Humanus/commit/8e3a28e763398874c466cff13cd3ad5a7d478230))

- **kanbus**: Lim-6a6da3 Papyrus PR #75 opened
  ([`26fa22e`](https://github.com/AnthusAI/Humanus/commit/26fa22e0a876563ecd4b0bd6765c510270e6642d))

- **kanbus**: Live OpenAI judge schema 400 on rubric
  ([`b84c3df`](https://github.com/AnthusAI/Humanus/commit/b84c3dffda73c6f009b3953ffbedb60bda4da938))


## v0.12.0 (2026-09-10)

### Chores

- **kanbus**: Authorize LIM-d895df canary implementation
  ([`f088427`](https://github.com/AnthusAI/Humanus/commit/f0884275a9aac7f216a1ff1ce4137e4881b640be))

- **kanbus**: Close LIM-d895df and LIM-df9d58 after PR #6
  ([`fdf771e`](https://github.com/AnthusAI/Humanus/commit/fdf771e0c6591785aae9f6d6456710da93626e68))

- **kanbus**: Lim-d895df PR #6 opened; acceptance in flight
  ([`d01c0f1`](https://github.com/AnthusAI/Humanus/commit/d01c0f1b02e3d0cccc06bfd95ef1a6b1a87731f3))

### Features

- **canary**: Add judge calibration fixture runner (LIM-ca93ca)
  ([#6](https://github.com/AnthusAI/Humanus/pull/6),
  [`2f8e225`](https://github.com/AnthusAI/Humanus/commit/2f8e2257654be515a0406bfa8d6aaedfa283758d))

Introduce limatus canary with a small checked-in manifest, fixture judge resolver, and calibration
  pins for JUDGE_PROMPT_VERSION and Terra default model. Complements the offline eval harness
  without replacing it.


## v0.11.0 (2026-09-10)

### Chores

- **kanbus**: Authorize LIM-e9176a agent-loop implementation
  ([`648fffa`](https://github.com/AnthusAI/Humanus/commit/648fffa7c8a7f0dbb5f4b97b1ad272f2ef6dc286))

- **kanbus**: Close LIM-e9176a; start LIM-d895df canary plan
  ([`03a6f6f`](https://github.com/AnthusAI/Humanus/commit/03a6f6fda537e613fc0a7722ec3b22b9e79c1a70))

- **kanbus**: Lim-e9176a acceptance passed; PR pending
  ([`ab9a910`](https://github.com/AnthusAI/Humanus/commit/ab9a9107915033311251797b48d72c4ab9c0c2ed))

### Features

- **editorial**: Agent copy-edit loop wiring (LIM-e9176a)
  ([#5](https://github.com/AnthusAI/Humanus/pull/5),
  [`f657e28`](https://github.com/AnthusAI/Humanus/commit/f657e286c8cef805fa0ecc34194df1aa56f9105b))

Add read-only patch preview and compare candidate expansion, plus compose_loop_record for audit
  bundles. Ship Behave contracts for explicit finding decisions and agent shortlist before human
  apply.


## v0.10.0 (2026-09-10)

### Chores

- **kanbus**: Close LIM-0e3f4e; start LIM-e9176a loop plan
  ([`08a602e`](https://github.com/AnthusAI/Humanus/commit/08a602e013273f78132d0ffd778b8a442db0d2d9))

- **kanbus**: Lim-0e3f4e PR #4 opened; acceptance in flight
  ([`9f4f42b`](https://github.com/AnthusAI/Humanus/commit/9f4f42bbdb3ce714eca4b164174fc632a41547da))

### Features

- **compare**: Rank candidates with always-lane deltas (LIM-0e3f4e)
  ([#4](https://github.com/AnthusAI/Humanus/pull/4),
  [`f3b2c15`](https://github.com/AnthusAI/Humanus/commit/f3b2c15ba459c197015cafb1e42f2a48da59a9a2))

Add limatus compare for multi-candidate ranking and regression mode with inspectable finding-count
  deltas, hard constraints on unsupported-claim increases, and optional rubric deltas when judge
  rubric is present.

verify and sdk.verify remain compatibility aliases that run compare regression before emitting the
  legacy advisory JSON.


## v0.9.0 (2026-09-10)

### Chores

- **kanbus**: Authorize LIM-0e3f4e compare implementation
  ([`43d25ea`](https://github.com/AnthusAI/Humanus/commit/43d25eabc1a579e4fade7e9e2123dc16385081cb))

- **kanbus**: Authorize LIM-9440e9 always-lane implementation
  ([`313100e`](https://github.com/AnthusAI/Humanus/commit/313100ef79802dfd1d1970a71718b8b3f96fc23d))

- **kanbus**: Authorize LIM-f233fb OpenAI judge implementation
  ([`f15234a`](https://github.com/AnthusAI/Humanus/commit/f15234a6a5348134f66fb1e4f88d05b7e1abcdab))

- **kanbus**: Close LIM-9440e9 after PR #2 merge
  ([`687283d`](https://github.com/AnthusAI/Humanus/commit/687283dd92c62778815aa1b49bce43d80c0163af))

- **kanbus**: Close LIM-f233fb after PR #3 merge
  ([`2f5057b`](https://github.com/AnthusAI/Humanus/commit/2f5057b3e9c57d35d5812ca0ea4e264085892367))

- **kanbus**: Lim-9440e9 acceptance passed; PR blocked on project/ files
  ([`e657289`](https://github.com/AnthusAI/Humanus/commit/e6572890717ce6c885ffc64076c5908c701ad26b))

- **kanbus**: Lim-f233fb acceptance rejected on missing Behave step
  ([`1e03d72`](https://github.com/AnthusAI/Humanus/commit/1e03d725f0fc6cb027cdc3fa14f47292dd4a20b1))

- **kanbus**: Re-accept LIM-f233fb; start LIM-0e3f4e compare plan
  ([`feaf8b2`](https://github.com/AnthusAI/Humanus/commit/feaf8b2b18819b0fe64aafb24c83162f0f185938))

- **kanbus**: Send LIM-9440e9 plan back for missing worktree
  ([`e51fd15`](https://github.com/AnthusAI/Humanus/commit/e51fd155b102528aacf93f01086c1075b1fdf275))

### Features

- **judge**: Configured OpenAI judge lane (LIM-f233fb)
  ([#3](https://github.com/AnthusAI/Humanus/pull/3),
  [`07bd9a8`](https://github.com/AnthusAI/Humanus/commit/07bd9a86b8b1a4d3ba83b0cd978dc521ded591f9))

* feat(judge): configured OpenAI judge lane (LIM-f233fb)

Wire live OpenAI judge when OPENAI_API_KEY is set, Terra default model, optional 1-5 rubric
  dimensions, union with profile findings, and --require-judge for hard-fail when the judge cannot
  run. Add verbatim Behave stories and mocked unit coverage; CI stays green without secrets.

* fix(test): register judge findings absent Behave step (LIM-f233fb)

Restore `when` import so editorial_judge_steps loads, and bind "judge findings are absent" to the
  existing no-judge-findings assertion.

### Testing

- **editorial**: Behave always-lane voice-local and density scenarios
  ([#2](https://github.com/AnthusAI/Humanus/pull/2),
  [`b0e9f01`](https://github.com/AnthusAI/Humanus/commit/b0e9f0147e0434a32bce942142b3422e184b25b5))

Add Kanbus LIM-0fa50c and LIM-cebc08 Gherkin with fixtures that prove scan findings differ per
  profile bans and skip document-level density flags for house-voice and sub-minWords drafts.


## v0.8.0 (2026-09-10)

### Chores

- **kanbus**: Approve LIM-3e6cb0 plan; implementation authorized
  ([`b639a9b`](https://github.com/AnthusAI/Humanus/commit/b639a9b8c6f39738dab299f478ac78ed8f8ee522))

- **kanbus**: Close LIM-3e6cb0; start always-lane and judge epics
  ([`6deaec3`](https://github.com/AnthusAI/Humanus/commit/6deaec311735be7876903040a96ea35ca9e472a1))

- **kanbus**: Commit board state (issues)
  ([`3158f61`](https://github.com/AnthusAI/Humanus/commit/3158f61aaae908bc2f316228abf8a747ee195471))

- **kanbus**: File LIM-df9d58 scan/judge/compare initiative
  ([`b51206c`](https://github.com/AnthusAI/Humanus/commit/b51206c01752dfa071e9c67e502070f414a262b2))

New initiative with six epics and behavioral stories for the agent-first copy-edit loop. Notes
  successor relationship to LIM-9d14e6.

- **kanbus**: Include event log for board updates
  ([`6755c31`](https://github.com/AnthusAI/Humanus/commit/6755c31ca0a885ff941f45451729d6c7057cb532))

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>

- **kanbus**: Start LIM-3e6cb0 unified scan; planner dispatched
  ([`f692f67`](https://github.com/AnthusAI/Humanus/commit/f692f6744941f1ff0047e1781a2f8a7e7ec36bb4))

### Features

- **scan**: Unified scan surface with finding provenance (LIM-3e6cb0)
  ([#1](https://github.com/AnthusAI/Humanus/pull/1),
  [`0efd3d6`](https://github.com/AnthusAI/Humanus/commit/0efd3d6db90b3104b5512f2ab0c050e745cd7d20))

* feat(scan): unified scan surface with finding provenance (LIM-3e6cb0)

Add limatus scan as the agent-facing entrypoint with diagnose as an alias, profile/judge source
  fields on findings, stub judge lane with injectable resolver for tests, and Behave coverage for
  the epic acceptance scenarios.

* docs(cli): list scan as primary command in --help text


## v0.7.0 (2026-09-10)

### Features

- Add uncontractedForms check for stated-but-unchecked contraction rules
  ([`ebc3f9a`](https://github.com/AnthusAI/Humanus/commit/ebc3f9ad52568e1b503f0051161fb697063885b8))

Caught dogfooding: "That is the same thrift family" shipped in an Anth.us post despite the profile's
  own sentenceStyle explicitly saying "Use contractions and active voice." A prose rule that isn't
  checked gets violated by default, since uncontracted phrasing is exactly what a careful, formal
  draft reaches for without anyone noticing.

checks.uncontractedForms (on by default) flags formal two-word constructions (that is, it is, do
  not, cannot, ...) against their common contraction. Skips the appositive/clarifying "that is,"
  (the "i.e." sense), where contracting would change the meaning.

This needs to vary by publication, not just by individual judgment call: Pilobolus's own VOICE.md
  says the impersonal narrator deliberately avoids contracting ("the narrator stays cool and
  strange"), confirmed against all five of its published articles, so its profile now sets
  uncontractedForms: false. That's a deterministic, profile-level switch -- not left to an agent to
  decide per piece.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>


## v0.6.0 (2026-09-09)

### Features

- Add overusedWords check for crutch-word repetition
  ([`80dabed`](https://github.com/AnthusAI/Humanus/commit/80dabed4b65c9ab1d9bef197c048f84511aa273e))

Caught dogfooding: the Anth.us article this session wrote about Limatus itself used "actually" seven
  times in under a thousand words, and diagnose didn't flag it, because "actually" isn't on anyone's
  bannedIntensifiers list -- it's ordinary English, just not in that quantity. The gap is
  structural: every existing rule-based check requires a publication to name the exact word in
  advance.

checks.overusedWords (on by default) checks a small built-in list of common hedges and crutch words
  (actually, really, very, basically, essentially, literally, simply, clearly, obviously) against
  their own frequency in the document, scaled to length, rather than a fixed per-profile ban list. A
  couple of uses is normal English; seven in a thousand words is a tell no publication should have
  to enumerate by hand.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>


## v0.5.1 (2026-09-09)

### Bug Fixes

- Verify() no longer treats frontmatter edits as factual changes
  ([`1894b0c`](https://github.com/AnthusAI/Humanus/commit/1894b0ce454f9c4eea2dede8095198c0feb69143))

diagnose_draft masks a leading YAML frontmatter block before checking prose, but verify_revision
  never did the same for its own text-scanning helpers (_findings, _factual_change_risk,
  _score_draft). Editing a draft's title, date, or description -- normal copyediting -- showed up as
  a "deleted_claim" (the old frontmatter block read as prose that disappeared) and inflated
  factual_change_risk, even when the body was untouched. Found dogfooding verify() on a real
  copy-edit.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>


## v0.5.0 (2026-09-09)

### Features

- Add check_rules for pattern-only checks on non-prose text
  ([`62a2049`](https://github.com/AnthusAI/Humanus/commit/62a2049417a0f17993f7a2a628ec07533ea183c0))

diagnose() runs the full heuristic suite -- cadence, redundancy, vague claims, density -- which is
  right for articles but wrong for text that isn't prose at all: a raw .tsx component source, a
  page-content.ts copy string. Those need only the explicit rules (banned phrases/intensifiers/
  patterns, no-emoji, contrast cap), not heuristics tuned for real sentences misfiring on code
  shape.

check_rules_only()/check_rules() run just the rules portion of the pipeline. This is the last piece
  needed to let Chattic.us-web's bespoke check_editorial_rules.py -- the script that inspired
  Limatus in the first place -- call Limatus directly across all three of its surfaces (articles,
  page-content.ts, component sources) instead of maintaining its own duplicate implementation of the
  same rules.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>


## v0.4.0 (2026-09-08)

### Chores

- **kanbus**: Commit board state (issues)
  ([`c3e3c68`](https://github.com/AnthusAI/Humanus/commit/c3e3c6853af0e34ee49076f9db399c54d9711074))

- **kanbus**: Record live suggestion dogfood
  ([`23d12e3`](https://github.com/AnthusAI/Humanus/commit/23d12e32f66e9c4772f6c476258e19c6dfb0fb68))

### Features

- Add no-emoji ban, per-surface contrast caps, and standfirst checks
  ([`3bfc969`](https://github.com/AnthusAI/Humanus/commit/3bfc969337997e4ff6c04976cdffa80929149109))

Extends the style-profile schema so a single profile can cover what a hand-rolled per-site editorial
  checker was covering separately:

- rules.noEmojis: bans emoji characters outright, checked the same way as banned
  phrases/intensifiers. - rules.bySurface: lets one profile give specific surfaces (marketing,
  legal, etc.) a looser or fully disabled contrast cap instead of forking the whole profile per
  surface. Threaded through diagnose_draft, the CLI's --surface flag, and the SDK's diagnose(). - A
  new standfirst schema block and `limatus standfirst` command/SDK function: checks the parts of a
  good standfirst a script can actually decide -- length, whether it names somebody the reader
  hasn't met yet (capitalized-word heuristic, cross-referenced against an allowlist),
  insider-vocabulary terms and patterns, and how much it overlaps with the article's description.
  Lets a copywriting agent iterate on a candidate sentence before it's written to a file, the way a
  real editorial gate already worked at Chattic.us-web -- ported and generalized from that repo's
  bespoke check_editorial_rules.py rather than reinvented, so a publication doesn't need a one-off
  script to get the same coverage.

Adds features/editorial-surface-rules.feature and features/editorial-standfirst.feature (9 new
  scenarios) alongside a dedicated fixture profile.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>


## v0.3.2 (2026-09-08)

### Bug Fixes

- Handle whole-document suggestion truncation
  ([`74afdf5`](https://github.com/AnthusAI/Humanus/commit/74afdf59e311e60d6b8ec478fdbb12476e03e656))

- **kanbus**: Record safety filter false positive
  ([`5304a89`](https://github.com/AnthusAI/Humanus/commit/5304a89e7bf2d113be629d4dc29345190cad338a))

### Chores

- **kanbus**: Commit board state (issues)
  ([`c5f17f2`](https://github.com/AnthusAI/Humanus/commit/c5f17f202e6986f39ec4e101b48ee65cdce7bf2d))

- **kanbus**: Commit board state (issues)
  ([`f0ca108`](https://github.com/AnthusAI/Humanus/commit/f0ca108951bba24d9bb6ec18e1889a1cb22890d7))


## v0.3.1 (2026-09-08)

### Bug Fixes

- **kanbus**: Record holistic suggestion truncation
  ([`ef04896`](https://github.com/AnthusAI/Humanus/commit/ef04896cf5839ea349ef482c6edc7bf93822b4f0))

### Chores

- **kanbus**: Commit board state (issues)
  ([`9fa242c`](https://github.com/AnthusAI/Humanus/commit/9fa242c1544aa756e1dbd8be0d8b6b19e64c4b8c))

- **kanbus**: Commit board state (issues)
  ([`7622752`](https://github.com/AnthusAI/Humanus/commit/7622752d1039cc45097394e07f214f933c6ac7ba))

- **kanbus**: Commit board state (issues)
  ([`fc3864b`](https://github.com/AnthusAI/Humanus/commit/fc3864bf81268918af31dfb507e15c5319089e1e))

- **kanbus**: Commit board state (issues)
  ([`65ebcee`](https://github.com/AnthusAI/Humanus/commit/65ebceeac4e93d05983c52e454625108102d14b0))

- **kanbus**: Commit board state (issues)
  ([`e3ca50a`](https://github.com/AnthusAI/Humanus/commit/e3ca50aef3106f08ccc5692cfa14fc899b666133))

- **kanbus**: Commit board state (issues)
  ([`3610f56`](https://github.com/AnthusAI/Humanus/commit/3610f56910eff0085fb29634a276e25ca7cc52c6))

- **kanbus**: Commit board state (issues)
  ([`baddef1`](https://github.com/AnthusAI/Humanus/commit/baddef128a9f65bd970cec92503f6947ee393ea8))

- **kanbus**: Complete composable suggestions
  ([`4e22ff1`](https://github.com/AnthusAI/Humanus/commit/4e22ff1e7bdec0c7c1d6ba49bd2d195d033e9c43))

- **kanbus**: Complete revision verifier
  ([`e189c10`](https://github.com/AnthusAI/Humanus/commit/e189c1080da78223b73c1498827527b2ffdc31b6))

- **kanbus**: Make editorial suggestions composable
  ([`16592d9`](https://github.com/AnthusAI/Humanus/commit/16592d90b83378f858c60d0c406e350d8f083016))

- **kanbus**: Make holistic suggestions standard
  ([`3e2df23`](https://github.com/AnthusAI/Humanus/commit/3e2df23f90719a07d84acdc826e064f52d53f989))

- **kanbus**: Record initial live-content dogfood
  ([`3a36556`](https://github.com/AnthusAI/Humanus/commit/3a36556a41990bf79e23a38c28df774f0ebbadac))

- **kanbus**: Reframe holistic suggestions
  ([`0c6a811`](https://github.com/AnthusAI/Humanus/commit/0c6a811348c89ef07b01bfa916abc1ec80b605c2))


## v0.3.0 (2026-09-08)

### Chores

- **kanbus**: Commit board state (issues)
  ([`161b66f`](https://github.com/AnthusAI/Humanus/commit/161b66f31a704168bf41f863315799f164202866))

- **kanbus**: Commit board state (issues)
  ([`1191cdb`](https://github.com/AnthusAI/Humanus/commit/1191cdb993ee35962e7d704a253717d9b0b9280d))

- **kanbus**: Record completed Luna tasks
  ([`d73b09e`](https://github.com/AnthusAI/Humanus/commit/d73b09e5524fcacabe72166d642a620a935ef403))

- **kanbus**: Record task planning events
  ([`0c0ad94`](https://github.com/AnthusAI/Humanus/commit/0c0ad943170bc5d6523ddfe22c69aa6381e25fca))

### Documentation

- Document portable style profiles
  ([`183ca5b`](https://github.com/AnthusAI/Humanus/commit/183ca5b4b936f49696caca0cf10a2c279eeaf445))

### Features

- Expose public Limatus Python SDK
  ([`3c8858f`](https://github.com/AnthusAI/Humanus/commit/3c8858ffef52bde0ba525709e3a3a220891aced1))


## v0.2.0 (2026-09-08)

### Features

- Add --version/-V flag to the CLI
  ([`5676f91`](https://github.com/AnthusAI/Humanus/commit/5676f91d747517b9832f887cccc642dc185fcef7))

Also serves as the first real conventional-commit release, to verify the python-semantic-release +
  PyPI trusted-publishing pipeline end to end now that the trusted publisher is registered on PyPI.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>


## v0.1.0 (2026-09-08)

### Bug Fixes

- Restore correct starting version after semantic-release misfire
  ([`160dac3`](https://github.com/AnthusAI/Humanus/commit/160dac300c3ed4d8ca5a09722b82dca0cd4f4f37))

python-semantic-release computed its first release purely from conventional-commit history and found
  none, so it defaulted to 0.0.0 and overwrote the version already recorded in pyproject.toml and
  __init__.py, rather than treating that as the starting point. Restores 0.1.0 in both places and
  drops the CHANGELOG.md it generated for the bogus release so a real one gets built cleanly from
  here.

Also drops the defensive "not pytest" framing from the README's Testing section -- naming a tool we
  don't use is a comparison nobody asked for, not information a reader needs.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>

### Chores

- **kanbus**: Commit board state (issues)
  ([`fe51d99`](https://github.com/AnthusAI/Humanus/commit/fe51d9901fe55980f97a45338e62de26a265277d))

- **kanbus**: Commit board state (issues)
  ([`d92775c`](https://github.com/AnthusAI/Humanus/commit/d92775c96f4a6b6e79126b3ab93453d6e847def9))
