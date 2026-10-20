"""Convert a style profile (the pre-policy-pack format) into a ``policy-pack-v1`` payload.

Mechanical controls (lexicon, banned phrases and patterns, checks) become
rules-lane detectors. Prose guidance (tone, sentence style, structure, voice
patterns, evidence rules) becomes guidance-only policies: they carry no
detector until someone writes a classifier question for them. Sections the
policy pack has no place for (judge, headline, standfirst, compare) are
ignored. The result is validated as a policy pack, which is the contract that
matters from here on.
"""
from __future__ import annotations

import json
import re
from datetime import date
from pathlib import Path
from typing import Any

import yaml

from .policy_pack import load_policy_pack

# Style-profile check names, all enabled unless the profile turns them off.
_CHECKS = {
    "emptyLeadin": "empty_leadin",
    "listShapedProse": "list_shaped_prose",
    "vagueClaim": "vague_claim",
    "unsupportedCertainty": "unsupported_certainty",
    "uniformCadence": "uniform_cadence",
    "redundancy": "redundancy",
    "voiceMismatch": "passive_voice",  # the legacy check flagged passive voice when the profile asked for active voice
    "missingAttribution": "missing_attribution",
    "informationDensity": "information_density",
    "overusedWords": "overused_words",
    "uncontractedForms": "uncontracted_forms",
}

_GUIDANCE_SECTIONS = (
    ("tone", "Tone", "tone"),
    ("sentence-style", "Sentence style", "sentenceStyle"),
    ("structure", "Structure", "structure"),
    ("voice-patterns", "Voice patterns", "voicePatterns"),
    ("evidence", "Evidence", "evidenceRules"),
)


class StyleProfileImportError(ValueError):
    """The style profile cannot be read or converted."""


