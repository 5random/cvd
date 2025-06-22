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
    # Elements from alt_gui_elements
    "WebcamStreamElement": ".alt_gui_elements",
    "EmailAlertsSection": ".alt_gui_elements",
    "ExperimentManagementSection": ".alt_gui_elements",
    "MotionStatusSection": ".alt_gui_elements",
    "create_compact_alert_widget": ".alt_gui_elements",
    "create_demo_configurations": ".alt_gui_elements",
    "create_email_alert_status_display": ".alt_gui_elements",
    "create_email_alert_wizard": ".alt_gui_elements",
    "EmailAlertStatusDisplay": ".alt_gui_elements",
    "load_alert_configs": ".alt_gui_elements",
    "save_alert_configs": ".alt_gui_elements",
    # styling helpers
    "setup_global_styles": ".theme",
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
