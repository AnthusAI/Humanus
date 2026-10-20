from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

DEFAULT_CONTRAST_MIN_RATIO = 4.5
DEFAULT_TAP_TARGET_MIN_PX = 24

USABILITY_PROFILE_TOP_LEVEL_KEYS = frozenset(
    {"contrast", "tapTarget", "focus", "accessibleName", "lang", "emoji", "template"}
)
CONTRAST_BLOCK_KEYS = frozenset({"minRatio"})
TAP_TARGET_BLOCK_KEYS = frozenset({"minPx"})
FOCUS_BLOCK_KEYS = frozenset({"flagSuppressedOutline"})
ACCESSIBLE_NAME_BLOCK_KEYS = frozenset({"flagMissing"})
LANG_BLOCK_KEYS = frozenset({"flagMissing"})
EMOJI_BLOCK_KEYS = frozenset({"flagInHeadings"})
TEMPLATE_BLOCK_KEYS = frozenset({"flagGradientHero", "flagFeatureRow"})
DEFAULT_FOCUS_FLAG_SUPPRESSED_OUTLINE = True
DEFAULT_TEMPLATE_FLAG_GRADIENT_HERO = True
DEFAULT_TEMPLATE_FLAG_FEATURE_ROW = True
DEFAULT_EMOJI_FLAG_IN_HEADINGS = True
DEFAULT_ACCESSIBLE_NAME_FLAG_MISSING = True
DEFAULT_LANG_FLAG_MISSING = True


class UsabilityProfileValidationError(ValueError):
    """Raised when a usability profile document fails validation."""


@dataclass(frozen=True)
class UsabilityContrastConfig:
    min_ratio: float


@dataclass(frozen=True)
class UsabilityTapTargetConfig:
    min_px: float


@dataclass(frozen=True)
class UsabilityFocusConfig:
    flag_suppressed_outline: bool


@dataclass(frozen=True)
class UsabilityAccessibleNameConfig:
    flag_missing: bool


@dataclass(frozen=True)
class UsabilityLangConfig:
    flag_missing: bool


@dataclass(frozen=True)
class UsabilityEmojiConfig:
    flag_in_headings: bool


@dataclass(frozen=True)
class UsabilityTemplateConfig:
    flag_gradient_hero: bool
    flag_feature_row: bool


@dataclass(frozen=True)
class UsabilityProfile:
    contrast: UsabilityContrastConfig
    tap_target: UsabilityTapTargetConfig
    focus: UsabilityFocusConfig
    accessible_name: UsabilityAccessibleNameConfig
    lang: UsabilityLangConfig
    emoji: UsabilityEmojiConfig
    template: UsabilityTemplateConfig


@dataclass(frozen=True)
class LoadedUsabilityProfile:
    path: Path
    profile: UsabilityProfile


def load_usability_profile(profile_path: Path) -> LoadedUsabilityProfile:
    resolved = profile_path.resolve()
    if not resolved.is_file():
        raise UsabilityProfileValidationError(f"Usability profile not found: {resolved}")
    raw_text = resolved.read_text(encoding="utf-8")
    try:
        raw = yaml.safe_load(raw_text)
    except yaml.YAMLError as exc:
        raise UsabilityProfileValidationError(f"Invalid YAML in {resolved}: {exc}") from exc
    if raw is None:
        raw = {}
    if not isinstance(raw, dict):
        raise UsabilityProfileValidationError(f"Usability profile must be a mapping in {resolved}")
    unknown = set(raw.keys()) - USABILITY_PROFILE_TOP_LEVEL_KEYS
    if unknown:
        joined = ", ".join(sorted(str(key) for key in unknown))
        raise UsabilityProfileValidationError(f"Unknown usability profile keys in {resolved}: {joined}")
    contrast = _parse_contrast(raw.get("contrast"), resolved)
    tap_target = _parse_tap_target(raw.get("tapTarget"), resolved)
    focus = _parse_focus(raw.get("focus"), resolved)
    accessible_name = _parse_accessible_name(raw.get("accessibleName"), resolved)
    lang = _parse_lang(raw.get("lang"), resolved)
    emoji = _parse_emoji(raw.get("emoji"), resolved)
    template = _parse_template(raw.get("template"), resolved)
    return LoadedUsabilityProfile(
        path=resolved,
        profile=UsabilityProfile(
            contrast=contrast,
            tap_target=tap_target,
            focus=focus,
            accessible_name=accessible_name,
            lang=lang,
            emoji=emoji,
            template=template,
        ),
    )


