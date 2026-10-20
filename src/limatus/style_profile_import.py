"""Convert a legacy style profile into an equivalent ``policy-pack-v1`` payload.

Mechanical controls (lexicon, banned phrases and patterns, checks) become
rules-lane detectors. Prose guidance (tone, sentence style, structure, voice
patterns, evidence rules) becomes guidance-only policies: they carry no
detector until someone writes a classifier question for them.
"""
from __future__ import annotations

import re
from datetime import date
from pathlib import Path
from typing import Any

from .editorial_style import DEFAULT_DIAGNOSE_CHECKS, load_style_profile

# Style-profile check names (camelCase) to builtin detector checks.
_CHECKS = {name: re.sub(r"(?<!^)(?=[A-Z])", "_", name).lower() for name in DEFAULT_DIAGNOSE_CHECKS}

_GUIDANCE_SECTIONS = (
    ("tone", "Tone", "tone"),
    ("sentence-style", "Sentence style", "sentence_style"),
    ("structure", "Structure", "structure"),
    ("voice-patterns", "Voice patterns", "voice_patterns"),
    ("evidence", "Evidence", "evidence_rules"),
)


def policy_pack_from_style_profile(path: str | Path, version: str | None = None) -> dict[str, Any]:
    """Read a style profile file and return a policy pack payload."""
    loaded = load_style_profile(path)
    profile = loaded.profile
    rules = profile.rules
    policies: list[dict[str, Any]] = []

    def add(policy_id: str, title: str, guidance: str, detectors: list[dict[str, Any]], severity: str = "warn") -> None:
        policies.append(
            {
                "id": policy_id,
                "version": 1,
                "title": title,
                "guidance": guidance,
                "severity": severity,
                "detectors": detectors,
            }
        )

    if profile.lexicon_avoid:
        guidance = "Avoid these words and phrases."
        if profile.lexicon_prefer:
            guidance += " Prefer: " + ", ".join(profile.lexicon_prefer) + "."
        add("avoid-lexicon", "Avoided lexicon", guidance, [_phrase("avoid-lexicon", profile.lexicon_avoid)])
    if rules.banned_phrases:
        add("banned-phrases", "Banned phrases", "Do not use these phrases.", [_phrase("banned-phrases", rules.banned_phrases)])
    if rules.banned_intensifiers:
        add(
            "banned-intensifiers",
            "Banned intensifiers",
            "Cut intensifiers that add emphasis without information.",
            [_phrase("banned-intensifiers", rules.banned_intensifiers)],
        )
    if rules.banned_patterns:
        add(
            "banned-patterns",
            "Banned patterns",
            "House patterns to rewrite.",
            [
                {"id": f"pattern-{index + 1}", "lane": "rules", "kind": "regex", "pattern": pattern, "message": message}
                for index, (pattern, message) in enumerate(rules.banned_patterns)
            ],
        )
    for index, (from_phrase, to_phrase) in enumerate(rules.preferred_phrasing):
        add(
            f"prefer-{_slug(to_phrase) or index + 1}",
            f"Prefer “{to_phrase}”",
            f"Prefer “{to_phrase}” over “{from_phrase}”.",
            [{**_phrase("preferred-phrasing", (from_phrase,)), "replacement": to_phrase}],
            severity="info",
        )

    builtins = [_builtin(name, profile) for name, enabled in profile.checks.items() if enabled]
    if rules.contrast_cap is not None:
        builtins.append({"id": "contrast-cap", "lane": "rules", "kind": "builtin", "check": "contrast_cap", "params": {"max": rules.contrast_cap}})
    if rules.no_emojis:
        builtins.append({"id": "no-emojis", "lane": "rules", "kind": "builtin", "check": "no_emojis"})
    if builtins:
        add("house-checks", "House checks", "Built-in prose checks enabled by the style profile.", builtins)

    for policy_id, title, attribute in _GUIDANCE_SECTIONS:
        lines = getattr(profile, attribute)
        if lines:
            add(policy_id, title, "\n".join(lines), [], severity="info")

    pack: dict[str, Any] = {
        "schemaVersion": 1,
        "packId": profile.publication_key,
        "version": version or f"style-profile-import-{date.today().isoformat()}",
        "title": f"{profile.voice_name} (imported style profile)",
        "policies": policies,
        "referenceSamples": [
            {"id": sample.id, "title": sample.title, "url": sample.url, "text": sample.body} for sample in loaded.samples
        ],
    }
    aim = profile.editorial_aim or f"Voice: {profile.voice_name}. Audience: {profile.audience}"
    pack["guidance"] = aim
    return pack


def _phrase(detector_id: str, phrases: tuple[str, ...]) -> dict[str, Any]:
    return {"id": detector_id, "lane": "rules", "kind": "phrase", "phrases": list(phrases)}


def _builtin(check_name: str, profile) -> dict[str, Any]:
    check = _CHECKS[check_name]
    detector: dict[str, Any] = {"id": check.replace("_", "-"), "lane": "rules", "kind": "builtin", "check": check}
    if check == "information_density":
        density = profile.density
        detector["params"] = {
            "minWords": density.min_words,
            "minLexicalDensity": density.min_lexical_density,
            "maxGzipRatio": density.max_gzip_ratio,
        }
    return detector


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
