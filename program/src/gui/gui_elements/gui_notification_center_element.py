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
import asyncio
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

from nicegui import ui
from src.gui.gui_tab_components.gui_tab_base_component import (
    TimedComponent,
    BaseComponent,
    ComponentConfig,
)
from src.utils.log_utils.log_service import get_log_service, LogService
from src.utils.config_utils.config_service import ConfigurationService
from src.experiment_handler.experiment_manager import ExperimentManager, ExperimentState
from src.data_handler.sources.sensor_source_manager import SensorManager  
from src.controllers.controller_manager import ControllerManager
from src.controllers.controller_base import ControllerStatus
from src.utils.alert_system_utils.email_alert_service import get_email_alert_service

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


class NotificationCenter(TimedComponent):
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
    
    def _setup_monitoring(self) -> None:
        """Setup monitoring for various notification sources"""
        
        # Monitor experiment events
        if self.experiment_manager:
            self.experiment_manager.add_state_change_callback(self._on_experiment_state_change)
            self.experiment_manager.add_data_callback(self._on_experiment_data)
        
        # Start background monitoring
        self._monitoring_active = True
        if not self._update_timer:
            self._update_timer = ui.timer(5.0, self._check_for_new_notifications)

    def _on_experiment_state_change(self, old_state: ExperimentState, new_state: ExperimentState) -> None:
        """Handle experiment state changes"""
        try:
            severity = NotificationSeverity.INFO
            if new_state in [ExperimentState.FAILED, ExperimentState.CANCELLED]:
                severity = NotificationSeverity.ERROR
            elif new_state == ExperimentState.COMPLETED:
                severity = NotificationSeverity.SUCCESS
            elif new_state == ExperimentState.PAUSED:
                severity = NotificationSeverity.WARNING
                
            # Try to get current experiment name, fallback to "Unknown"
            exp_name = "Unknown"
            try:
                current_exp = getattr(self.experiment_manager, 'current_experiment_id', None) or \
                             getattr(self.experiment_manager, 'current_experiment', None)
                if current_exp:
                    exp_name = current_exp
            except AttributeError:
                pass
            
            self.add_notification(
                title=f"Experiment State Changed",
                message=f"Experiment '{exp_name}' changed from {old_state.value} to {new_state.value}",
                severity=severity,
                source=NotificationSource.EXPERIMENT,
                metadata={
                    'experiment_id': exp_name,
                    'old_state': old_state.value,
                    'new_state': new_state.value
                }
            )
        except Exception as e:
            self.log_service.error(f"Error handling experiment state change: {e}")
    
    def _on_experiment_data(self, data_point) -> None:
        """Handle experiment data collection events"""
        try:
            # Only notify on errors or milestones
            error_count = sum(1 for reading in data_point.sensor_readings.values() 
                            if hasattr(reading, 'status') and reading.status.name != 'OK')
            
            if error_count > 0:
                self.add_notification(
                    title="Experiment Data Issues",
                    message=f"Experiment '{data_point.experiment_id}': {error_count} sensor(s) reporting errors",
                    severity=NotificationSeverity.WARNING,
                    source=NotificationSource.EXPERIMENT,
                    metadata={
                        'experiment_id': data_point.experiment_id,
                        'error_count': error_count,
                        'phase': data_point.phase.value if hasattr(data_point.phase, 'value') else str(data_point.phase)
                    }
                )
        except Exception as e:
            self.log_service.error(f"Error handling experiment data event: {e}")
    
    def _check_for_new_notifications(self) -> None:
        """Check for new notifications from various sources"""
        try:
            # Check sensors for errors or status changes
            self._check_sensor_notifications()
            
            # Check controllers for status changes
            self._check_controller_notifications()
            
            # Check configuration validation
            self._check_config_notifications()
            
            # Check log files for recent errors/warnings
            self._check_log_notifications()
            
        except Exception as e:
            self.log_service.error(f"Error checking for notifications: {e}")
    
    def _check_sensor_notifications(self) -> None:
        """Check sensor manager for notification-worthy events"""
        if not self.sensor_manager:
            return
            
        try:
            # Get current sensor readings
            readings = self.sensor_manager.get_latest_readings()
            
            for sensor_id, reading in readings.items():
                # Check for sensor errors
                if hasattr(reading, 'status') and reading.status.name != 'OK':
                    # Check if we already have a recent notification for this sensor
                    recent_notifications = [n for n in self.notifications[-20:] 
                                          if n.source == NotificationSource.SENSOR 
                                          and n.metadata.get('sensor_id') == sensor_id
                                          and (datetime.now() - n.timestamp).seconds < 300]  # 5 minutes
                    
                    if not recent_notifications:
                        self.add_notification(
                            title=f"Sensor Issue: {sensor_id}",
                            message=f"Sensor {sensor_id} status: {reading.status.name}" + 
                                   (f" - {reading.error_message}" if hasattr(reading, 'error_message') and reading.error_message else ""),
                            severity=NotificationSeverity.ERROR if reading.status.name == 'ERROR' else NotificationSeverity.WARNING,
                            source=NotificationSource.SENSOR,
                            metadata={
                                'sensor_id': sensor_id,
                                'status': reading.status.name,
                                'error_message': getattr(reading, 'error_message', None)
                            }
                        )
        except Exception as e:
            self.log_service.error(f"Error checking sensor notifications: {e}")
    
    def _check_controller_notifications(self) -> None:
        """Check controller manager for notification-worthy events"""
        if not self.controller_manager:
            return
            
        try:
            alert_cfg = self.config_service.get('alerting', dict, {}) or {}
            timeout = alert_cfg.get('critical_state_timeout_s', 60)
            now = time.time()
            for cid in self.controller_manager.list_controllers():
                ctrl = self.controller_manager.get_controller(cid)
                if ctrl is None:
                    continue
                stats = ctrl.get_stats()
                status = stats.get('status')
                if status == ControllerStatus.ERROR.value:
                    start = self._controller_error_times.get(cid, now)
                    self._controller_error_times.setdefault(cid, start)
                    if now - start >= timeout:
                        self.add_notification(
                            title=f"Controller {cid} kritisch",
                            message=f"Controller {cid} befindet sich seit {timeout}s im Fehlerzustand",
                            severity=NotificationSeverity.ERROR,
                            source=NotificationSource.CONTROLLER,
                            metadata={'controller_id': cid, 'status': status}
                        )
                        service = get_email_alert_service()
                        if service:
                            subject = f"Controller {cid} critical"
                            body = f"Controller {cid} has reported an error for {timeout} seconds."
                            service.send_alert(subject, body)
                        self._controller_error_times[cid] = now
                else:
                    self._controller_error_times.pop(cid, None)
        except Exception as e:
            self.log_service.error(f"Error checking controller notifications: {e}")

    def _check_config_notifications(self) -> None:
        """Check for configuration validation errors"""
        try:
            # Check if config validation produces errors
            validation_errors = []
            
            # Basic config validation 
            try:
                config = self.config_service.get_configuration()
                if not config.get('sensors'):
                    validation_errors.append("Missing sensors configuration")
                if not config.get('controllers'):
                    validation_errors.append("Missing controllers configuration")
            except Exception:
                validation_errors.append("Failed to load configuration")
            
            if validation_errors:
                # Only notify if we haven't already notified about config errors recently
                recent_config_notifications = [n for n in self.notifications[-10:] 
                                             if n.source == NotificationSource.CONFIG 
                                             and (datetime.now() - n.timestamp).seconds < 1800]  # 30 minutes
                
                if not recent_config_notifications:
                    self.add_notification(
                        title="Configuration Validation Errors",
                        message=f"Found {len(validation_errors)} configuration validation error(s)",
                        severity=NotificationSeverity.WARNING,
                        source=NotificationSource.CONFIG,
                        metadata={
                            'error_count': len(validation_errors),
                            'errors': validation_errors[:5]  # First 5 errors
                        }
                    )
        except Exception as e:
            # Config validation might not be implemented yet
            pass
    
    def _check_log_notifications(self) -> None:
        """Check log files for recent errors and warnings"""
        try:
            # Check error log for recent entries
            # Use the configured log directory from the log service
            error_log_path = self.log_service.log_dir / "error.log"
            if error_log_path.exists():
                # Get modification time
                mod_time = error_log_path.stat().st_mtime
                
                # Only check if file was modified since last check
                if mod_time > self._last_log_check:
                    with open(error_log_path, 'r', encoding='utf-8') as f:
                        lines = f.readlines()
                        
                    # Check last few lines for recent errors
                    recent_lines = lines[-10:] if len(lines) > 10 else lines
                    
                    for line in recent_lines:
                        # Skip errors generated from our own notifications
                        if 'NOTIFICATION:' in line:
                            continue
                        if 'ERROR' in line and datetime.now().strftime('%Y-%m-%d') in line:
                            # Extract error message
                            parts = line.split(' - ', 2)
                            if len(parts) >= 3:
                                error_msg = parts[2].strip()
                                
                                # Check if we already have this error
                                existing = [n for n in self.notifications[-5:] 
                                          if n.source == NotificationSource.SYSTEM 
                                          and error_msg in n.message]
                                
                                if not existing:
                                    self.add_notification(
                                        title="System Error",
                                        message=error_msg,
                                        severity=NotificationSeverity.ERROR,
                                        source=NotificationSource.SYSTEM,
                                        metadata={'log_source': 'error.log'}
                                    )
                    
                    self._last_log_check = mod_time
                    
        except Exception as e:
            # Log file checking is best effort
            pass
    
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
    
    def create_notification_button(self) -> ui.button:
        """Create the notification center button for the header"""
        with ui.row().classes('relative'):
            button = ui.button(
                icon='notifications',
                color='5898d4'
            ).props('flat round').classes('relative')
            
            # Badge counter for unread notifications
            unread_count = self.get_unread_count()
            self._badge_counter = ui.badge(
                str(unread_count) if unread_count > 0 else '',
                color='red'
            ).props('floating').classes('absolute -top-2 -right-2')
            
            if unread_count == 0:
                self._badge_counter.set_visibility(False)
            
            # Create dropdown menu attached to the button
            with button:
                self._create_notification_menu()
        
        return button
    
    def _create_notification_menu(self) -> None:
        """Create notification dropdown menu"""
        with ui.menu().props('max-width=400px') as menu:
            self._menu = menu
            with ui.card().classes('w-96 max-h-[70vh]'):  # Smaller width and limited height
                # Header with simplified controls
                with ui.card_section().classes('bg-blue-600 text-white'):
                    with ui.row().classes('w-full items-center justify-between'):
                        ui.label('Benachrichtigungen').classes('text-h6')
                        ui.button(icon='close', color='5898d4', on_click=menu.close).props('flat round dense')
                
                # Compact filter bar
                with ui.card_section().classes('py-2'):
                    with ui.row().classes('items-center gap-2'):
                        with ui.select(
                            ['all', 'info', 'warning', 'error', 'success'],
                            value=self._severity_filter,
                            label='Priorität',
                            on_change=self._on_severity_filter_change
                        ).props('dense options-dense').classes('text-xs w-28'):
                            pass
                        
                        with ui.select(
                            ['all', 'experiment', 'sensor', 'controller', 'system', 'config'],
                            value=self._source_filter,
                            label='Quelle',
                            on_change=self._on_source_filter_change
                        ).props('dense options-dense').classes('text-xs w-28'):
                            pass
                
                # Notification list with scrolling
                with ui.card_section().classes('overflow-auto max-h-[50vh]') as list_container:
                    self._notification_list_container = list_container
                    self._create_notification_list()
                
                # Footer with actions
                with ui.card_section().classes('py-2 bg-gray-100'):
                    with ui.row().classes('justify-between'):
                        ui.button('Alle gelesen', 
                                on_click=self.mark_all_as_read,
                                icon='mark_email_read').props('outline flat dense')
                        ui.button('Alle löschen', 
                                on_click=self._confirm_clear_all,
                                icon='clear_all').props('outline flat dense color=negative')
    
    def show_notification_dialog(self) -> None:
        """Show the notification center menu as a dropdown"""
        if self._menu:
            self._menu.open()
        # Legacy method - menu is now created directly with button
    
    def _create_notification_list(self) -> None:
        """Create the notification list UI"""
        # Filter notifications
        filtered_notifications = self._get_filtered_notifications()
        
        if not filtered_notifications:
            with ui.column().classes('w-full items-center justify-center p-4'):
                ui.icon('notifications_none', size='2rem').classes('text-gray-400')
                ui.label('Keine Benachrichtigungen').classes('text-sm text-gray-500')
            return
            
        # Group by date, more compact for small popup
        today = datetime.now().date()
        yesterday = today - timedelta(days=1)
        
        grouped_notifications = {
            'Heute': [],
            'Gestern': [],
            'Älter': []
        }
        
        for notification in filtered_notifications:
            notif_date = notification.timestamp.date()
            if notif_date == today:
                grouped_notifications['Heute'].append(notification)
            elif notif_date == yesterday:
                grouped_notifications['Gestern'].append(notification)
            else:
                grouped_notifications['Älter'].append(notification)
        
        # Display grouped notifications with smaller headers
        for group_name, group_notifications in grouped_notifications.items():
            if not group_notifications:
                continue
                
            ui.label(group_name).classes('text-xs font-bold mt-2 mb-1 text-gray-500')
            for notification in group_notifications:
                self._create_notification_item(notification)
    
    def _create_notification_item(self, notification: Notification) -> None:
        """Create a single notification item"""
        # Determine styling based on severity and read status
        card_classes = 'w-full mb-1 cursor-pointer hover:shadow-md transition-shadow rounded-sm'
        if not notification.read:
            card_classes += ' border-l-4'
            if notification.severity == NotificationSeverity.ERROR:
                card_classes += ' border-red-500 bg-red-50'
            elif notification.severity == NotificationSeverity.WARNING:
                card_classes += ' border-orange-500 bg-orange-50'
            elif notification.severity == NotificationSeverity.SUCCESS:
                card_classes += ' border-green-500 bg-green-50'
            else:
                card_classes += ' border-blue-500 bg-blue-50'
        
        with ui.card().classes(card_classes):
            with ui.card_section().classes('p-2'):  # Reduced padding for compact display
                # Compact header with icon and title
                with ui.row().classes('items-center gap-1 mb-1'):
                    # Severity icon (smaller)
                    icon_map = {
                        NotificationSeverity.ERROR: ('error', 'text-red-500'),
                        NotificationSeverity.WARNING: ('warning', 'text-orange-500'),
                        NotificationSeverity.SUCCESS: ('check_circle', 'text-green-500'),
                        NotificationSeverity.INFO: ('info', 'text-blue-500')
                    }
                    icon, icon_class = icon_map.get(notification.severity, ('info', 'text-gray-500'))
                    ui.icon(icon, size='xs').classes(icon_class)
                    
                    # Title with click handler to mark as read
                    title_classes = 'text-sm flex-1'
                    if not notification.read:
                        title_classes += ' font-bold'
                    ui.label(notification.title).classes(title_classes).on('click', lambda e, notif_id=notification.id: self.mark_as_read(notif_id))
                    
                    # Delete button (small X)
                    ui.button(icon='close', on_click=lambda e, notif_id=notification.id: self.delete_notification(notif_id)).props('flat dense size=xs').classes('text-gray-400 hover:text-red-500')
                    
                    # Unread indicator (dot)
                    if not notification.read:
                        ui.icon('circle', size='xs').classes('text-blue-500')
                
                # Message with limited height
                message_classes = 'text-xs text-gray-600'
                if not notification.read:
                    message_classes = 'text-xs text-gray-800'
                
                # Truncate long messages and add ellipsis
                message = notification.message
                if len(message) > 100:
                    message = message[:97] + '...'
                
                ui.label(message).classes(message_classes)
                
                # Footer with source and time
                with ui.row().classes('items-center justify-between mt-1'):
                    # Source as small text
                    source_display = notification.source.value.replace('_', ' ').capitalize()
                    ui.label(source_display).classes('text-xs text-gray-500')
                    
                    # Timestamp
                    time_str = notification.timestamp.strftime('%H:%M')
                    ui.label(time_str).classes('text-xs text-gray-400')
                
                # Action button if available (more compact)
                if notification.action_label and notification.action_callback:
                    ui.button(
                        notification.action_label,
                        on_click=notification.action_callback
                    ).props('dense flat size="xs"').classes('mt-1 text-xs')
    
    def _get_filtered_notifications(self) -> List[Notification]:
        """Get notifications filtered by current filters"""
        filtered = self.notifications
        
        # Filter by severity
        if self._severity_filter != 'all':
            filtered = [n for n in filtered if n.severity.value == self._severity_filter]
        
        # Filter by source
        if self._source_filter != 'all':
            filtered = [n for n in filtered if n.source.value == self._source_filter]
        
        # Sort by timestamp (newest first)
        return sorted(filtered, key=lambda n: n.timestamp, reverse=True)
    
    def _on_severity_filter_change(self, event) -> None:
        """Handle severity filter change"""
        self._severity_filter = event.value
        self._update_notification_list()
    
    def _on_source_filter_change(self, event) -> None:
        """Handle source filter change"""
        self._source_filter = event.value
        self._update_notification_list()
    
    def _update_notification_list(self) -> None:
        """Update the notification list display"""
        if self._notification_list_container:
            # Clear existing content and recreate
            self._notification_list_container.clear()
            with self._notification_list_container:
                self._create_notification_list()
    
    def _confirm_clear_all(self) -> None:
        """Show confirmation dialog for clearing all notifications"""
        with ui.dialog() as confirm_dialog:
            with ui.card().classes('w-72'):  # Smaller confirmation dialog
                ui.label('Alle Benachrichtigungen löschen?').classes('text-base mb-2')
                ui.label('Diese Aktion kann nicht rückgängig gemacht werden.').classes('text-xs text-gray-600 mb-2')
                with ui.row().classes('gap-2 justify-end'):
                    ui.button('Abbrechen', on_click=confirm_dialog.close).props('flat dense')
                    ui.button('Löschen', 
                             on_click=lambda: (self.clear_notifications(), confirm_dialog.close()),
                             color='negative').props('dense')
        confirm_dialog.open()
    
    def _update_ui(self) -> None:
        """Update UI elements (badge counter, notification list)"""
        # Update badge counter
        if self._badge_counter:
            unread_count = self.get_unread_count()
            self._badge_counter.set_text(str(unread_count) if unread_count > 0 else '')
            self._badge_counter.set_visibility(unread_count > 0)
        
        # Update notification list if menu is open
        self._update_notification_list()
    
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
