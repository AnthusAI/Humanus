from __future__ import annotations

import re
from dataclasses import dataclass, field
from html.parser import HTMLParser
from typing import Any

from ._util import hash_short
from .emoji import EMOJI_PATTERN
from .usability_profile import LoadedUsabilityProfile

HEADING_TAGS = frozenset({"h1", "h2", "h3", "h4", "h5", "h6"})

SCHEMA_VERSION = 1

USABILITY_FORBIDDEN_OUTPUT_KEYS = frozenset(
    {
        "rewrite",
        "patch",
        "patches",
        "options",
        "decisions",
        "revised_text",
        "rewritten_prose",
        "revisedProse",
        "revisedText",
    }
)

# CSS Level 1 color names supported for deterministic parsing (no full named-color table).
CSS_NAMED_COLORS: dict[str, tuple[int, int, int]] = {
    "black": (0, 0, 0),
    "white": (255, 255, 255),
    "red": (255, 0, 0),
    "green": (0, 128, 0),
    "blue": (0, 0, 255),
    "gray": (128, 128, 128),
    "grey": (128, 128, 128),
}

VOID_HTML_ELEMENTS = frozenset(
    {
        "area",
        "base",
        "br",
        "col",
        "embed",
        "hr",
        "img",
        "input",
        "link",
        "meta",
        "source",
        "track",
        "wbr",
    }
)

TEXT_CONTAINER_TAGS = frozenset(
    {
        "p",
        "span",
        "div",
        "h1",
        "h2",
        "h3",
        "h4",
        "h5",
        "h6",
        "a",
        "li",
        "label",
        "button",
        "td",
        "th",
        "strong",
        "em",
        "small",
    }
)


class UsabilityFindingsValidationError(ValueError):
    """Raised when usability findings JSON fails schema validation."""


@dataclass
class _DomNode:
    tag: str
    attrs: dict[str, str]
    direct_text: list[str] = field(default_factory=list)
    children: list[_DomNode] = field(default_factory=list)
    parent: _DomNode | None = None


@dataclass(frozen=True)
class _CssRule:
    selectors: tuple[str, ...]
    declarations: dict[str, str]


def scan_html_page(page_html: str, *, profile: LoadedUsabilityProfile) -> dict[str, Any]:
    tree, style_text = _parse_html(page_html)
    css_rules = _parse_stylesheet(style_text)
    findings: list[dict[str, Any]] = []
    findings.extend(_find_missing_alt(tree))
    findings.extend(
        _find_low_contrast(tree, css_rules, min_ratio=profile.profile.contrast.min_ratio)
    )
    findings.extend(
        _find_small_tap_target(
            tree, css_rules, min_px=profile.profile.tap_target.min_px
        )
    )
    if profile.profile.focus.flag_suppressed_outline:
        findings.extend(_find_suppressed_focus_outline(tree, css_rules))
    if profile.profile.accessible_name.flag_missing:
        findings.extend(_find_missing_accessible_name(tree))
    if profile.profile.lang.flag_missing:
        findings.extend(_find_missing_lang(tree))
    if profile.profile.emoji.flag_in_headings:
        findings.extend(_find_emoji_heading(tree))
    if profile.profile.template.flag_gradient_hero:
        findings.extend(_find_generic_gradient_hero(tree, css_rules))
    if profile.profile.template.flag_feature_row:
        findings.extend(_find_generic_feature_row(tree))
    payload = {"schemaVersion": SCHEMA_VERSION, "findings": findings}
    return validate_usability_findings(payload)


def stable_usability_finding_id(kind: str, selector: str, detail: str = "") -> str:
    return f"finding-{hash_short([SCHEMA_VERSION, kind, selector, detail])}"


