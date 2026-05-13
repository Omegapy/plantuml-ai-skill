"""Small stdlib JSON-schema subset validator for corpus records."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .constants import DEFAULT_SCHEMA_PATH


def load_schema(path: Path | str = DEFAULT_SCHEMA_PATH) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def validate_against_schema(
    data: dict[str, Any],
    schema: dict[str, Any] | None = None,
) -> list[str]:
    """Validate the subset of JSON Schema used by this project.

    This intentionally covers required fields, primitive types, arrays, string
    minLength, and enums without adding a runtime dependency.
    """

    schema = schema or load_schema()
    errors: list[str] = []
    for key in schema.get("required", []):
        if key not in data:
            errors.append(f"missing required field: {key}")
    properties = schema.get("properties", {})
    for key, value in data.items():
        prop = properties.get(key)
        if not prop:
            continue
        expected_type = prop.get("type")
        if expected_type and not _matches_type(value, expected_type):
            errors.append(f"{key}: expected {expected_type}, got {type(value).__name__}")
            continue
        if expected_type == "string" and prop.get("minLength") and len(value) < int(prop["minLength"]):
            errors.append(f"{key}: shorter than minLength {prop['minLength']}")
        if "enum" in prop and value not in prop["enum"]:
            errors.append(f"{key}: {value!r} is not one of {prop['enum']}")
        if expected_type == "array" and isinstance(value, list):
            item_type = prop.get("items", {}).get("type")
            if item_type:
                for index, item in enumerate(value):
                    if not _matches_type(item, item_type):
                        errors.append(
                            f"{key}[{index}]: expected {item_type}, got {type(item).__name__}"
                        )
    return errors


def _matches_type(value: Any, expected_type: str) -> bool:
    if expected_type == "object":
        return isinstance(value, dict)
    if expected_type == "array":
        return isinstance(value, list)
    if expected_type == "string":
        return isinstance(value, str)
    if expected_type == "boolean":
        return isinstance(value, bool)
    if expected_type == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected_type == "number":
        return (isinstance(value, int) or isinstance(value, float)) and not isinstance(value, bool)
    return True
