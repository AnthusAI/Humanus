"""Published JSON Schema contracts for policy packs, check and suggest.

The schema files under ``limatus/schemas`` are the single source of truth for
the payloads a caller (for example a CMS) exchanges with Limatus. Callers in
other languages validate against the same files; ``limatus schema <name>``
prints them.
"""
from __future__ import annotations

import json
from functools import lru_cache
from importlib import resources
from typing import Any

from jsonschema import Draft202012Validator
from jsonschema.exceptions import best_match
from referencing import Registry, Resource

SCHEMA_BASE_URI = "https://limatus.anth.us/schemas/"

CONTRACT_SCHEMAS = (
    "policy-pack-v1",
    "check-request-v1",
    "check-result-v1",
    "finding-v1",
    "suggest-request-v1",
    "suggest-result-v1",
    "draft-questions-request-v1",
    "draft-questions-result-v1",
)


class ContractValidationError(ValueError):
    """A payload does not satisfy its published contract.

    ``location`` is the slash-separated path to the offending value
    (empty for the document root).
    """

    def __init__(self, schema_name: str, message: str, location: str = "") -> None:
        self.schema_name = schema_name
        self.location = location
        where = f" at '{location}'" if location else ""
        super().__init__(f"Invalid {schema_name}{where}: {message}")


def load_schema(name: str) -> dict[str, Any]:
    """Return a published schema by name, e.g. ``"policy-pack-v1"``."""
    if name not in CONTRACT_SCHEMAS:
        raise KeyError(f"Unknown contract schema '{name}'. Known: {', '.join(CONTRACT_SCHEMAS)}")
    return json.loads(_schema_text(name))


def validate_payload(
    name: str,
    payload: Any,
    error_class: type[ContractValidationError] = ContractValidationError,
) -> None:
    """Raise ``error_class`` if ``payload`` does not satisfy schema ``name``."""
    error = best_match(_validator(name).iter_errors(payload))
    if error is not None:
        location = "/".join(str(part) for part in error.absolute_path)
        raise error_class(name, error.message, location)


@lru_cache(maxsize=None)
def _schema_text(name: str) -> str:
    return resources.files("limatus").joinpath("schemas", f"{name}.json").read_text(encoding="utf-8")


@lru_cache(maxsize=None)
def _registry() -> Registry:
    resources_by_uri = [
        (SCHEMA_BASE_URI + f"{name}.json", Resource.from_contents(json.loads(_schema_text(name))))
        for name in CONTRACT_SCHEMAS
    ]
    return Registry().with_resources(resources_by_uri)


@lru_cache(maxsize=None)
def _validator(name: str) -> Draft202012Validator:
    return Draft202012Validator(load_schema(name), registry=_registry())
