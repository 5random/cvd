from __future__ import annotations

import logging
from jsonschema import Draft7Validator
from typing import Dict, Any, List, Set

# Use a differently named variable so test fixtures that monkeypatch a
# ``warning`` attribute on this module do not silence standard logging.
log_warning = logging.warning


def validate_config(
    config: Dict[str, Any], schema: Dict[str, Any], config_type: str
) -> List[str]:
    """Validate configuration against schema and return list of errors."""
    validator = Draft7Validator(schema)
    errors: List[str] = []
    for err in validator.iter_errors(config):
        path = ".".join(str(p) for p in err.path)
        message = f"{path}: {err.message}" if path else err.message
        errors.append(message)

    known_fields: Set[str] = set(schema.get("properties", {}).keys())
    known_fields.update({"sensor_id", "controller_id", "algorithm_id", "webcam_id"})
    for field in set(config.keys()) - known_fields:
        log_warning(f"Unknown field in {config_type} config: {field}")

    return errors
