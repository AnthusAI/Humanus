"""Starter policy packs shipped with Humanus.

A CMS copies a starter pack's policies into its own store, where editors can
change them; Humanus itself never merges packs at check time.
"""
from __future__ import annotations

from importlib import resources
from typing import Any

import yaml


def list_builtin_packs() -> list[str]:
    """Names of the starter packs, e.g. ``["ai-writing-tells"]``."""
    return sorted(
        entry.name.removesuffix(".yml")
        for entry in resources.files(__name__).iterdir()
        if entry.name.endswith(".yml")
    )


def builtin_pack(name: str) -> dict[str, Any]:
    """Return a starter pack as a ``policy-pack-v1`` payload."""
    if name not in list_builtin_packs():
        raise KeyError(f"Unknown built-in pack '{name}'. Known: {', '.join(list_builtin_packs())}")
    return yaml.safe_load(resources.files(__name__).joinpath(f"{name}.yml").read_text(encoding="utf-8"))
