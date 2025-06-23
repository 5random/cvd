"""Backwards compatibility layer for deprecated module name."""
from typing import Any, Dict, List

from .alert_element import *  # noqa: F401,F403


def create_demo_configurations() -> List[Dict[str, Any]]:
    """Create demo alert configurations for testing."""
    return [
        {
            "name": "Lab Monitoring",
            "emails": ["admin@tuhh.de", "security@tuhh.de", "technician@tuhh.de"],
            "settings": {
                "no_motion_detected": {"enabled": True, "delay_minutes": 10},
                "camera_offline": {"enabled": True},
                "system_error": {"enabled": True},
                "experiment_complete_alert": {"enabled": False},
            },
        },
        {
            "name": "Experiment Notifications",
            "emails": ["researcher@tuhh.de", "supervisor@tuhh.de"],
            "settings": {
                "no_motion_detected": {"enabled": False, "delay_minutes": 5},
                "camera_offline": {"enabled": False},
                "system_error": {"enabled": True},
                "experiment_complete_alert": {"enabled": True},
            },
        },
        {
            "name": "Inactive Configuration",
            "emails": ["test@tuhh.de"],
            "settings": {
                "no_motion_detected": {"enabled": False, "delay_minutes": 5},
                "camera_offline": {"enabled": False},
                "system_error": {"enabled": False},
                "experiment_complete_alert": {"enabled": False},
            },
        },
    ]
