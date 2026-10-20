"""Packaged Agent Skill document for the copy-edit loop."""

from __future__ import annotations

from importlib.resources import files


def load_skill_bytes() -> bytes:
    return files("humanus.data").joinpath("SKILL.md").read_bytes()


def load_skill_text() -> str:
    return load_skill_bytes().decode("utf-8")