def _parse_contrast(value: Any, profile_path: Path) -> UsabilityContrastConfig:
    if value is None:
        return UsabilityContrastConfig(min_ratio=DEFAULT_CONTRAST_MIN_RATIO)
    if not isinstance(value, dict):
        raise UsabilityProfileValidationError(f"contrast must be a mapping in {profile_path}")
    unknown = set(value.keys()) - CONTRAST_BLOCK_KEYS
    if unknown:
        joined = ", ".join(sorted(str(key) for key in unknown))
        raise UsabilityProfileValidationError(f"Unknown contrast keys in {profile_path}: {joined}")
    min_ratio_raw = value.get("minRatio", DEFAULT_CONTRAST_MIN_RATIO)
    if not isinstance(min_ratio_raw, (int, float)) or isinstance(min_ratio_raw, bool):
        raise UsabilityProfileValidationError(f"contrast.minRatio must be a number in {profile_path}")
    min_ratio = float(min_ratio_raw)
    if min_ratio <= 0:
        raise UsabilityProfileValidationError(f"contrast.minRatio must be positive in {profile_path}")
    return UsabilityContrastConfig(min_ratio=min_ratio)


def _parse_tap_target(value: Any, profile_path: Path) -> UsabilityTapTargetConfig:
    if value is None:
        return UsabilityTapTargetConfig(min_px=DEFAULT_TAP_TARGET_MIN_PX)
    if not isinstance(value, dict):
        raise UsabilityProfileValidationError(f"tapTarget must be a mapping in {profile_path}")
    unknown = set(value.keys()) - TAP_TARGET_BLOCK_KEYS
    if unknown:
        joined = ", ".join(sorted(str(key) for key in unknown))
        raise UsabilityProfileValidationError(f"Unknown tapTarget keys in {profile_path}: {joined}")
    min_px_raw = value.get("minPx", DEFAULT_TAP_TARGET_MIN_PX)
    if not isinstance(min_px_raw, (int, float)) or isinstance(min_px_raw, bool):
        raise UsabilityProfileValidationError(f"tapTarget.minPx must be a number in {profile_path}")
    min_px = float(min_px_raw)
    if min_px <= 0:
        raise UsabilityProfileValidationError(f"tapTarget.minPx must be positive in {profile_path}")
    return UsabilityTapTargetConfig(min_px=min_px)


def _parse_focus(value: Any, profile_path: Path) -> UsabilityFocusConfig:
    if value is None:
        return UsabilityFocusConfig(flag_suppressed_outline=DEFAULT_FOCUS_FLAG_SUPPRESSED_OUTLINE)
    if not isinstance(value, dict):
        raise UsabilityProfileValidationError(f"focus must be a mapping in {profile_path}")
    unknown = set(value.keys()) - FOCUS_BLOCK_KEYS
    if unknown:
        joined = ", ".join(sorted(str(key) for key in unknown))
        raise UsabilityProfileValidationError(f"Unknown focus keys in {profile_path}: {joined}")
    flag_raw = value.get("flagSuppressedOutline", DEFAULT_FOCUS_FLAG_SUPPRESSED_OUTLINE)
    if not isinstance(flag_raw, bool):
        raise UsabilityProfileValidationError(
            f"focus.flagSuppressedOutline must be a boolean in {profile_path}"
        )
    return UsabilityFocusConfig(flag_suppressed_outline=flag_raw)


