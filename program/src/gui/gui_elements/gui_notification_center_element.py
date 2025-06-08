"""
Notification Center Component for CVD Tracker - FIXED VERSION

This component collects and displays all possible notifications and alerts from various sources:
- Experiments (status changes, events, completion, errors)
- Sensors (readings, errors, status changes) 
- Controllers (status changes, errors, actions)
- System events (configuration changes, validation errors)
- Data processing events
- Audit trail events

Features:
- Real-time notification collection
- Severity-based filtering and styling
- Persistent notification history
- Integration with logging service
- Badge counter for unread notifications
- Clear and mark as read functionality
- Dropdown positioning under notification icon
- Dynamic UI updates for filters and deletions
"""

import time
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Callable

from pathlib import Path

from nicegui import ui
from src.gui.gui_tab_components.gui_tab_base_component import (
    TimedComponent,
    ComponentConfig,
)
from src.utils.log_utils.log_service import get_log_service, LogService
from src.utils.config_utils.config_service import ConfigurationService
from src.experiment_handler.experiment_manager import ExperimentManager, ExperimentState
from src.data_handler.sources.sensor_source_manager import SensorManager  
from src.controllers.controller_manager import ControllerManager
from src.controllers.controller_base import ControllerStatus
from src.utils.alert_system_utils.email_alert_service import get_email_alert_service


from src.gui.notifications import (
    Notification,
    NotificationSeverity,
    NotificationSource,
    NotificationMonitoringMixin,
    NotificationUIMixin,
)


