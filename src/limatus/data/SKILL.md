---
name: limatus-editorial-checks
description: Check prose against a publication's editorial policy pack with Limatus (rule and decision-model findings with exact spans), get rewrite options for a finding or any passage, draft classifier questions for a policy, calibrate from editors' decisions, and run read-only HTML usability scans. Never apply a rewrite the human did not choose; never edit the draft in place unless asked.
---

# Limatus editorial checks

Use this skill when an agent (or a human with agent help) copy-edits prose against a publication's own editorial policies. Limatus finds problems and offers rewrites; a person decides what changes. Run `limatus skill` any time to re-read this document.

## Principles

- **Policies come from the publication.** A *policy pack* (`limatus schema policy-pack-v1`) holds the policies; Limatus stores none. Get the pack from the CMS (Papyrus: `papyrus editorial pack`) or convert a legacy style profile with `limatus pack import`.
- **Check is read-only.** `check` returns findings with spans; it never changes the draft.
- **Two lanes find problems.** The *rules* lane (phrases, patterns, built-in checks) is deterministic. The *classifier* lane asks a decision model (TypeSafe Jev) each policy's question about every sentence, paragraph or the whole document; its findings carry a probability, and `status: review` means "unsure, a person should decide".
- **Generative models only suggest.** `suggest` (rewrites) and `draft-questions` (policy authoring) use an LLM; nothing an LLM writes is applied automatically.
- **Facts stay.** Prefer options that fix the finding without adding facts, numbers, names, quotes or experiences. Options with `factVerificationRequired: true` change a claim: verify before using.
- **Spans are UTF-16.** Offsets count UTF-16 code units, as JavaScript does. In Python, convert before slicing text that contains emoji or other astral characters.

## Workflow

1. **check**: `limatus check --draft draft.md --pack pack.json` (or `--request check-request.json`). Read `findings` (policy, severity, message, excerpt, span, probability) and `lanes` (did the classifier run, partially, or not at all).
2. **suggest**: for a finding or a selected span, `limatus suggest --request suggest-request.json` returns up to three options for the finding's whole sentence (or the exact selection). Pass an editor note in `options.instructions` ("shorter", "less formal").
3. **choose**: show the options to the human; apply exactly the one they pick, replacing `span` in the draft (or a working copy).
4. **check again**: findings ids are stable for unchanged sentences, so dismissals carry over.
5. **learn** (CMS side): record accepted / fixed / dismissed decisions; `limatus calibrate --labels labels.json` fits per-detector calibration to store on the pack's detectors.

Policy authoring: `limatus draft-questions --request draft-questions-request.json` proposes classifier detectors for a policy written in prose; review them before adding them to the pack. `limatus pack builtin ai-writing-tells` prints a starter pack of AI-writing tells.

## HTML usability

Use this path for static HTML pages (landing pages, articles rendered to HTML)—not for markdown copy-edit drafts. It is **read-only**: Limatus reports findings; it does not rewrite the page. There is no `usability options`, `usability apply`, or other usability write commands.

The profile is a **usability profile** (thresholds for contrast, tap targets, focus visibility, etc.). It is **not** an editorial policy pack.

```bash
python -m limatus usability scan --page FILE.html --profile FILE.yml [--output findings.json]
```

Structured finding kinds include:

- `missing_alt`
- `low_contrast`
- `small_tap_target`
- `suppressed_focus_outline`
- `missing_accessible_name`
- `missing_lang`
- `emoji_heading`
- `generic_gradient_hero`
- `generic_feature_row`

Route usability findings to human or design-system fixes outside editorial checks.

## Agent steering

- Read each policy's guidance and rewrite guidance before suggesting or choosing.
- Do not apply an option the human did not pick, and do not "fix" `review` findings without asking.
- Do not loosen a policy (disable it, raise a threshold) to make a draft pass; report instead.
