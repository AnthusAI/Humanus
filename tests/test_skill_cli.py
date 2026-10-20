from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from limatus.cli import main
from limatus.skill import load_skill_bytes


ROOT = Path(__file__).resolve().parents[1]
ENV = {**os.environ, "PYTHONPATH": str(ROOT / "src")}


def test_skill_stdout_matches_packaged_resource():
    expected = load_skill_bytes()
    completed = subprocess.run(
        [sys.executable, "-m", "limatus", "skill"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        env=ENV,
    )
    assert completed.stdout == expected


def test_skill_stdout_includes_frontmatter_and_heading():
    completed = subprocess.run(
        [sys.executable, "-m", "limatus", "skill"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
        env=ENV,
    )
    assert "name:" in completed.stdout
    assert "# Limatus editorial checks" in completed.stdout


def test_help_mentions_skill():
    assert main(["-h"]) == 0
    from limatus import cli

    assert "limatus skill" in (cli.__doc__ or "")