class NotificationCenter(NotificationMonitoringMixin, NotificationUIMixin, TimedComponent):
    """Notification center component for collecting and displaying system notifications"""

    timer_attributes = ["_update_timer"]
    
    def __init__(self, 
                 config_service: ConfigurationService,
                 sensor_manager: Optional[SensorManager] = None,
                 controller_manager: Optional[ControllerManager] = None,
                 experiment_manager: Optional[ExperimentManager] = None):
        """Initialize notification center"""
        
        component_config = ComponentConfig(
            component_id="notification_center",
            title="Notification Center",
            classes="notification-center"
        )
        super().__init__(component_config)
        
        self.config_service = config_service
        self.sensor_manager = sensor_manager
        self.controller_manager = controller_manager
        self.experiment_manager = experiment_manager
        self.log_service = get_log_service()
        
        # Notification storage
        self.notifications: List[Notification] = []
        self.max_notifications: int = 500
        self.notification_history_file: Path = Path("data/notifications/history.json")
        
        # UI elements
        self._notification_list: Optional[Any] = None
        self._badge_counter: Optional[Any] = None
        self._dialog: Optional[Any] = None
        self._menu: Optional[Any] = None
        self._notification_list_container: Optional[Any] = None  # Container for dynamic updates
        self._severity_filter: str = "all"
        self._source_filter: str = "all"

        # Track how long controllers remain in critical state
        self._controller_error_times: Dict[str, float] = {}
        
        # Monitoring state
        self._last_log_check = time.time()
        self._monitoring_active = False
        self._update_timer = None
        
        # Initialize notification directory
        self.notification_history_file.parent.mkdir(parents=True, exist_ok=True)
        
        # Load existing notifications
        self._load_notification_history()
        
        # Setup monitoring
        self._setup_monitoring()
        
    def _load_notification_history(self) -> None:
        """Load notification history from file"""
        try:
            if self.notification_history_file.exists():
                with open(self.notification_history_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    
                # Convert to notification objects (last 100 for performance)
                for item in data.get('notifications', [])[-100:]:
                    notification = Notification(
                        id=item['id'],
                        title=item['title'],
                        message=item['message'],
                        severity=NotificationSeverity(item['severity']),
                        source=NotificationSource(item['source']),
                        timestamp=datetime.fromisoformat(item['timestamp']),
                        read=item.get('read', False),
                        metadata=item.get('metadata', {})
                    )
                    self.notifications.append(notification)
                    
        except Exception as e:
            self.log_service.warning(f"Failed to load notification history: {e}")
    
    def _save_notification_history(self) -> None:
        """Save notification history to file"""
        try:
            data = {
                'last_updated': datetime.now().isoformat(),
                'notifications': []
            }
            
            # Save last 200 notifications
            for notification in self.notifications[-200:]:
                data['notifications'].append({
                    'id': notification.id,
                    'title': notification.title,
                    'message': notification.message,
                    'severity': notification.severity.value,
                    'source': notification.source.value,
                    'timestamp': notification.timestamp.isoformat(),
                    'read': notification.read,
                    'metadata': notification.metadata
                })
            
            with open(self.notification_history_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
                
        except Exception as e:
            self.log_service.error(f"Failed to save notification history: {e}")
    
    def add_notification(self, 
                        title: str, 
                        message: str, 
                        severity: NotificationSeverity = NotificationSeverity.INFO,
                        source: NotificationSource = NotificationSource.SYSTEM,
                        metadata: Optional[Dict[str, Any]] = None,
                        action_label: Optional[str] = None,
                        action_callback: Optional[Callable] = None) -> str:
        """Add a new notification"""
        
        notification_id = f"{source.value}_{int(time.time() * 1000)}"
        
        notification = Notification(
            id=notification_id,
            title=title,
            message=message,
            severity=severity,
            source=source,
            timestamp=datetime.now(),
            metadata=metadata or {},
            action_label=action_label,
            action_callback=action_callback
        )
        
        self.notifications.append(notification)
        
        # Limit notification count
        if len(self.notifications) > self.max_notifications:
            self.notifications = self.notifications[-self.max_notifications:]
        
        # Save to file periodically
        if len(self.notifications) % 10 == 0:
            self._save_notification_history()
        
        # Update UI if visible
        self._update_ui()
        
        # Log the notification
        log_level = 'error' if severity == NotificationSeverity.ERROR else 'warning' if severity == NotificationSeverity.WARNING else 'info'
        getattr(self.log_service, log_level)(f"NOTIFICATION: {title} - {message}")
        
        return notification_id
    
    def delete_notification(self, notification_id: str) -> None:
        """Delete a specific notification"""
        self.notifications = [n for n in self.notifications if n.id != notification_id]
        self._save_notification_history()
        self._update_ui()

    def mark_as_read(self, notification_id: str) -> None:
        """Mark a notification as read"""
        for notification in self.notifications:
            if notification.id == notification_id:
                notification.read = True
                break
        self._update_ui()
    
    def mark_all_as_read(self) -> None:
        """Mark all notifications as read"""
        for notification in self.notifications:
            notification.read = True
        self._update_ui()
    
    def clear_notifications(self) -> None:
        """Clear all notifications"""
        self.notifications.clear()
        self._save_notification_history()
        self._update_ui()
    
    def get_unread_count(self) -> int:
        """Get count of unread notifications"""
        return sum(1 for n in self.notifications if not n.read)
    
    def render(self) -> None:
        """Render the component (not used - button is created on demand)"""
        pass

    def _update_element(self, data: Any) -> None:
        """Handle BaseComponent.update calls by refreshing UI elements"""
        self._update_ui()

    def cleanup(self) -> None:
        """Cleanup component resources"""
        self._monitoring_active = False
        self._save_notification_history()
        super().cleanup()


def create_notification_center(config_service: ConfigurationService,
                             sensor_manager: Optional[SensorManager] = None,
                             controller_manager: Optional[ControllerManager] = None,
                             experiment_manager: Optional[ExperimentManager] = None) -> NotificationCenter:
    """Factory function to create notification center"""
    return NotificationCenter(
        config_service=config_service,
        sensor_manager=sensor_manager,
        controller_manager=controller_manager,
        experiment_manager=experiment_manager
    )

__all__ = ["NotificationCenter", "create_notification_center"]
