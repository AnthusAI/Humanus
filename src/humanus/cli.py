"""Humanus CLI entry point.

    humanus check --request <check-request.json> | --draft <file> --pack <policy-pack.yml> [--format markus|markdown|text] [--output FILE]
    humanus suggest --request <suggest-request.json>          (rewrite options; needs OPENAI_API_KEY)
    humanus draft-questions --request <draft-questions-request.json>
    humanus calibrate --labels <feedback-labels.json>          (per-detector calibration from editor decisions)
    humanus pack import --profile <style-profile.yml> [--version V] [--output FILE]
    humanus pack validate <policy-pack.yml>
    humanus pack builtin [name]   (list or print starter packs, e.g. ai-writing-tells, asd-ste100, plain-language)
    humanus schema <name>         (print a contract JSON Schema)
    humanus usability scan --page FILE.html --profile FILE.yml [--output findings.json]
    humanus skill                 (print the packaged Agent Skill for agents)

The judgment (classifier) lane uses TypeSafe Jev when `humanus[jev]` is installed
and TYPESAFE_API_KEY is set.
"""
from __future__ import annotations

import sys

from . import __version__
from .contract_commands import (
    contract_calibrate,
    contract_check,
    contract_draft_questions,
    contract_pack,
    contract_schema,
    contract_suggest,
)
from .skill import load_skill_bytes
from .style_profile_import import StyleProfileImportError
from .suggest import SuggestUnavailableError
from .usability_commands import editorial_usability
from .usability_profile import UsabilityProfileValidationError


def print_skill(flags: list[str]) -> None:
    if flags and flags[0] in {"-h", "--help"}:
        print("humanus skill — print the packaged Agent Skill (SKILL.md)")
        return
    sys.stdout.buffer.write(load_skill_bytes())


COMMANDS = {
    "check": contract_check,
    "suggest": contract_suggest,
    "draft-questions": contract_draft_questions,
    "calibrate": contract_calibrate,
    "pack": contract_pack,
    "schema": contract_schema,
    "usability": editorial_usability,
    "skill": print_skill,
}


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if not args or args[0] in {"-h", "--help"}:
        print(__doc__)
        return 0
    if args[0] in {"-V", "--version"}:
        print(f"humanus {__version__}")
        return 0

    command, flags = args[0], args[1:]
    handler = COMMANDS.get(command)
    if handler is None:
        print(f"humanus: unknown command '{command}'. Try one of: {', '.join(sorted(COMMANDS))}")
        return 1

    try:
        result = handler(flags)
    except (StyleProfileImportError, UsabilityProfileValidationError, SuggestUnavailableError, ValueError) as exc:
        print(f"humanus: {exc}", file=sys.stderr)
        return 1
    return result if isinstance(result, int) else 0


if __name__ == "__main__":
    sys.exit(main())
