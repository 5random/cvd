from __future__ import annotations

import json


def reload_config(service) -> None:
    """Reload configuration for the given service."""
    service._load_config()


def reset_to_defaults(service) -> None:
    """Reset configuration using default file."""
    if service.default_config_path.exists():
        with open(service.default_config_path, "r", encoding="utf-8") as f:
            service._config_cache = json.load(f)
        service._save_config()
