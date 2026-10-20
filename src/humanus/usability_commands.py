from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .usability_profile import load_usability_profile
from .usability_scan import scan_html_page


def usability_scan(flags: list[str]) -> None:
    parser = argparse.ArgumentParser(prog="humanus usability scan")
    parser.add_argument("--page", required=True, help="Path to the HTML page (read-only).")
    parser.add_argument("--profile", required=True, help="Path to the usability profile YAML.")
    parser.add_argument("--output", default="", help="Optional path to write findings JSON.")
    args = parser.parse_args(flags)

    page_path = Path(args.page).resolve()
    if not page_path.is_file():
        raise ValueError(f"HTML page not found: {page_path}")
    page_html = page_path.read_text(encoding="utf-8")
    profile = load_usability_profile(Path(args.profile).resolve())
    result = scan_html_page(page_html, profile=profile)
    rendered = json.dumps(result, indent=2) + "\n"
    if args.output:
        Path(args.output).resolve().write_text(rendered, encoding="utf-8")
        return
    sys.stdout.write(rendered)


def editorial_usability(flags: list[str]) -> None:
    if not flags or flags[0] in {"-h", "--help"}:
        print("humanus usability scan --page FILE.html --profile FILE.yml [--output findings.json]")
        return
    if flags[0] != "scan":
        raise ValueError(f"Unknown usability subcommand '{flags[0]}'. Supported: scan")
    usability_scan(flags[1:])
