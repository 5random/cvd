from . import concurrency, data_utils
from .container import ApplicationContainer
from .email_alert_service import EmailAlertService, set_email_alert_service
from .log_service import info, warning, error, debug, performance, timer, context

"""
Utility subpackage providing helpers for configuration, logging and
concurrency management.

This package collects:
    - config_service, container, email_alert_service, log_service, ui_helpers
    - the two subpackages: concurrency, data_utils
"""

# ----------------------------------------------------------------------
# subpackages
# ----------------------------------------------------------------------

# ----------------------------------------------------------------------
# individual modules
# ----------------------------------------------------------------------
from .config_service import (
        ConfigurationService,
        ConfigurationError,
        ValidationError,
        get_config_service,
        set_config_service,
)
from .ui_helpers import *  # pylint: disable=wildcard-import

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
# add whatever ui_helpers exposes
__all__ += ui_helpers.__all__  # assumes ui_helpers.py defines its own __all__

