"""Limatus: a configurable editorial compliance engine.

A caller sends content and a policy pack; ``check`` returns where the content
breaks the pack's policies, ``suggest`` offers rewrites for a finding or any
selection, ``draft_questions`` helps write classifier detectors, and
``calibrate`` learns from editors' decisions. The JSON Schemas under
``limatus/schemas`` are the contract (``load_schema``).
"""

__version__ = "0.32.0"

from .calibration import apply_calibration, calibrate
from .check import CheckRequestValidationError, check
from .contracts import ContractValidationError, load_schema, validate_payload
from .finding_ids import finding_id
from .packs import builtin_pack, list_builtin_packs
from .policy_pack import PolicyPack, PolicyPackValidationError, load_policy_pack
from .segmentation import SegmentedDocument, segment_document
from .style_profile_import import StyleProfileImportError, policy_pack_from_style_profile
from .suggest import SuggestRequestValidationError, SuggestUnavailableError, draft_questions, suggest

__all__ = [
    "CheckRequestValidationError",
    "ContractValidationError",
    "PolicyPack",
    "PolicyPackValidationError",
    "SegmentedDocument",
    "StyleProfileImportError",
    "SuggestRequestValidationError",
    "SuggestUnavailableError",
    "__version__",
    "apply_calibration",
    "builtin_pack",
    "calibrate",
    "check",
    "draft_questions",
    "finding_id",
    "list_builtin_packs",
    "load_policy_pack",
    "load_schema",
    "policy_pack_from_style_profile",
    "segment_document",
    "suggest",
    "validate_payload",
]
