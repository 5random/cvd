"""Utility subpackage providing helpers for configuration, logging and
concurrency management.

This package exposes a number of submodules and convenience functions.  In
order to avoid circular import issues these objects are imported lazily via
``__getattr__`` rather than at module import time.
"""

from __future__ import annotations

import importlib

from .config_service import (
    ConfigurationService,
    ConfigurationError,
    ValidationError,
    get_config_service,
    set_config_service,
)

_BASE_PACKAGE = __name__

# ----------------------------------------------------------------------
# Lazy module attributes
# ----------------------------------------------------------------------

_lazy_modules = {
    "concurrency": ".concurrency",
    "data_utils": ".data_utils",
    "ApplicationContainer": ".container",
    "EmailAlertService": ".email_alert_service",
    "set_email_alert_service": ".email_alert_service",
    "info": ".log_service",
    "warning": ".log_service",
    "error": ".log_service",
    "debug": ".log_service",
    "performance": ".log_service",
    "timer": ".log_service",
    "context": ".log_service",
    "notify_later": "..gui.ui_helpers",
}


def __getattr__(name: str):  # pragma: no cover - thin wrapper
    """Dynamically import attributes on first access."""

    module_name = _lazy_modules.get(name)
    if module_name is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

    module = importlib.import_module(module_name, __name__)
    attr = getattr(module, name)
    globals()[name] = attr
    return attr


# ----------------------------------------------------------------------
# subpackages
# ----------------------------------------------------------------------

# ----------------------------------------------------------------------
# individual modules
# ----------------------------------------------------------------------
# ----------------------------------------------------------------------
# public API
# ----------------------------------------------------------------------
__all__ = [
    # subpackages
    "concurrency",
    "data_utils",
    # config_service
    "ConfigurationService",
    "ConfigurationError",
    "ValidationError",
    "get_config_service",
    "set_config_service",
    # container
    "ApplicationContainer",
    # email_alert_service
    "EmailAlertService",
    "set_email_alert_service",
    # log_service
    "info",
    "warning",
    "error",
    "debug",
    "performance",
    "timer",
    "context",
]
# ui helper utilities
__all__.append("notify_later")
