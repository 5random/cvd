"""Provide alternate GUI components and theme setup."""

from .theme import setup_global_styles
from .alt_gui_elements import (
    WebcamStreamElement,
    EmailAlertsSection,
    ExperimentManagementSection,
    MotionStatusSection,
    create_compact_alert_widget,
    create_demo_configurations,
    create_email_alert_status_display,
    create_email_alert_wizard,
    EmailAlertStatusDisplay,
)

__all__ = [
    "setup_global_styles",
    "WebcamStreamElement",
    "EmailAlertsSection",
    "ExperimentManagementSection",
    "MotionStatusSection",
    "create_compact_alert_widget",
    "create_demo_configurations",
    "create_email_alert_status_display",
    "create_email_alert_wizard",
    "EmailAlertStatusDisplay",
]
