import os
import re

# Pattern for allowed IDs: letters, digits, underscore, dash and dot
ID_PATTERN = re.compile(r"^[A-Za-z0-9_.-]+$")


def sanitize_id(id_str: str) -> str:
    """Return a safe string usable as filename."""
    sanitized = id_str.replace(os.sep, "_")
    if os.altsep:
        sanitized = sanitized.replace(os.altsep, "_")
    sanitized = re.sub(r"[^A-Za-z0-9_.-]", "_", sanitized)
    return sanitized
