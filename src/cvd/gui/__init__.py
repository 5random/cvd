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
    "SimpleGUIApplication": ".alt_application",
    "WebcamStreamElement": ".alt_gui_elements.webcam_stream_element",
    "EmailAlertsSection": ".alt_gui_elements.alert_element",
    "EmailAlertStatusDisplay": ".alt_gui_elements.alert_element",
    "ExperimentManagementSection": ".alt_gui_elements.experiment_element",
    "MotionStatusSection": ".alt_gui_elements.motion_detection_element",
    "create_compact_alert_widget": ".alt_gui_elements.alert_element",
    "create_demo_configurations": ".alt_gui_elements.alert_element",
    "create_email_alert_status_display": ".alt_gui_elements.alert_element",
    "create_email_alert_wizard": ".alt_gui_elements.alert_element",
    "load_alert_configs": ".alt_gui_elements.alert_element",
    "save_alert_configs": ".alt_gui_elements.alert_element",
    "setup_global_styles": ".theme",
}


def __getattr__(name: str) -> Any:  # pragma: no cover - simple passthrough
    """Lazily import submodules and classes on first access."""

    module_path = _LAZY_ATTRS.get(name)
    if module_path is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

    module = importlib.import_module(module_path, __name__)
    # return the attribute if present on the module, otherwise the module itself
    if hasattr(module, name):
        attr = getattr(module, name)
    else:
        attr = module
    globals()[name] = attr
    return attr


__all__ = list(_LAZY_ATTRS.keys())
