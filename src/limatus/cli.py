"""Limatus CLI entry point.

    limatus check --request <check-request.json> | --draft <file> --pack <policy-pack.yml> [--output FILE]
    limatus suggest --request <suggest-request.json>          (rewrite options; needs OPENAI_API_KEY)
    limatus draft-questions --request <draft-questions-request.json>
    limatus calibrate --labels <feedback-labels.json>          (per-detector calibration from editor decisions)
    limatus schema policy-pack-v1|check-request-v1|check-result-v1|finding-v1|suggest-request-v1|suggest-result-v1
    limatus pack import --profile <style-profile.yml> [--version V] [--output FILE]
    limatus pack validate <policy-pack.yml>
    limatus pack builtin [name]   (list or print starter packs, e.g. ai-writing-tells)
    limatus scan --draft <file> --profile <style-profile.yml> [--require-judge] [...]
    limatus decide --finding-id finding-<hex> --decision skip|rewrite|delete|keep|add \\
                   [--note TEXT] --decisions <decisions.json>
    limatus options  --draft <file> --profile <style-profile.yml> \\
                      --diagnosis <diagnosis.json> --decisions <decisions.json> \\
                      --skill <editorial-rewrite-skill.yml> [...]
    limatus compare --profile <style-profile.yml> --baseline <file> --candidate <file> [...]
    limatus apply --original <file> --working-copy <file> --options <options.json> [...]
    limatus diff --original <file> --working-copy <file> [...]
    limatus verify --original <file> --working-copy <file> --profile <style-profile.yml> [...]
    limatus headline options --job title|subtitle --working-copy <file> --profile <style-profile.yml> \\
                             --skill <editorial-rewrite-skill.yml> [...]
    limatus usability scan --page FILE.html --profile FILE.yml [--output findings.json]
    limatus eval --manifest <editorial-corpus/manifest.yml>
    limatus canary --manifest <editorial-canary/manifest.yml>
    limatus skill   (print the packaged copy-edit Agent Skill for agents)
    limatus diagnose  (alias for scan)

Agents should run `limatus skill` for the full copy-edit workflow skill.
See editorial_commands.py for each subcommand's full flag set.
"""
from __future__ import annotations

import sys

from . import __version__
from .editorial_judge import JudgeUnavailableError
from .editorial_style import StyleProfileValidationError
from .editorial_commands import (
    editorial_apply,
    editorial_decide,
    editorial_diagnose,
    editorial_diff,
    editorial_options,
    editorial_compare,
    editorial_scan,
    editorial_headline,
    editorial_standfirst,
    editorial_verify,
)
from .contract_commands import (
    contract_calibrate,
    contract_check,
    contract_draft_questions,
    contract_pack,
    contract_schema,
    contract_suggest,
)
from .suggest import SuggestUnavailableError
from .editorial_canary import main as editorial_canary
from .editorial_eval import main as editorial_eval
from .skill import load_skill_bytes
from .usability_commands import editorial_usability
from .usability_profile import UsabilityProfileValidationError


def editorial_skill(flags: list[str]) -> None:
    if flags and flags[0] in {"-h", "--help"}:
        print("limatus skill — print the packaged copy-edit Agent Skill (SKILL.md)")
        return
    sys.stdout.buffer.write(load_skill_bytes())


COMMANDS = {
    "check": contract_check,
    "suggest": contract_suggest,
    "draft-questions": contract_draft_questions,
    "calibrate": contract_calibrate,
    "schema": contract_schema,
    "pack": contract_pack,
    "scan": editorial_scan,
    "diagnose": editorial_diagnose,
    "decide": editorial_decide,
    "options": editorial_options,
    "apply": editorial_apply,
    "diff": editorial_diff,
    "compare": editorial_compare,
    "verify": editorial_verify,
    "headline": editorial_headline,
    "usability": editorial_usability,
    "standfirst": editorial_standfirst,
    "eval": editorial_eval,
    "canary": editorial_canary,
    "skill": editorial_skill,
}


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if not args or args[0] in {"-h", "--help"}:
        print(__doc__)
        return 0
    if args[0] in {"-V", "--version"}:
        print(f"limatus {__version__}")
        return 0

    command, flags = args[0], args[1:]
    handler = COMMANDS.get(command)
    if handler is None:
        print(f"limatus: unknown command '{command}'. Try one of: {', '.join(sorted(COMMANDS))}")
        return 1

    try:
        result = handler(flags)
    except (
        StyleProfileValidationError,
        UsabilityProfileValidationError,
        JudgeUnavailableError,
        SuggestUnavailableError,
        ValueError,
    ) as exc:
        print(f"limatus: {exc}", file=sys.stderr)
        return 1
    return result if isinstance(result, int) else 0


if __name__ == "__main__":
    sys.exit(main())
