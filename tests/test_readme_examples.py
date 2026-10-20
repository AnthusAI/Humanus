"""The README's documented commands run as written."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
README = (ROOT / "README.md").read_text(encoding="utf-8")
ENV = {**os.environ, "PYTHONPATH": str(ROOT / "src")}
ENV.pop("TYPESAFE_API_KEY", None)


def _humanus(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run([sys.executable, "-m", "humanus", *args], cwd=ROOT, env=ENV, text=True, capture_output=True, check=True)


def test_starter_pack_then_check(tmp_path: Path) -> None:
    assert "humanus pack builtin ai-writing-tells > pack.json" in README
    assert "humanus check --draft draft.md --pack pack.json" in README
    pack = tmp_path / "pack.json"
    pack.write_text(_humanus("pack", "builtin", "ai-writing-tells").stdout, encoding="utf-8")
    draft = tmp_path / "draft.md"
    draft.write_text("# Notes\n\nCertainly! Our platform is a game-changer. Let's dive in.\n", encoding="utf-8")
    result = json.loads(_humanus("check", "--draft", str(draft), "--pack", str(pack)).stdout)
    assert result["offsetUnit"] == "utf16"
    assert {f["policyId"] for f in result["findings"]} >= {"chatbot-artifacts"}


def test_style_profile_import() -> None:
    assert "humanus pack import --profile style-profile.yml > pack.json" in README
    pack = json.loads(_humanus("pack", "import", "--profile", "features/fixtures/policy-pack/style-profile.yml").stdout)
    assert pack["schemaVersion"] == 1 and pack["policies"]
