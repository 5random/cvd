from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict


def deep_merge(default: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    """Deep merge two dictionaries."""
    result = default.copy()
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def load_config(config_path: Path, default_config_path: Path) -> Dict[str, Any]:
    """Load configuration from disk and merge with defaults."""
    default_config: Dict[str, Any] = {}
    if default_config_path.exists():
        with open(default_config_path, "r", encoding="utf-8") as f:
            default_config = json.load(f)

    user_config: Dict[str, Any] = {}
    if config_path.exists():
        with open(config_path, "r", encoding="utf-8") as f:
            user_config = json.load(f)

    return deep_merge(default_config, user_config)


def save_config(config: Dict[str, Any], path: Path) -> None:
    """Persist configuration dictionary to disk."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2, ensure_ascii=False)
