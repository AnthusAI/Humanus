from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from humanus.usability_profile import (  # noqa: E402
    UsabilityProfileValidationError,
    load_usability_profile,
)
from humanus.usability_scan import (  # noqa: E402
    USABILITY_FORBIDDEN_OUTPUT_KEYS,
    parse_css_color,
    scan_html_page,
    validate_usability_findings,
)

FIXTURE_ROOT = ROOT / "tests/fixtures/usability-scan"
BOTH_PAGE = FIXTURE_ROOT / "both-findings.html"
MINIMAL_PAGE = FIXTURE_ROOT / "minimal.html"
PROFILE = FIXTURE_ROOT / "profile.yml"


class UsabilityScanTests(unittest.TestCase):
    def test_both_findings_page_reports_missing_alt_and_low_contrast(self):
        profile = load_usability_profile(PROFILE)
        html = BOTH_PAGE.read_text(encoding="utf-8")
        payload = scan_html_page(html, profile=profile)
        self.assertEqual(payload["schemaVersion"], 1)
        kinds = {entry["kind"] for entry in payload["findings"]}
        self.assertEqual(kinds, {"missing_alt", "low_contrast"})
        self.assertNotIn("suppressed_focus_outline", kinds)
        for key in USABILITY_FORBIDDEN_OUTPUT_KEYS:
            self.assertNotIn(key, json.dumps(payload))
        missing = next(entry for entry in payload["findings"] if entry["kind"] == "missing_alt")
        self.assertIn("img", missing["selector"])
        low = next(entry for entry in payload["findings"] if entry["kind"] == "low_contrast")
        self.assertIn("ratio", low)
        self.assertLess(low["ratio"], 4.5)

    def test_minimal_page_has_no_findings(self):
        profile = load_usability_profile(PROFILE)
        html = MINIMAL_PAGE.read_text(encoding="utf-8")
        payload = scan_html_page(html, profile=profile)
        self.assertEqual(payload["findings"], [])

    def test_small_tap_target_flags_16px_button(self):
        profile = load_usability_profile(PROFILE)
        html = '<!DOCTYPE html><html><body><button width="16" height="16">Go</button></body></html>'
        payload = scan_html_page(html, profile=profile)
        tap = [entry for entry in payload["findings"] if entry["kind"] == "small_tap_target"]
        self.assertEqual(len(tap), 1)
        self.assertEqual(tap[0]["width"], 16.0)
        self.assertEqual(tap[0]["height"], 16.0)
        validate_usability_findings(payload)

    def test_24px_control_does_not_flag_small_tap_target(self):
        profile = load_usability_profile(PROFILE)
        html = '<!DOCTYPE html><html><body><button width="24" height="24">Go</button></body></html>'
        payload = scan_html_page(html, profile=profile)
        tap = [entry for entry in payload["findings"] if entry["kind"] == "small_tap_target"]
        self.assertEqual(tap, [])

    def test_unsized_link_does_not_flag_small_tap_target(self):
        profile = load_usability_profile(PROFILE)
        html = '<!DOCTYPE html><html><body><a href="/x">Home</a></body></html>'
        payload = scan_html_page(html, profile=profile)
        tap = [entry for entry in payload["findings"] if entry["kind"] == "small_tap_target"]
        self.assertEqual(tap, [])

    def test_suppressed_focus_outline_flags_button_focus_none(self):
        profile = load_usability_profile(PROFILE)
        html = """<!DOCTYPE html><html><head><style>
        button:focus { outline: none }
        </style></head><body><button>Go</button></body></html>"""
        payload = scan_html_page(html, profile=profile)
        suppressed = [
            entry for entry in payload["findings"] if entry["kind"] == "suppressed_focus_outline"
        ]
        self.assertEqual(len(suppressed), 1)
        self.assertEqual(suppressed[0]["selector"], "button")

    def test_suppressed_focus_outline_skips_when_box_shadow_focus_ring(self):
        profile = load_usability_profile(PROFILE)
        html = """<!DOCTYPE html><html><head><style>
        button:focus { outline: none; box-shadow: 0 0 0 2px #000 }
        </style></head><body><button>Go</button></body></html>"""
        payload = scan_html_page(html, profile=profile)
        suppressed = [
            entry for entry in payload["findings"] if entry["kind"] == "suppressed_focus_outline"
        ]
        self.assertEqual(suppressed, [])

    def test_flag_suppressed_outline_false_disables_finding(self):
        with tempfile.TemporaryDirectory() as tmp:
            profile_path = Path(tmp) / "no-focus.yml"
            profile_path.write_text(
                "focus:\n  flagSuppressedOutline: false\n",
                encoding="utf-8",
            )
            profile = load_usability_profile(profile_path)
            html = """<!DOCTYPE html><html><head><style>
            button:focus { outline: none }
            </style></head><body><button>Go</button></body></html>"""
            payload = scan_html_page(html, profile=profile)
            suppressed = [
                entry for entry in payload["findings"] if entry["kind"] == "suppressed_focus_outline"
            ]
            self.assertEqual(suppressed, [])

    def test_tap_target_only_profile_uses_default_focus_flag(self):
        with tempfile.TemporaryDirectory() as tmp:
            profile_path = Path(tmp) / "tap-only.yml"
            profile_path.write_text("tapTarget:\n  minPx: 24\n", encoding="utf-8")
            loaded = load_usability_profile(profile_path)
            self.assertTrue(loaded.profile.focus.flag_suppressed_outline)
            html = """<!DOCTYPE html><html><head><style>
            button:focus { outline: none }
            </style></head><body><button>Go</button></body></html>"""
            payload = scan_html_page(html, profile=loaded)
            self.assertEqual(
                len([f for f in payload["findings"] if f["kind"] == "suppressed_focus_outline"]),
                1,
            )

    def test_contrast_only_profile_uses_default_tap_target_min_px(self):
        with tempfile.TemporaryDirectory() as tmp:
            profile_path = Path(tmp) / "contrast-only.yml"
            profile_path.write_text("contrast:\n  minRatio: 4.5\n", encoding="utf-8")
            loaded = load_usability_profile(profile_path)
            self.assertEqual(loaded.profile.tap_target.min_px, 24)
            html = '<!DOCTYPE html><html><body><button width="16" height="16">Go</button></body></html>'
            payload = scan_html_page(html, profile=loaded)
            self.assertEqual(len([f for f in payload["findings"] if f["kind"] == "small_tap_target"]), 1)

    def test_bare_text_input_flags_missing_accessible_name(self):
        profile = load_usability_profile(PROFILE)
        html = '<!DOCTYPE html><html><body><input type="text"></body></html>'
        payload = scan_html_page(html, profile=profile)
        missing = [f for f in payload["findings"] if f["kind"] == "missing_accessible_name"]
        self.assertEqual(len(missing), 1)
        self.assertIn("input", missing[0]["selector"])

    def test_wrapping_label_does_not_flag_missing_accessible_name(self):
        profile = load_usability_profile(PROFILE)
        html = '<!DOCTYPE html><html><body><label>Name <input type="text"></label></body></html>'
        payload = scan_html_page(html, profile=profile)
        missing = [f for f in payload["findings"] if f["kind"] == "missing_accessible_name"]
        self.assertEqual(missing, [])

    def test_label_for_id_does_not_flag_missing_accessible_name(self):
        profile = load_usability_profile(PROFILE)
        html = (
            '<!DOCTYPE html><html><body>'
            '<label for="n">Name</label><input id="n" type="text">'
            "</body></html>"
        )
        payload = scan_html_page(html, profile=profile)
        missing = [f for f in payload["findings"] if f["kind"] == "missing_accessible_name"]
        self.assertEqual(missing, [])

    def test_aria_label_does_not_flag_missing_accessible_name(self):
        profile = load_usability_profile(PROFILE)
        html = '<!DOCTYPE html><html><body><input type="text" aria-label="Search"></body></html>'
        payload = scan_html_page(html, profile=profile)
        missing = [f for f in payload["findings"] if f["kind"] == "missing_accessible_name"]
        self.assertEqual(missing, [])

    def test_both_findings_page_has_no_missing_accessible_name(self):
        profile = load_usability_profile(PROFILE)
        payload = scan_html_page(BOTH_PAGE.read_text(encoding="utf-8"), profile=profile)
        kinds = {entry["kind"] for entry in payload["findings"]}
        self.assertNotIn("missing_accessible_name", kinds)

    def test_minimal_page_has_no_missing_accessible_name(self):
        profile = load_usability_profile(PROFILE)
        payload = scan_html_page(MINIMAL_PAGE.read_text(encoding="utf-8"), profile=profile)
        kinds = {entry["kind"] for entry in payload["findings"]}
        self.assertNotIn("missing_accessible_name", kinds)

    def test_flag_missing_false_disables_missing_accessible_name(self):
        with tempfile.TemporaryDirectory() as tmp:
            profile_path = Path(tmp) / "no-name.yml"
            profile_path.write_text(
                "accessibleName:\n  flagMissing: false\n",
                encoding="utf-8",
            )
            profile = load_usability_profile(profile_path)
            html = '<!DOCTYPE html><html><body><input type="text"></body></html>'
            payload = scan_html_page(html, profile=profile)
            missing = [f for f in payload["findings"] if f["kind"] == "missing_accessible_name"]
            self.assertEqual(missing, [])

    def test_missing_lang_flags_html_without_lang(self):
        profile = load_usability_profile(PROFILE)
        html = "<html><body></body></html>"
        payload = scan_html_page(html, profile=profile)
        missing = [f for f in payload["findings"] if f["kind"] == "missing_lang"]
        self.assertEqual(len(missing), 1)
        self.assertEqual(missing[0]["selector"], "html")

    def test_missing_lang_skips_when_lang_present(self):
        profile = load_usability_profile(PROFILE)
        html = '<html lang="en"><body></body></html>'
        payload = scan_html_page(html, profile=profile)
        missing = [f for f in payload["findings"] if f["kind"] == "missing_lang"]
        self.assertEqual(missing, [])

    def test_both_findings_page_has_no_missing_lang(self):
        profile = load_usability_profile(PROFILE)
        payload = scan_html_page(BOTH_PAGE.read_text(encoding="utf-8"), profile=profile)
        kinds = {entry["kind"] for entry in payload["findings"]}
        self.assertNotIn("missing_lang", kinds)

    def test_minimal_page_has_no_missing_lang(self):
        profile = load_usability_profile(PROFILE)
        payload = scan_html_page(MINIMAL_PAGE.read_text(encoding="utf-8"), profile=profile)
        kinds = {entry["kind"] for entry in payload["findings"]}
        self.assertNotIn("missing_lang", kinds)

    def test_flag_missing_false_disables_missing_lang(self):
        with tempfile.TemporaryDirectory() as tmp:
            profile_path = Path(tmp) / "no-lang.yml"
            profile_path.write_text("lang:\n  flagMissing: false\n", encoding="utf-8")
            profile = load_usability_profile(profile_path)
            html = "<html><body></body></html>"
            payload = scan_html_page(html, profile=profile)
            missing = [f for f in payload["findings"] if f["kind"] == "missing_lang"]
            self.assertEqual(missing, [])

    def test_html_fragment_without_html_element_has_no_missing_lang(self):
        profile = load_usability_profile(PROFILE)
        html = "<body><p>Fragment</p></body>"
        payload = scan_html_page(html, profile=profile)
        missing = [f for f in payload["findings"] if f["kind"] == "missing_lang"]
        self.assertEqual(missing, [])

    def test_profile_rejects_unknown_keys(self):
        with tempfile.TemporaryDirectory() as tmp:
            bad_path = Path(tmp) / "bad-profile.yml"
            bad_path.write_text(
                "contrast:\n  minRatio: 4.5\nunknown: true\n",
                encoding="utf-8",
            )
            with self.assertRaises(UsabilityProfileValidationError):
                load_usability_profile(bad_path)

    def test_emoji_heading_flags_h1_with_emoji(self):
        profile = load_usability_profile(PROFILE)
        html = "<!DOCTYPE html><html><body><h1>🚀 Launch</h1></body></html>"
        payload = scan_html_page(html, profile=profile)
        emoji = [f for f in payload["findings"] if f["kind"] == "emoji_heading"]
        self.assertEqual(len(emoji), 1)
        self.assertEqual(emoji[0]["selector"], "h1")

    def test_emoji_heading_ignores_emoji_in_non_headings(self):
        profile = load_usability_profile(PROFILE)
        html = "<!DOCTYPE html><html><body><h1>Launch</h1><p>🚀</p></body></html>"
        payload = scan_html_page(html, profile=profile)
        emoji = [f for f in payload["findings"] if f["kind"] == "emoji_heading"]
        self.assertEqual(emoji, [])

    def test_both_findings_page_has_no_emoji_heading(self):
        profile = load_usability_profile(PROFILE)
        payload = scan_html_page(BOTH_PAGE.read_text(encoding="utf-8"), profile=profile)
        kinds = {entry["kind"] for entry in payload["findings"]}
        self.assertNotIn("emoji_heading", kinds)

    def test_minimal_page_has_no_emoji_heading(self):
        profile = load_usability_profile(PROFILE)
        payload = scan_html_page(MINIMAL_PAGE.read_text(encoding="utf-8"), profile=profile)
        kinds = {entry["kind"] for entry in payload["findings"]}
        self.assertNotIn("emoji_heading", kinds)

    def test_flag_in_headings_false_disables_emoji_heading(self):
        with tempfile.TemporaryDirectory() as tmp:
            profile_path = Path(tmp) / "no-emoji.yml"
            profile_path.write_text("emoji:\n  flagInHeadings: false\n", encoding="utf-8")
            profile = load_usability_profile(profile_path)
            html = "<!DOCTYPE html><html><body><h1>🚀 Launch</h1></body></html>"
            payload = scan_html_page(html, profile=profile)
            emoji = [f for f in payload["findings"] if f["kind"] == "emoji_heading"]
            self.assertEqual(emoji, [])

    def test_generic_gradient_hero_flags_body_linear_gradient(self):
        profile = load_usability_profile(PROFILE)
        html = """<!DOCTYPE html><html><head><style>
        body { background: linear-gradient(to bottom, #fff, #eee); }
        </style></head><body><p>Hi</p></body></html>"""
        payload = scan_html_page(html, profile=profile)
        gradient = [f for f in payload["findings"] if f["kind"] == "generic_gradient_hero"]
        self.assertEqual(len(gradient), 1)
        self.assertEqual(gradient[0]["selector"], "body")

    def test_generic_gradient_hero_ignores_button_linear_gradient(self):
        profile = load_usability_profile(PROFILE)
        html = """<!DOCTYPE html><html><head><style>
        button { background-image: linear-gradient(90deg, red, blue); }
        </style></head><body><button>Go</button></body></html>"""
        payload = scan_html_page(html, profile=profile)
        gradient = [f for f in payload["findings"] if f["kind"] == "generic_gradient_hero"]
        self.assertEqual(gradient, [])

    def test_generic_gradient_hero_hero_rule_without_matching_element(self):
        profile = load_usability_profile(PROFILE)
        html = """<!DOCTYPE html><html><head><style>
        .hero { background: linear-gradient(#000, #111); }
        </style></head><body><div class="banner">X</div></body></html>"""
        payload = scan_html_page(html, profile=profile)
        gradient = [f for f in payload["findings"] if f["kind"] == "generic_gradient_hero"]
        self.assertEqual(gradient, [])

    def test_flag_gradient_hero_false_disables_generic_gradient_hero(self):
        with tempfile.TemporaryDirectory() as tmp:
            profile_path = Path(tmp) / "no-gradient-hero.yml"
            profile_path.write_text("template:\n  flagGradientHero: false\n", encoding="utf-8")
            profile = load_usability_profile(profile_path)
            html = """<!DOCTYPE html><html><head><style>
            body { background: linear-gradient(to bottom, #fff, #eee); }
            </style></head><body></body></html>"""
            payload = scan_html_page(html, profile=profile)
            gradient = [f for f in payload["findings"] if f["kind"] == "generic_gradient_hero"]
            self.assertEqual(gradient, [])

    def test_both_findings_page_has_no_generic_gradient_hero(self):
        profile = load_usability_profile(PROFILE)
        payload = scan_html_page(BOTH_PAGE.read_text(encoding="utf-8"), profile=profile)
        kinds = {entry["kind"] for entry in payload["findings"]}
        self.assertNotIn("generic_gradient_hero", kinds)

    def test_minimal_page_has_no_generic_gradient_hero(self):
        profile = load_usability_profile(PROFILE)
        payload = scan_html_page(MINIMAL_PAGE.read_text(encoding="utf-8"), profile=profile)
        kinds = {entry["kind"] for entry in payload["findings"]}
        self.assertNotIn("generic_gradient_hero", kinds)

    def test_generic_feature_row_flags_parent_with_three_cards_and_images(self):
        profile = load_usability_profile(PROFILE)
        html = """<!DOCTYPE html><html><body><section>
        <div class="card"><img src="a" alt=""></div>
        <div class="card"><img src="b" alt=""></div>
        <div class="card"><img src="c" alt=""></div>
        </section></body></html>"""
        payload = scan_html_page(html, profile=profile)
        feature_rows = [f for f in payload["findings"] if f["kind"] == "generic_feature_row"]
        self.assertEqual(len(feature_rows), 1)
        self.assertEqual(feature_rows[0]["selector"], "section")

    def test_generic_feature_row_ignores_two_cards_with_images(self):
        profile = load_usability_profile(PROFILE)
        html = """<!DOCTYPE html><html><body><section>
        <div class="card"><img src="a" alt=""></div>
        <div class="card"><img src="b" alt=""></div>
        </section></body></html>"""
        payload = scan_html_page(html, profile=profile)
        feature_rows = [f for f in payload["findings"] if f["kind"] == "generic_feature_row"]
        self.assertEqual(feature_rows, [])

    def test_generic_feature_row_ignores_three_cards_without_images(self):
        profile = load_usability_profile(PROFILE)
        html = """<!DOCTYPE html><html><body><section>
        <div class="card"><p>One</p></div>
        <div class="card"><p>Two</p></div>
        <div class="card"><p>Three</p></div>
        </section></body></html>"""
        payload = scan_html_page(html, profile=profile)
        feature_rows = [f for f in payload["findings"] if f["kind"] == "generic_feature_row"]
        self.assertEqual(feature_rows, [])

    def test_flag_feature_row_false_disables_generic_feature_row(self):
        with tempfile.TemporaryDirectory() as tmp:
            profile_path = Path(tmp) / "no-feature-row.yml"
            profile_path.write_text("template:\n  flagFeatureRow: false\n", encoding="utf-8")
            profile = load_usability_profile(profile_path)
            html = """<!DOCTYPE html><html><body><section>
            <div class="card"><img src="a" alt=""></div>
            <div class="card"><img src="b" alt=""></div>
            <div class="card"><img src="c" alt=""></div>
            </section></body></html>"""
            payload = scan_html_page(html, profile=profile)
            feature_rows = [f for f in payload["findings"] if f["kind"] == "generic_feature_row"]
            self.assertEqual(feature_rows, [])

    def test_template_only_flag_gradient_hero_defaults_flag_feature_row_true(self):
        with tempfile.TemporaryDirectory() as tmp:
            profile_path = Path(tmp) / "gradient-only.yml"
            profile_path.write_text("template:\n  flagGradientHero: true\n", encoding="utf-8")
            profile = load_usability_profile(profile_path)
            self.assertTrue(profile.profile.template.flag_feature_row)
            html = """<!DOCTYPE html><html><body><section>
            <div class="card"><img src="a" alt=""></div>
            <div class="card"><img src="b" alt=""></div>
            <div class="card"><img src="c" alt=""></div>
            </section></body></html>"""
            payload = scan_html_page(html, profile=profile)
            feature_rows = [f for f in payload["findings"] if f["kind"] == "generic_feature_row"]
            self.assertEqual(len(feature_rows), 1)

    def test_void_img_does_not_swallow_following_siblings(self):
        profile = load_usability_profile(PROFILE)
        html = """<!DOCTYPE html>
<html><head><style>.muted { color: #777777; background-color: #888888; }</style></head>
<body><img src="x"><p class="muted">Low contrast</p></body></html>"""
        payload = scan_html_page(html, profile=profile)
        missing = next(entry for entry in payload["findings"] if entry["kind"] == "missing_alt")
        low = next(entry for entry in payload["findings"] if entry["kind"] == "low_contrast")
        self.assertEqual(missing["selector"], "img")
        self.assertEqual(low["selector"], "p.muted")

    def test_invalid_three_digit_hex_color_returns_none(self):
        self.assertIsNone(parse_css_color("#ggg"))

    def test_cli_usability_scan_writes_json(self):
        env = {**os.environ, "PYTHONPATH": str(SRC)}
        with tempfile.TemporaryDirectory() as tmp:
            output_path = Path(tmp) / "findings.json"
            completed = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "humanus",
                    "usability",
                    "scan",
                    "--page",
                    str(BOTH_PAGE),
                    "--profile",
                    str(PROFILE),
                    "--output",
                    str(output_path),
                ],
                cwd=ROOT,
                env=env,
                capture_output=True,
                text=True,
                check=True,
            )
            self.assertEqual(completed.stdout, "")
            payload = json.loads(output_path.read_text(encoding="utf-8"))
            validate_usability_findings(payload)
            self.assertEqual(len(payload["findings"]), 2)

    def test_cli_scan_does_not_modify_page_file(self):
        env = {**os.environ, "PYTHONPATH": str(SRC)}
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            page_copy = tmp_path / "page.html"
            page_copy.write_bytes(BOTH_PAGE.read_bytes())
            before = page_copy.read_bytes()
            output_path = tmp_path / "findings.json"
            subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "humanus",
                    "usability",
                    "scan",
                    "--page",
                    str(page_copy),
                    "--profile",
                    str(PROFILE),
                    "--output",
                    str(output_path),
                ],
                cwd=ROOT,
                env=env,
                capture_output=True,
                text=True,
                check=True,
            )
            self.assertEqual(page_copy.read_bytes(), before)


if __name__ == "__main__":
    unittest.main()
