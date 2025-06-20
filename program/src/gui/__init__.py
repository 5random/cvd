"""Web GUI built with NiceGUI.

This package exposes the standard application as well as a lightweight
alternative implementation.  The heavy modules are imported lazily to avoid
circular import issues during test collection.
"""

from __future__ import annotations

import importlib
from typing import Any

_LAZY_ATTRS = {
    "application": ".application",
    "alt_application": ".alt_application",
    "alt_gui": ".alt_gui",
    "WebApplication": ".application",
    "SimpleGUIApplication": ".alt_application",
}


def __getattr__(name: str) -> Any:  # pragma: no cover - simple passthrough
    """Lazily import submodules and classes on first access."""

    module_path = _LAZY_ATTRS.get(name)
    if module_path is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

    module = importlib.import_module(module_path, __name__)
    if name in {"WebApplication", "SimpleGUIApplication"}:
        attr = getattr(module, name)
    else:
        attr = module
    globals()[name] = attr
    return attr


__all__ = list(_LAZY_ATTRS.keys())