def assert_no_forbidden_usability_keys(value: Any, key_path: str = "") -> None:
    if isinstance(value, dict):
        for key, nested in value.items():
            key_text = str(key)
            current_path = f"{key_path}.{key_text}" if key_path else key_text
            if key_text in USABILITY_FORBIDDEN_OUTPUT_KEYS:
                raise UsabilityFindingsValidationError(
                    f"Usability findings JSON contains forbidden field '{current_path}'"
                )
            assert_no_forbidden_usability_keys(nested, current_path)
        return
    if isinstance(value, list):
        for index, nested in enumerate(value):
            assert_no_forbidden_usability_keys(nested, f"{key_path}[{index}]")


def validate_usability_findings(payload: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise UsabilityFindingsValidationError("Usability findings JSON must be a mapping.")
    assert_no_forbidden_usability_keys(payload)
    if payload.get("schemaVersion") != SCHEMA_VERSION:
        raise UsabilityFindingsValidationError(
            f"Unsupported schemaVersion: expected {SCHEMA_VERSION}."
        )
    findings = payload.get("findings")
    if not isinstance(findings, list):
        raise UsabilityFindingsValidationError("findings must be a list.")
    validated: list[dict[str, Any]] = []
    for index, entry in enumerate(findings):
        validated.append(_validate_finding(entry, f"findings[{index}]"))
    return {"schemaVersion": SCHEMA_VERSION, "findings": validated}


def _validate_finding(entry: Any, location: str) -> dict[str, Any]:
    if not isinstance(entry, dict):
        raise UsabilityFindingsValidationError(f"{location} must be a mapping.")
    assert_no_forbidden_usability_keys(entry, location)
    kind = entry.get("kind")
    if kind not in {
        "missing_alt",
        "low_contrast",
        "small_tap_target",
        "suppressed_focus_outline",
        "missing_accessible_name",
        "missing_lang",
        "emoji_heading",
        "generic_gradient_hero",
        "generic_feature_row",
    }:
        raise UsabilityFindingsValidationError(
            f"{location}.kind must be 'missing_alt', 'low_contrast', 'small_tap_target', "
            "'suppressed_focus_outline', 'missing_accessible_name', 'missing_lang', "
            "'emoji_heading', 'generic_gradient_hero', or 'generic_feature_row'."
        )
    finding_id = entry.get("id")
    if not isinstance(finding_id, str) or not re.fullmatch(r"finding-[a-f0-9]{16}", finding_id):
        raise UsabilityFindingsValidationError(f"{location}.id must match finding-<16 hex>.")
    selector = entry.get("selector")
    if not isinstance(selector, str) or not selector.strip():
        raise UsabilityFindingsValidationError(f"{location}.selector must be a non-empty string.")
    rationale = entry.get("rationale")
    if not isinstance(rationale, str) or not rationale.strip():
        raise UsabilityFindingsValidationError(f"{location}.rationale must be a non-empty string.")
    result: dict[str, Any] = {
        "id": finding_id,
        "kind": kind,
        "selector": selector,
        "rationale": rationale,
    }
    if kind == "low_contrast":
        ratio = entry.get("ratio")
        if not isinstance(ratio, (int, float)) or isinstance(ratio, bool):
            raise UsabilityFindingsValidationError(f"{location}.ratio must be a number.")
        result["ratio"] = round(float(ratio), 4)
    elif kind == "small_tap_target":
        width = entry.get("width")
        height = entry.get("height")
        if not isinstance(width, (int, float)) or isinstance(width, bool):
            raise UsabilityFindingsValidationError(f"{location}.width must be a number.")
        if not isinstance(height, (int, float)) or isinstance(height, bool):
            raise UsabilityFindingsValidationError(f"{location}.height must be a number.")
        result["width"] = float(width)
        result["height"] = float(height)
    elif kind == "suppressed_focus_outline":
        if "ratio" in entry:
            raise UsabilityFindingsValidationError(
                f"{location} must not include ratio for suppressed_focus_outline."
            )
        if "width" in entry or "height" in entry:
            raise UsabilityFindingsValidationError(
                f"{location} must not include width or height for suppressed_focus_outline."
            )
    elif kind in {
        "missing_alt",
        "missing_accessible_name",
        "missing_lang",
        "emoji_heading",
        "generic_gradient_hero",
        "generic_feature_row",
    }:
        if "ratio" in entry:
            raise UsabilityFindingsValidationError(
                f"{location} must not include ratio for {kind}."
            )
        if "width" in entry or "height" in entry:
            raise UsabilityFindingsValidationError(
                f"{location} must not include width or height for {kind}."
            )
    return result


def _node_text_content(node: _DomNode) -> str:
    parts = list(node.direct_text)
    for child in node.children:
        parts.append(_node_text_content(child))
    return "".join(parts)


HERO_GRADIENT_SELECTORS = frozenset(
    {"body", "header", ".hero", "#hero", ".banner", "#banner"}
)


def _parse_simple_hero_selector(selector: str) -> str | None:
    stripped = selector.strip()
    if not stripped or any(char in stripped for char in " *>+~"):
        return None
    if stripped in HERO_GRADIENT_SELECTORS:
        return stripped
    return None


def _declaration_value_has_linear_gradient(value: str) -> bool:
    return "linear-gradient" in value.lower()


def _rule_has_hero_linear_gradient(declarations: dict[str, str]) -> bool:
    for prop in ("background", "background-image"):
        raw = declarations.get(prop)
        if raw is not None and _declaration_value_has_linear_gradient(raw):
            return True
    return False


def _collect_gradient_hero_nodes(
    node: _DomNode,
    css_rules: list[_CssRule],
    flagged: set[str],
    findings: list[dict[str, Any]],
) -> None:
    if node.tag != "document":
        for rule in css_rules:
            if not _rule_has_hero_linear_gradient(rule.declarations):
                continue
            for selector in rule.selectors:
                hero = _parse_simple_hero_selector(selector)
                if hero is None:
                    continue
                if not _single_selector_matches(node, hero):
                    continue
                selector_label = _element_selector(node)
                if selector_label in flagged:
                    break
                flagged.add(selector_label)
                finding_id = stable_usability_finding_id("generic_gradient_hero", selector_label)
                findings.append(
                    {
                        "id": finding_id,
                        "kind": "generic_gradient_hero",
                        "selector": selector_label,
                        "rationale": (
                            "Hero-region element uses a linear-gradient background, a common "
                            "generic template pattern."
                        ),
                    }
                )
                break
    for child in node.children:
        _collect_gradient_hero_nodes(child, css_rules, flagged, findings)


def _find_generic_gradient_hero(
    node: _DomNode,
    css_rules: list[_CssRule],
) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    flagged: set[str] = set()
    _collect_gradient_hero_nodes(node, css_rules, flagged, findings)
    return findings


def _first_class_token(node: _DomNode) -> str | None:
    for class_name in node.attrs.get("class", "").split():
        if class_name:
            return class_name
    return None


def _has_img_or_svg_descendant(node: _DomNode) -> bool:
    if node.tag in {"img", "svg"}:
        return True
    for child in node.children:
        if _has_img_or_svg_descendant(child):
            return True
    return False


def _parent_has_qualifying_feature_row_run(parent: _DomNode) -> bool:
    children = parent.children
    index = 0
    while index < len(children):
        token = _first_class_token(children[index])
        if not token:
            index += 1
            continue
        end = index + 1
        while end < len(children) and _first_class_token(children[end]) == token:
            end += 1
        run_length = end - index
        if run_length >= 3:
            run = children[index:end]
            if all(_has_img_or_svg_descendant(child) for child in run):
                return True
        index = end
    return False


def _collect_generic_feature_row_findings(
    node: _DomNode,
    flagged_parents: set[str],
    findings: list[dict[str, Any]],
) -> None:
    if node.tag != "document" and _parent_has_qualifying_feature_row_run(node):
        selector_label = _element_selector(node)
        if selector_label not in flagged_parents:
            flagged_parents.add(selector_label)
            finding_id = stable_usability_finding_id("generic_feature_row", selector_label)
            findings.append(
                {
                    "id": finding_id,
                    "kind": "generic_feature_row",
                    "selector": selector_label,
                    "rationale": (
                        "Parent contains three or more consecutive sibling elements sharing the "
                        "same leading class, each with an image or SVG—a common generic "
                        "feature-row template pattern."
                    ),
                }
            )
    for child in node.children:
        _collect_generic_feature_row_findings(child, flagged_parents, findings)


def _find_generic_feature_row(node: _DomNode) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    flagged_parents: set[str] = set()
    _collect_generic_feature_row_findings(node, flagged_parents, findings)
    return findings


def _find_emoji_heading(node: _DomNode) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    if node.tag in HEADING_TAGS:
        text = _node_text_content(node)
        if EMOJI_PATTERN.search(text):
            selector = _element_selector(node)
            finding_id = stable_usability_finding_id("emoji_heading", selector)
            findings.append(
                {
                    "id": finding_id,
                    "kind": "emoji_heading",
                    "selector": selector,
                    "rationale": "Heading contains emoji characters.",
                }
            )
    for child in node.children:
        findings.extend(_find_emoji_heading(child))
    return findings


def _find_missing_lang(node: _DomNode) -> list[dict[str, Any]]:
    html_nodes = [child for child in node.children if child.tag == "html"]
    if not html_nodes:
        return []
    html = html_nodes[0]
    lang = html.attrs.get("lang", "")
    if lang.strip():
        return []
    finding_id = stable_usability_finding_id("missing_lang", "html")
    return [
        {
            "id": finding_id,
            "kind": "missing_lang",
            "selector": "html",
            "rationale": "Root html element lacks a non-empty lang attribute.",
        }
    ]


def _build_accessible_name_index(
    node: _DomNode,
    *,
    element_ids: set[str],
    label_for_ids: set[str],
) -> None:
    element_id = node.attrs.get("id", "").strip()
    if element_id:
        element_ids.add(element_id)
    if node.tag == "label":
        for_value = node.attrs.get("for", "").strip()
        if for_value:
            label_for_ids.add(for_value)
    for child in node.children:
        _build_accessible_name_index(
            child, element_ids=element_ids, label_for_ids=label_for_ids
        )


def _input_type(node: _DomNode) -> str:
    return node.attrs.get("type", "text").lower()


def _control_needs_accessible_name_check(node: _DomNode) -> bool:
    tag = node.tag
    if tag in {"select", "textarea"}:
        return True
    if tag != "input":
        return False
    input_type = _input_type(node)
    if input_type == "hidden":
        return False
    if input_type in {"submit", "button", "reset"}:
        if node.attrs.get("value", "").strip():
            return False
        if node.attrs.get("aria-label", "").strip():
            return False
    return True


def _has_accessible_name(
    node: _DomNode,
    *,
    element_ids: set[str],
    label_for_ids: set[str],
) -> bool:
    if node.attrs.get("aria-label", "").strip():
        return True
    labelledby = node.attrs.get("aria-labelledby", "").strip()
    if labelledby:
        for token in labelledby.split():
            if token in element_ids:
                return True
    ancestor = node.parent
    while ancestor is not None and ancestor.tag != "document":
        if ancestor.tag == "label":
            return True
        ancestor = ancestor.parent
    element_id = node.attrs.get("id", "").strip()
    if element_id and element_id in label_for_ids:
        return True
    if node.tag == "input" and _input_type(node) == "image":
        if node.attrs.get("alt", "").strip():
            return True
    return False


def _find_missing_accessible_name(node: _DomNode) -> list[dict[str, Any]]:
    element_ids: set[str] = set()
    label_for_ids: set[str] = set()
    _build_accessible_name_index(node, element_ids=element_ids, label_for_ids=label_for_ids)
    findings: list[dict[str, Any]] = []

    def walk(current: _DomNode) -> None:
        if current.tag != "document" and _control_needs_accessible_name_check(current):
            if not _has_accessible_name(
                current, element_ids=element_ids, label_for_ids=label_for_ids
            ):
                selector = _element_selector(current)
                finding_id = stable_usability_finding_id("missing_accessible_name", selector)
                findings.append(
                    {
                        "id": finding_id,
                        "kind": "missing_accessible_name",
                        "selector": selector,
                        "rationale": "Form control has no accessible name.",
                    }
                )
        for child in current.children:
            walk(child)

    walk(node)
    return findings


def _find_missing_alt(node: _DomNode) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    if node.tag == "img":
        if "alt" not in node.attrs:
            selector = _element_selector(node)
            src = node.attrs.get("src", "")
            finding_id = stable_usability_finding_id("missing_alt", selector, src)
            findings.append(
                {
                    "id": finding_id,
                    "kind": "missing_alt",
                    "selector": selector,
                    "rationale": "Image element has no alt attribute.",
                }
            )
    for child in node.children:
        findings.extend(_find_missing_alt(child))
    return findings


def _is_interactive_tap_target(node: _DomNode) -> bool:
    role = node.attrs.get("role", "").lower()
    if role in {"button", "link"}:
        return True
    tag = node.tag
    if tag == "input":
        input_type = node.attrs.get("type", "text").lower()
        return input_type != "hidden"
    return tag in {"a", "button", "select", "textarea", "summary"}


_FOCUS_PSEUDO_SUFFIXES = (":focus-visible", ":focus")
_FOCUS_SELECTOR_BASE_RE = re.compile(r"^(?:[a-z][a-z0-9-]*|\.[a-zA-Z0-9_-]+|#[a-zA-Z0-9_-]+)$")
_FOCUS_PSEUDO_SPECIFICITY_BONUS = 1000


def _parse_simple_focus_selector(selector: str) -> tuple[str, bool] | None:
    """Return (base_selector, is_focus_pseudo) for allowed simple selectors, else None."""
    stripped = selector.strip()
    if not stripped or any(char in stripped for char in " *>+~"):
        return None
    for suffix in _FOCUS_PSEUDO_SUFFIXES:
        if stripped.endswith(suffix):
            base = stripped[: -len(suffix)]
            if _FOCUS_SELECTOR_BASE_RE.fullmatch(base):
                return base, True
            return None
    if _FOCUS_SELECTOR_BASE_RE.fullmatch(stripped):
        return stripped, False
    return None


def _base_selector_specificity(base_selector: str) -> int:
    if base_selector.startswith("#"):
        return 100
    if base_selector.startswith("."):
        return 10
    return 1


def _base_selector_matches_node(node: _DomNode, base_selector: str) -> bool:
    return _single_selector_matches(node, base_selector)


def _declarations_suppress_outline(declarations: dict[str, str]) -> bool:
    outline = declarations.get("outline")
    if outline is not None:
        first_token = outline.strip().lower().split()[0] if outline.strip() else ""
        if first_token in {"none", "0", "0px"}:
            return True
    outline_width = declarations.get("outline-width")
    if outline_width is not None:
        width_text = outline_width.strip().lower()
        if width_text in {"0", "0px"}:
            return True
    return False


def _declarations_have_non_none_box_shadow(declarations: dict[str, str]) -> bool:
    box_shadow = declarations.get("box-shadow")
    if box_shadow is None:
        return False
    return box_shadow.strip().lower() != "none"


@dataclass(frozen=True)
class _WinningOutlineBlock:
    declarations: dict[str, str]
    specificity: int
    order: int


def _resolve_focus_outline_block(
    node: _DomNode, css_rules: list[_CssRule]
) -> _WinningOutlineBlock | None:
    winner: _WinningOutlineBlock | None = None
    inline = _inline_style_dict(node.attrs.get("style", ""))
    if "outline" in inline or "outline-width" in inline:
        winner = _WinningOutlineBlock(
            declarations=inline,
            specificity=10_000,
            order=10_000,
        )
    for order, rule in enumerate(css_rules):
        for selector in rule.selectors:
            parsed = _parse_simple_focus_selector(selector)
            if parsed is None:
                continue
            base, is_focus_pseudo = parsed
            if not _base_selector_matches_node(node, base):
                continue
            if "outline" not in rule.declarations and "outline-width" not in rule.declarations:
                continue
            specificity = _base_selector_specificity(base)
            if is_focus_pseudo:
                specificity += _FOCUS_PSEUDO_SPECIFICITY_BONUS
            candidate = _WinningOutlineBlock(
                declarations=rule.declarations,
                specificity=specificity,
                order=order,
            )
            if winner is None or candidate.specificity > winner.specificity or (
                candidate.specificity == winner.specificity and candidate.order > winner.order
            ):
                winner = candidate
    return winner


def _find_suppressed_focus_outline(
    node: _DomNode,
    css_rules: list[_CssRule],
) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    if node.tag != "document" and _is_interactive_tap_target(node):
        block = _resolve_focus_outline_block(node, css_rules)
        if block is not None and _declarations_suppress_outline(block.declarations):
            if not _declarations_have_non_none_box_shadow(block.declarations):
                selector = _element_selector(node)
                finding_id = stable_usability_finding_id("suppressed_focus_outline", selector)
                findings.append(
                    {
                        "id": finding_id,
                        "kind": "suppressed_focus_outline",
                        "selector": selector,
                        "rationale": (
                            "Interactive control suppresses visible focus outline without a "
                            "non-none box-shadow in the same declaration block."
                        ),
                    }
                )
    for child in node.children:
        findings.extend(_find_suppressed_focus_outline(child, css_rules))
    return findings


def _find_small_tap_target(
    node: _DomNode,
    css_rules: list[_CssRule],
    *,
    min_px: float,
) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    if node.tag != "document" and _is_interactive_tap_target(node):
        width = _resolve_length_px(node, "width", css_rules)
        height = _resolve_length_px(node, "height", css_rules)
        if width is not None and height is not None and (width < min_px or height < min_px):
            selector = _element_selector(node)
            detail = f"{width}x{height}"
            finding_id = stable_usability_finding_id("small_tap_target", selector, detail)
            findings.append(
                {
                    "id": finding_id,
                    "kind": "small_tap_target",
                    "selector": selector,
                    "rationale": (
                        f"Interactive control size {width}×{height}px is below the profile "
                        f"minimum ({min_px}px) on at least one dimension."
                    ),
                    "width": width,
                    "height": height,
                }
            )
    for child in node.children:
        findings.extend(_find_small_tap_target(child, css_rules, min_px=min_px))
    return findings


def _find_low_contrast(
    node: _DomNode,
    css_rules: list[_CssRule],
    *,
    min_ratio: float,
) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    if node.tag in TEXT_CONTAINER_TAGS:
        direct = "".join(node.direct_text).strip()
        if direct:
            fg = _resolve_color(node, "color", css_rules)
            bg = _resolve_color(node, "background-color", css_rules)
            if fg is not None and bg is not None:
                ratio = _contrast_ratio(fg, bg)
                if ratio < min_ratio:
                    selector = _element_selector(node)
                    finding_id = stable_usability_finding_id(
                        "low_contrast", selector, f"{ratio:.4f}"
                    )
                    findings.append(
                        {
                            "id": finding_id,
                            "kind": "low_contrast",
                            "selector": selector,
                            "rationale": (
                                f"Text contrast ratio {ratio:.2f} is below the profile minimum "
                                f"({min_ratio})."
                            ),
                            "ratio": round(ratio, 4),
                        }
                    )
    for child in node.children:
        findings.extend(_find_low_contrast(child, css_rules, min_ratio=min_ratio))
    return findings


def _element_selector(node: _DomNode) -> str:
    parts = [node.tag]
    element_id = node.attrs.get("id")
    if element_id:
        parts.append(f"#{element_id}")
    classes = node.attrs.get("class", "")
    for class_name in classes.split():
        if class_name:
            parts.append(f".{class_name}")
    return "".join(parts)


def _resolve_length_px(
    node: _DomNode, property_name: str, css_rules: list[_CssRule]
) -> float | None:
    attr_value = node.attrs.get(property_name)
    if attr_value is not None:
        parsed = parse_css_length_px(attr_value)
        if parsed is not None:
            return parsed
    inline = _inline_style_dict(node.attrs.get("style", ""))
    if property_name in inline:
        parsed = parse_css_length_px(inline[property_name])
        if parsed is not None:
            return parsed
    matched_value: str | None = None
    matched_specificity = -1
    matched_order = -1
    for order, rule in enumerate(css_rules):
        if not _selector_matches_node(node, rule.selectors):
            continue
        if property_name not in rule.declarations:
            continue
        specificity = _selector_specificity(rule.selectors, node)
        if specificity > matched_specificity or (
            specificity == matched_specificity and order > matched_order
        ):
            matched_specificity = specificity
            matched_order = order
            matched_value = rule.declarations[property_name]
    if matched_value is None:
        return None
    return parse_css_length_px(matched_value)


def parse_css_length_px(value: str) -> float | None:
    text = value.strip().lower()
    if not text:
        return None
    if text.endswith("px"):
        number_text = text[:-2].strip()
        if not number_text:
            return None
        try:
            return float(number_text)
        except ValueError:
            return None
    if re.fullmatch(r"-?[0-9]+(?:\.[0-9]+)?", text):
        return float(text)
    return None


def _resolve_color(node: _DomNode, property_name: str, css_rules: list[_CssRule]) -> tuple[int, int, int] | None:
    inline = _inline_style_dict(node.attrs.get("style", ""))
    if property_name in inline:
        return parse_css_color(inline[property_name])
    matched_value: str | None = None
    matched_specificity = -1
    matched_order = -1
    for order, rule in enumerate(css_rules):
        if not _selector_matches_node(node, rule.selectors):
            continue
        if property_name not in rule.declarations:
            continue
        specificity = _selector_specificity(rule.selectors, node)
        if specificity > matched_specificity or (
            specificity == matched_specificity and order > matched_order
        ):
            matched_specificity = specificity
            matched_order = order
            matched_value = rule.declarations[property_name]
    if matched_value is None:
        return None
    return parse_css_color(matched_value)


def _inline_style_dict(style_attr: str) -> dict[str, str]:
    result: dict[str, str] = {}
    for chunk in style_attr.split(";"):
        if ":" not in chunk:
            continue
        name, value = chunk.split(":", 1)
        key = name.strip().lower()
        if key:
            result[key] = value.strip()
    return result


def _selector_matches_node(node: _DomNode, selectors: tuple[str, ...]) -> bool:
    return any(_single_selector_matches(node, selector) for selector in selectors)


def _single_selector_matches(node: _DomNode, selector: str) -> bool:
    selector = selector.strip()
    if not selector:
        return False
    tag = node.tag
    element_id = node.attrs.get("id", "")
    classes = set(node.attrs.get("class", "").split())
    if selector.startswith("#"):
        return selector[1:] == element_id
    if selector.startswith("."):
        return selector[1:] in classes
    return selector == tag


def _selector_specificity(selectors: tuple[str, ...], node: _DomNode) -> int:
    best = 0
    for selector in selectors:
        if not _single_selector_matches(node, selector):
            continue
        score = 0
        stripped = selector.strip()
        if stripped.startswith("#"):
            score = 100
        elif stripped.startswith("."):
            score = 10
        else:
            score = 1
        best = max(best, score)
    return best


def _parse_stylesheet(style_text: str) -> list[_CssRule]:
    if not style_text.strip():
        return []
    rules: list[_CssRule] = []
    for match in re.finditer(r"([^{}]+)\{([^{}]*)\}", style_text):
        selector_text = match.group(1).strip()
        block = match.group(2)
        selectors = tuple(part.strip() for part in selector_text.split(",") if part.strip())
        declarations: dict[str, str] = {}
        for decl in block.split(";"):
            if ":" not in decl:
                continue
            name, value = decl.split(":", 1)
            key = name.strip().lower()
            if key:
                declarations[key] = value.strip()
        if selectors:
            rules.append(_CssRule(selectors=selectors, declarations=declarations))
    return rules


class _PageParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.root = _DomNode(tag="document", attrs={})
        self._stack: list[_DomNode] = [self.root]
        self._style_text: str | None = None
        self._capture_style = False
        self._style_chunks: list[str] = []

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.handle_starttag(tag, attrs)

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        normalized = tag.lower()
        attr_map = {name.lower(): (value if value is not None else "") for name, value in attrs}
        parent = self._stack[-1]
        node = _DomNode(tag=normalized, attrs=attr_map, parent=parent)
        parent.children.append(node)
        if normalized == "style" and self._style_text is None:
            self._capture_style = True
            self._style_chunks = []
        if normalized in VOID_HTML_ELEMENTS:
            return
        self._stack.append(node)

    def handle_endtag(self, tag: str) -> None:
        normalized = tag.lower()
        if normalized == "style" and self._capture_style:
            self._capture_style = False
            self._style_text = "".join(self._style_chunks)
        if len(self._stack) > 1 and self._stack[-1].tag == normalized:
            self._stack.pop()

    def handle_data(self, data: str) -> None:
        if self._capture_style:
            self._style_chunks.append(data)
            return
        if len(self._stack) > 1:
            self._stack[-1].direct_text.append(data)


def _parse_html(page_html: str) -> tuple[_DomNode, str]:
    parser = _PageParser()
    parser.feed(page_html)
    parser.close()
    return parser.root, parser._style_text or ""


def parse_css_color(value: str) -> tuple[int, int, int] | None:
    text = value.strip().lower()
    if not text:
        return None
    if text in CSS_NAMED_COLORS:
        return CSS_NAMED_COLORS[text]
    if text.startswith("#"):
        return _parse_hex_color(text)
    rgb_match = re.fullmatch(
        r"rgba?\(\s*([0-9.]+)\s*,\s*([0-9.]+)\s*,\s*([0-9.]+)\s*(?:,\s*([0-9.]+)\s*)?\)",
        text,
    )
    if rgb_match:
        alpha_text = rgb_match.group(4)
        if alpha_text is not None and float(alpha_text) != 1.0:
            return None
        channels = (
            _clamp_channel(float(rgb_match.group(1))),
            _clamp_channel(float(rgb_match.group(2))),
            _clamp_channel(float(rgb_match.group(3))),
        )
        return channels
    return None


def _parse_hex_color(value: str) -> tuple[int, int, int] | None:
    hex_body = value[1:]
    if len(hex_body) == 3:
        try:
            return (
                int(hex_body[0] * 2, 16),
                int(hex_body[1] * 2, 16),
                int(hex_body[2] * 2, 16),
            )
        except ValueError:
            return None
    if len(hex_body) == 6:
        try:
            return (
                int(hex_body[0:2], 16),
                int(hex_body[2:4], 16),
                int(hex_body[4:6], 16),
            )
        except ValueError:
            return None
    return None


def _clamp_channel(value: float) -> int:
    if value <= 1.0:
        value *= 255.0
    return max(0, min(255, int(round(value))))


def _relative_luminance(rgb: tuple[int, int, int]) -> float:
    def channel(value: int) -> float:
        scaled = value / 255.0
        if scaled <= 0.03928:
            return scaled / 12.92
        return ((scaled + 0.055) / 1.055) ** 2.4

    red, green, blue = rgb
    return 0.2126 * channel(red) + 0.7152 * channel(green) + 0.0722 * channel(blue)


def _contrast_ratio(fg: tuple[int, int, int], bg: tuple[int, int, int]) -> float:
    l1 = _relative_luminance(fg)
    l2 = _relative_luminance(bg)
    lighter = max(l1, l2)
    darker = min(l1, l2)
    return (lighter + 0.05) / (darker + 0.05)
