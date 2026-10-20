"""CLI commands for the policy-pack contracts: ``check``, ``schema`` and ``pack``."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from .calibration import calibrate
from .check import check
from .contracts import CONTRACT_SCHEMAS, load_schema
from .packs import builtin_pack, list_builtin_packs
from .policy_pack import load_policy_pack
from .style_profile_import import policy_pack_from_style_profile
from .suggest import draft_questions, suggest


def contract_check(flags: list[str]) -> int:
    parser = argparse.ArgumentParser(
        prog="limatus check",
        description="Check a document against a policy pack and print a check-result-v1 document.",
    )
    parser.add_argument("--request", help="check-request-v1 JSON file")
    parser.add_argument("--draft", help="document to check (instead of --request)")
    parser.add_argument("--pack", help="policy pack JSON/YAML file (with --draft)")
    parser.add_argument("--format", default="markus", choices=["markus", "markdown", "text"])
    parser.add_argument("--output", help="write the result here instead of stdout")
    args = parser.parse_args(flags)

    if args.request:
        request = json.loads(Path(args.request).read_text(encoding="utf-8"))
    elif args.draft and args.pack:
        request = {
            "schemaVersion": 1,
            "content": {"format": args.format, "text": Path(args.draft).read_text(encoding="utf-8")},
            "pack": _read_structured(Path(args.pack)),
        }
    else:
        parser.error("give --request, or --draft with --pack")
    _emit(check(request), args.output)
    return 0


def contract_suggest(flags: list[str]) -> int:
    parser = argparse.ArgumentParser(
        prog="limatus suggest",
        description="Rewrite options for a finding or selection (suggest-request-v1 in, suggest-result-v1 out). Needs OPENAI_API_KEY.",
    )
    parser.add_argument("--request", required=True, help="suggest-request-v1 JSON file")
    parser.add_argument("--output", help="write the result here instead of stdout")
    args = parser.parse_args(flags)
    _emit(suggest(json.loads(Path(args.request).read_text(encoding="utf-8"))), args.output)
    return 0


def contract_draft_questions(flags: list[str]) -> int:
    parser = argparse.ArgumentParser(
        prog="limatus draft-questions",
        description="Draft classifier detectors for a prose policy (draft-questions-request-v1 in). Needs OPENAI_API_KEY.",
    )
    parser.add_argument("--request", required=True, help="draft-questions-request-v1 JSON file")
    parser.add_argument("--output", help="write the result here instead of stdout")
    args = parser.parse_args(flags)
    _emit(draft_questions(json.loads(Path(args.request).read_text(encoding="utf-8"))), args.output)
    return 0


def contract_calibrate(flags: list[str]) -> int:
    parser = argparse.ArgumentParser(
        prog="limatus calibrate",
        description="Fit per-detector calibration from editor decisions (feedback-labels-v1 in, calibration-v1 out).",
    )
    parser.add_argument("--labels", required=True, help="feedback-labels-v1 JSON file")
    parser.add_argument("--output", help="write the result here instead of stdout")
    args = parser.parse_args(flags)
    _emit(calibrate(json.loads(Path(args.labels).read_text(encoding="utf-8"))), args.output)
    return 0


def contract_schema(flags: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="limatus schema", description="Print a published contract JSON Schema.")
    parser.add_argument("name", choices=CONTRACT_SCHEMAS)
    args = parser.parse_args(flags)
    _emit(load_schema(args.name), None)
    return 0


def contract_pack(flags: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="limatus pack", description="Work with policy packs.")
    commands = parser.add_subparsers(dest="command", required=True)
    importer = commands.add_parser("import", help="convert a style profile into a policy pack")
    importer.add_argument("--profile", required=True, help="style profile YAML/JSON")
    importer.add_argument("--version", help="pack version to record (default: dated import)")
    importer.add_argument("--output", help="write the pack here instead of stdout")
    validator = commands.add_parser("validate", help="validate a policy pack file")
    validator.add_argument("path")
    starter = commands.add_parser("builtin", help="list starter packs, or print one")
    starter.add_argument("name", nargs="?", help="starter pack to print")
    args = parser.parse_args(flags)

    if args.command == "import":
        _emit(policy_pack_from_style_profile(args.profile, version=args.version), args.output)
    elif args.command == "builtin":
        if args.name:
            _emit(builtin_pack(args.name), None)
        else:
            print("\n".join(list_builtin_packs()))
    else:
        pack = load_policy_pack(args.path)
        print(f"{pack.pack_id} {pack.version}: {len(pack.policies)} policies valid")
    return 0


def _read_structured(path: Path) -> Any:
    import yaml

    text = path.read_text(encoding="utf-8")
    return json.loads(text) if path.suffix.lower() == ".json" else yaml.safe_load(text)


def _emit(payload: Any, output: str | None) -> None:
    text = json.dumps(payload, indent=2, ensure_ascii=False) + "\n"
    if output:
        Path(output).write_text(text, encoding="utf-8")
    else:
        sys.stdout.write(text)
