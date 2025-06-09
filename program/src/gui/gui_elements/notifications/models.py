from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, Optional

class NotificationSeverity(Enum):
    """Severity levels for notifications"""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    SUCCESS = "success"

class NotificationSource(Enum):
    """Sources of notifications"""
    EXPERIMENT = "experiment"
    SENSOR = "sensor"
    CONTROLLER = "controller"
    SYSTEM = "system"
    CONFIG = "config"
    DATA_PROCESSING = "data_processing"
    AUDIT = "audit"

@dataclass
class Notification:
    """Individual notification entry"""
    id: str
    title: str
    message: str
    severity: NotificationSeverity
    source: NotificationSource
    timestamp: datetime
    read: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)
    action_label: Optional[str] = None
    action_callback: Optional[Callable] = None
