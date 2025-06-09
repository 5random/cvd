"""Monitoring helper mixin for the NotificationCenter."""
from datetime import datetime
import time
from typing import Any, Dict, Optional

from nicegui import ui

from src.utils.alert_system_utils.email_alert_service import get_email_alert_service
from src.controllers.controller_base import ControllerStatus
from src.gui.gui_elements.notifications.models import Notification, NotificationSeverity, NotificationSource

# Stub for add_notification to satisfy usage and return type
def add_notification(
    title: str,
    message: str,
    severity: NotificationSeverity,
    source: NotificationSource,
    metadata: Optional[Dict[str, Any]] = None,
    action_label: Optional[Any] = None,
    action_callback: Optional[Any] = None,
) -> str:
    """Stub: Adds a notification and returns its ID"""
    return ""

class NotificationMonitoringMixin:
    """Mixin providing monitoring helpers for NotificationCenter."""

    sensor_manager: Optional[Any]
    controller_manager: Optional[Any]
    experiment_manager: Optional[Any]
    config_service: Any
    log_service: Any
    notifications: list
    _controller_error_times: Dict[str, float]
    _last_log_check: float
    _monitoring_active: bool
    _update_timer: Optional[Any]

    def __init__(self, *args, **kwargs) -> None:
        """Initialize monitoring state defaults"""
        super().__init__(*args, **kwargs)
        # internal state defaults
        self._controller_error_times: Dict[str, float] = {}
        self._last_log_check: float = 0.0
        self._monitoring_active: bool = False
        self._update_timer: Optional[Any] = None

    def _setup_monitoring(self) -> None:
        """Setup monitoring for various notification sources."""
        if self.experiment_manager:
            self.experiment_manager.add_state_change_callback(self._on_experiment_state_change)
            self.experiment_manager.add_data_callback(self._on_experiment_data)

        self._monitoring_active = True
        if not self._update_timer:
            self._update_timer = ui.timer(5.0, self._check_for_new_notifications)

    def _on_experiment_state_change(self, old_state, new_state) -> None:
        severity = NotificationSeverity.INFO
        if new_state.name in {"FAILED", "CANCELLED"}:
            severity = NotificationSeverity.ERROR
        elif new_state.name == "COMPLETED":
            severity = NotificationSeverity.SUCCESS
        elif new_state.name == "PAUSED":
            severity = NotificationSeverity.WARNING

        exp_name = "Unknown"
        try:
            current_exp = getattr(self.experiment_manager, "current_experiment_id", None) or getattr(
                self.experiment_manager, "current_experiment", None
            )
            if current_exp:
                exp_name = current_exp
        except AttributeError:
            pass

        add_notification(
            title="Experiment State Changed",
            message=f"Experiment '{exp_name}' changed from {old_state.value} to {new_state.value}",
            severity=severity,
            source=NotificationSource.EXPERIMENT,
            metadata={
                "experiment_id": exp_name,
                "old_state": old_state.value,
                "new_state": new_state.value,
            },
        )

    def _on_experiment_data(self, data_point) -> None:
        error_count = sum(
            1 for reading in data_point.sensor_readings.values() if hasattr(reading, "status") and reading.status.name != "OK"
        )
        if error_count:
            add_notification(
                title="Experiment Data Issues",
                message=f"Experiment '{data_point.experiment_id}': {error_count} sensor(s) reporting errors",
                severity=NotificationSeverity.WARNING,
                source=NotificationSource.EXPERIMENT,
                metadata={
                    "experiment_id": data_point.experiment_id,
                    "error_count": error_count,
                    "phase": data_point.phase.value if hasattr(data_point.phase, "value") else str(data_point.phase),
                },
            )

    def _check_for_new_notifications(self) -> None:
        self._check_sensor_notifications()
        self._check_controller_notifications()
        self._check_config_notifications()
        self._check_log_notifications()

    def _check_sensor_notifications(self) -> None:
        if not self.sensor_manager:
            return
        readings = self.sensor_manager.get_latest_readings()
        for sensor_id, reading in readings.items():
            if hasattr(reading, "status") and reading.status.name != "OK":
                recent_notifications = [
                    n
                    for n in self.notifications[-20:]
                    if n.source == NotificationSource.SENSOR
                    and n.metadata.get("sensor_id") == sensor_id
                    and (datetime.now() - n.timestamp).seconds < 300
                ]
                if not recent_notifications:
                    add_notification(
                        title=f"Sensor Issue: {sensor_id}",
                        message=f"Sensor {sensor_id} status: {reading.status.name}" + (
                            f" - {reading.error_message}" if hasattr(reading, "error_message") and reading.error_message else ""
                        ),
                        severity=NotificationSeverity.ERROR
                        if reading.status.name == "ERROR"
                        else NotificationSeverity.WARNING,
                        source=NotificationSource.SENSOR,
                        metadata={
                            "sensor_id": sensor_id,
                            "status": reading.status.name,
                            "error_message": getattr(reading, "error_message", None),
                        },
                    )

    def _check_controller_notifications(self) -> None:
        if not self.controller_manager:
            return
        alert_cfg = self.config_service.get("alerting", dict, {}) or {}
        timeout = alert_cfg.get("critical_state_timeout_s", 60)
        now = time.time()
        for cid in self.controller_manager.list_controllers():
            ctrl = self.controller_manager.get_controller(cid)
            if ctrl is None:
                continue
            stats = ctrl.get_stats()
            status = stats.get("status")
            if status == ControllerStatus.ERROR.value:
                start = self._controller_error_times.get(cid, now)
                self._controller_error_times.setdefault(cid, start)
                if now - start >= timeout:
                    add_notification(
                        title=f"Controller {cid} kritisch",
                        message=f"Controller {cid} befindet sich seit {timeout}s im Fehlerzustand",
                        severity=NotificationSeverity.ERROR,
                        source=NotificationSource.CONTROLLER,
                        metadata={"controller_id": cid, "status": status},
                    )
                    service = get_email_alert_service()
                    if service:
                        subject = f"Controller {cid} critical"
                        body = f"Controller {cid} has reported an error for {timeout} seconds."
                        service.send_alert(subject, body)
                    self._controller_error_times[cid] = now
            else:
                self._controller_error_times.pop(cid, None)

    def _check_config_notifications(self) -> None:
        validation_errors = []
        try:
            config = self.config_service.get_configuration()
            if not config.get("sensors"):
                validation_errors.append("Missing sensors configuration")
            if not config.get("controllers"):
                validation_errors.append("Missing controllers configuration")
        except Exception:
            validation_errors.append("Failed to load configuration")

        if validation_errors:
            recent_config_notifications = [
                n
                for n in self.notifications[-10:]
                if n.source == NotificationSource.CONFIG and (datetime.now() - n.timestamp).seconds < 1800
            ]
            if not recent_config_notifications:
                add_notification(
                    title="Configuration Validation Errors",
                    message=f"Found {len(validation_errors)} configuration validation error(s)",
                    severity=NotificationSeverity.WARNING,
                    source=NotificationSource.CONFIG,
                    metadata={"error_count": len(validation_errors), "errors": validation_errors[:5]},
                )

    def _check_log_notifications(self) -> None:
        error_log_path = self.log_service.log_dir / "error.log"
        if error_log_path.exists():
            mod_time = error_log_path.stat().st_mtime
            if mod_time > self._last_log_check:
                with open(error_log_path, "r", encoding="utf-8") as f:
                    lines = f.readlines()
                recent_lines = lines[-10:] if len(lines) > 10 else lines
                for line in recent_lines:
                    if "NOTIFICATION:" in line:
                        continue
                    # any ERROR line qualifies for notification once file updated
                    if "ERROR" in line:
                        parts = line.split(" - ", 2)
                        if len(parts) >= 3:
                            error_msg = parts[2].strip()
                            existing = [
                                n
                                for n in self.notifications[-5:]
                                if n.source == NotificationSource.SYSTEM and error_msg in n.message
                            ]
                            if not existing:
                                add_notification(
                                    title="System Error",
                                    message=error_msg,
                                    severity=NotificationSeverity.ERROR,
                                    source=NotificationSource.SYSTEM,
                                    metadata={"log_source": "error.log"},
                                )
                self._last_log_check = mod_time