def policy_pack_from_style_profile(path: str | Path, version: str | None = None) -> dict[str, Any]:
    """Read a style profile file and return a validated policy pack payload."""
    profile_path = Path(path).resolve()
    try:
        text = profile_path.read_text(encoding="utf-8")
        raw = json.loads(text) if profile_path.suffix.lower() == ".json" else yaml.safe_load(text)
    except (OSError, json.JSONDecodeError, yaml.YAMLError) as exc:
        raise StyleProfileImportError(f"Could not read style profile {profile_path}: {exc}") from exc
    if not isinstance(raw, dict) or not raw.get("publicationKey"):
        raise StyleProfileImportError(f"{profile_path} is not a style profile (no publicationKey)")

    lexicon = raw.get("lexicon") or {}
    rules = raw.get("rules") or {}
    policies: list[dict[str, Any]] = []

    def add(policy_id: str, title: str, guidance: str, detectors: list[dict[str, Any]], severity: str = "warn") -> None:
        policies.append({"id": policy_id, "version": 1, "title": title, "guidance": guidance, "severity": severity, "detectors": detectors})

    avoid, prefer = _strings(lexicon.get("avoid")), _strings(lexicon.get("prefer"))
    if avoid:
        guidance = "Avoid these words and phrases." + (f" Prefer: {', '.join(prefer)}." if prefer else "")
        add("avoid-lexicon", "Avoided lexicon", guidance, [_phrase("avoid-lexicon", avoid)])
    if _strings(rules.get("bannedPhrases")):
        add("banned-phrases", "Banned phrases", "Do not use these phrases.", [_phrase("banned-phrases", _strings(rules["bannedPhrases"]))])
    if _strings(rules.get("bannedIntensifiers")):
        add(
            "banned-intensifiers",
            "Banned intensifiers",
            "Cut intensifiers that add emphasis without information.",
            [_phrase("banned-intensifiers", _strings(rules["bannedIntensifiers"]))],
        )
    patterns = [entry for entry in rules.get("bannedPatterns") or [] if isinstance(entry, dict) and entry.get("pattern")]
    if patterns:
        add(
            "banned-patterns",
            "Banned patterns",
            "House patterns to rewrite.",
            [
                {"id": f"pattern-{index + 1}", "lane": "rules", "kind": "regex", "pattern": entry["pattern"], "message": entry.get("message") or "House pattern."}
                for index, entry in enumerate(patterns)
            ],
        )
    for index, entry in enumerate(rules.get("preferredPhrasing") or []):
        from_phrase, to_phrase = str(entry.get("from", "")).strip(), str(entry.get("to", "")).strip()
        if from_phrase and to_phrase:
            add(
                f"prefer-{_slug(to_phrase) or index + 1}",
                f"Prefer “{to_phrase}”",
                f"Prefer “{to_phrase}” over “{from_phrase}”.",
                [{**_phrase("preferred-phrasing", [from_phrase]), "replacement": to_phrase}],
                severity="info",
            )

    checks = {name: True for name in _CHECKS} | {k: bool(v) for k, v in (raw.get("checks") or {}).items() if k in _CHECKS}
    prefers_active = "active voice" in " ".join(_strings(raw.get("sentenceStyle"))).lower()
    builtins = [
        _builtin(name, raw.get("density") or {})
        for name, enabled in checks.items()
        if enabled and (name != "voiceMismatch" or prefers_active)
    ]
    if isinstance(rules.get("contrastCap"), int):
        builtins.append({"id": "contrast-cap", "lane": "rules", "kind": "builtin", "check": "contrast_cap", "params": {"max": rules["contrastCap"]}})
    if rules.get("noEmojis"):
        builtins.append({"id": "no-emojis", "lane": "rules", "kind": "builtin", "check": "no_emojis"})
    if builtins:
        add("house-checks", "House checks", "Built-in prose checks enabled by the style profile.", builtins)

    for policy_id, title, key in _GUIDANCE_SECTIONS:
        lines = _strings(raw.get(key))
        if lines:
            add(policy_id, title, "\n".join(lines), [], severity="info")

    voice = (raw.get("voice") or {}).get("name") or raw["publicationKey"]
    pack: dict[str, Any] = {
        "schemaVersion": 1,
        "packId": raw["publicationKey"],
        "version": version or f"style-profile-import-{date.today().isoformat()}",
        "title": f"{voice} (imported style profile)",
        "guidance": raw.get("editorialAim") or f"Voice: {voice}. Audience: {raw.get('audience', 'general readers')}",
        "policies": policies,
        "referenceSamples": [_sample(entry, profile_path.parent) for entry in raw.get("referenceSamples") or []],
    }
    load_policy_pack(pack)
    return pack


def _strings(value: Any) -> list[str]:
    return [str(item).strip() for item in value or [] if str(item).strip()] if isinstance(value, list) else []


def _phrase(detector_id: str, phrases: list[str]) -> dict[str, Any]:
    return {"id": detector_id, "lane": "rules", "kind": "phrase", "phrases": phrases}


def _builtin(check_name: str, density: dict[str, Any]) -> dict[str, Any]:
    check = _CHECKS[check_name]
    detector: dict[str, Any] = {"id": check.replace("_", "-"), "lane": "rules", "kind": "builtin", "check": check}
    if check == "information_density":
        detector["params"] = {
            "minWords": density.get("minWords", 400),
            "minLexicalDensity": density.get("minLexicalDensity", 0.45),
            "maxGzipRatio": density.get("maxGzipRatio", 0.35),
        }
    return detector


def _sample(entry: dict[str, Any], root: Path) -> dict[str, Any]:
    path = (root / entry["path"]).resolve()
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise StyleProfileImportError(f"Reference sample not found: {path}") from exc
    if text.startswith("---\n"):
        parts = text.split("---\n", 2)
        if len(parts) == 3 and parts[2].strip():
            text = parts[2]
    sample = {"id": _slug(str(entry["id"])) or "sample", "text": text.strip()}
    for key in ("title", "url"):
        if entry.get(key):
            sample[key] = str(entry[key])
    return sample


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
