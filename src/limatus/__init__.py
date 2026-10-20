"""Limatus: a diagnose-and-steer quality loop for AI-generated content."""

__version__ = "0.30.0"

from .calibration import apply_calibration, calibrate
from .check import CheckRequestValidationError, check
from .contracts import ContractValidationError, load_schema, validate_payload
from .finding_ids import finding_id
from .policy_pack import PolicyPack, PolicyPackValidationError, load_policy_pack
from .segmentation import SegmentedDocument, segment_document
from .style_profile_import import policy_pack_from_style_profile
from .suggest import SuggestRequestValidationError, SuggestUnavailableError, draft_questions, suggest
from .sdk import (
    AnnotationFormatError,
    EditorialDiagnosisValidationError,
    EditorialLoopValidationError,
    EditorialOptionsValidationError,
    LoadedStyleProfile,
    StyleProfileValidationError,
    candidates_from_options,
    compare,
    compose_loop_record,
    diagnose,
    scan,
    verify,
    check_rules,
    check_standfirst,
    generate_options,
    suggest_rewrite,
    generate_suggestions,
    load_config,
    preview_patch_text,
    record_decision,
    render_annotations,
)

__all__ = [
    "CheckRequestValidationError",
    "ContractValidationError",
    "PolicyPack",
    "PolicyPackValidationError",
    "SegmentedDocument",
    "SuggestRequestValidationError",
    "SuggestUnavailableError",
    "apply_calibration",
    "calibrate",
    "check",
    "draft_questions",
    "suggest",
    "finding_id",
    "load_policy_pack",
    "load_schema",
    "policy_pack_from_style_profile",
    "segment_document",
    "validate_payload",
    "AnnotationFormatError",
    "EditorialDiagnosisValidationError",
    "EditorialLoopValidationError",
    "EditorialOptionsValidationError",
    "LoadedStyleProfile",
    "StyleProfileValidationError",
    "__version__",
    "candidates_from_options",
    "compare",
    "compose_loop_record",
    "diagnose",
    "preview_patch_text",
    "scan",
    "verify",
    "check_rules",
    "check_standfirst",
    "generate_options",
    "suggest_rewrite",
    "generate_suggestions",
    "load_config",
    "record_decision",
    "render_annotations",
]