def _parse_accessible_name(value: Any, profile_path: Path) -> UsabilityAccessibleNameConfig:
    if value is None:
        return UsabilityAccessibleNameConfig(flag_missing=DEFAULT_ACCESSIBLE_NAME_FLAG_MISSING)
    if not isinstance(value, dict):
        raise UsabilityProfileValidationError(
            f"accessibleName must be a mapping in {profile_path}"
        )
    unknown = set(value.keys()) - ACCESSIBLE_NAME_BLOCK_KEYS
    if unknown:
        joined = ", ".join(sorted(str(key) for key in unknown))
        raise UsabilityProfileValidationError(
            f"Unknown accessibleName keys in {profile_path}: {joined}"
        )
    flag_raw = value.get("flagMissing", DEFAULT_ACCESSIBLE_NAME_FLAG_MISSING)
    if not isinstance(flag_raw, bool):
        raise UsabilityProfileValidationError(
            f"accessibleName.flagMissing must be a boolean in {profile_path}"
        )
    return UsabilityAccessibleNameConfig(flag_missing=flag_raw)


def _parse_lang(value: Any, profile_path: Path) -> UsabilityLangConfig:
    if value is None:
        return UsabilityLangConfig(flag_missing=DEFAULT_LANG_FLAG_MISSING)
    if not isinstance(value, dict):
        raise UsabilityProfileValidationError(f"lang must be a mapping in {profile_path}")
    unknown = set(value.keys()) - LANG_BLOCK_KEYS
    if unknown:
        joined = ", ".join(sorted(str(key) for key in unknown))
        raise UsabilityProfileValidationError(f"Unknown lang keys in {profile_path}: {joined}")
    flag_raw = value.get("flagMissing", DEFAULT_LANG_FLAG_MISSING)
    if not isinstance(flag_raw, bool):
        raise UsabilityProfileValidationError(f"lang.flagMissing must be a boolean in {profile_path}")
    return UsabilityLangConfig(flag_missing=flag_raw)


def _parse_emoji(value: Any, profile_path: Path) -> UsabilityEmojiConfig:
    if value is None:
        return UsabilityEmojiConfig(flag_in_headings=DEFAULT_EMOJI_FLAG_IN_HEADINGS)
    if not isinstance(value, dict):
        raise UsabilityProfileValidationError(f"emoji must be a mapping in {profile_path}")
    unknown = set(value.keys()) - EMOJI_BLOCK_KEYS
    if unknown:
        joined = ", ".join(sorted(str(key) for key in unknown))
        raise UsabilityProfileValidationError(f"Unknown emoji keys in {profile_path}: {joined}")
    flag_raw = value.get("flagInHeadings", DEFAULT_EMOJI_FLAG_IN_HEADINGS)
    if not isinstance(flag_raw, bool):
        raise UsabilityProfileValidationError(
            f"emoji.flagInHeadings must be a boolean in {profile_path}"
        )
    return UsabilityEmojiConfig(flag_in_headings=flag_raw)


def _parse_template(value: Any, profile_path: Path) -> UsabilityTemplateConfig:
    if value is None:
        return UsabilityTemplateConfig(
            flag_gradient_hero=DEFAULT_TEMPLATE_FLAG_GRADIENT_HERO,
            flag_feature_row=DEFAULT_TEMPLATE_FLAG_FEATURE_ROW,
        )
    if not isinstance(value, dict):
        raise UsabilityProfileValidationError(f"template must be a mapping in {profile_path}")
    unknown = set(value.keys()) - TEMPLATE_BLOCK_KEYS
    if unknown:
        joined = ", ".join(sorted(str(key) for key in unknown))
        raise UsabilityProfileValidationError(f"Unknown template keys in {profile_path}: {joined}")
    flag_gradient_raw = value.get("flagGradientHero", DEFAULT_TEMPLATE_FLAG_GRADIENT_HERO)
    if not isinstance(flag_gradient_raw, bool):
        raise UsabilityProfileValidationError(
            f"template.flagGradientHero must be a boolean in {profile_path}"
        )
    flag_feature_row_raw = value.get("flagFeatureRow", DEFAULT_TEMPLATE_FLAG_FEATURE_ROW)
    if not isinstance(flag_feature_row_raw, bool):
        raise UsabilityProfileValidationError(
            f"template.flagFeatureRow must be a boolean in {profile_path}"
        )
    return UsabilityTemplateConfig(
        flag_gradient_hero=flag_gradient_raw,
        flag_feature_row=flag_feature_row_raw,
    )
