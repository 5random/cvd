# Alternative GUI application for the program that enables only basic
# functionality of the program:
# - live view of webcam with basic controls (start/stop webcam, adjust ROI,
#   sensitivity settings, fps settings, resolution settings)
# - live status of motion detection algorithm applied to the webcam with ROI and
#   sensitivity settings
# - email alert service for critical events (e.g. when motion is not detected)
#   with alert delay settings (email alert includes webcam image, motion
#   detection status, timestamp, and other relevant information)
# - basic experiment management (start/stop experiment, view results/status,
#   alert on critical events)

from pathlib import Path

from nicegui import ui, app
from datetime import datetime
from typing import Optional, Dict, Any
import asyncio
import cv2
from fastapi.responses import StreamingResponse
from fastapi import Request

from program.src.controllers.controller_base import ControllerConfig
from program.src.controllers.controller_utils.controller_data_sources.camera_capture_controller import (
    CameraCaptureController,
)
from program.src.controllers.controller_utils.camera_utils import apply_uvc_settings
from program.src.controllers.controller_manager import (
    ControllerManager,
    create_cvd_controller_manager,
)
from program.src.controllers.algorithms.motion_detection import (
    MotionDetectionController,
)
from program.src.experiment_handler.experiment_manager import (
    ExperimentManager,
    ExperimentConfig,
)
from program.src.utils.concurrency.async_utils import install_signal_handlers
from program.src.utils.config_service import ConfigurationService
from program.src.utils.email_alert_service import get_email_alert_service
from program.src.data_handler.sources.sensor_source_manager import SensorManager

from .alt_gui import (
    setup_global_styles,
    WebcamStreamElement,
    ExperimentManagementSection,
    MotionStatusSection,
    create_demo_configurations,
    create_email_alert_wizard,
    EmailAlertStatusDisplay,
)


class SimpleGUIApplication:
    """Simple GUI application skeleton with basic CVD functionality"""

    def __init__(
        self,
        controller_manager: Optional[ControllerManager] = None,
        config_dir: Optional[Path] = None,
    ):
        self.camera_active = False
        self.motion_detected = False
        self.experiment_running = False
        self.alerts_enabled = False
        self.controller_manager = (
            controller_manager
            if controller_manager is not None
            else create_cvd_controller_manager()
        )

        self.camera_controller: Optional[CameraCaptureController] = None

        # Determine configuration directory and initialise core services
        if config_dir is None:
            config_dir = Path(__file__).resolve().parents[3] / "config"

        self.config_service = ConfigurationService(
            config_dir / "config.json",
            config_dir / "default_config.json",
        )
        self.sensor_manager = SensorManager(self.config_service)
        # use the already created controller manager for the experiment manager
        self.experiment_manager = ExperimentManager(
            config_service=self.config_service,
            sensor_manager=self.sensor_manager,
            controller_manager=self.controller_manager,
            auto_install_signal_handlers=False,
        )

        # Additional runtime attributes
        # Global dark mode controller from NiceGUI
        self.dark_mode = ui.dark_mode()
        self._current_experiment_id: Optional[str] = None
        self._experiment_start: Optional[datetime] = None
        self._experiment_duration: Optional[int] = None
        self._experiment_timer: Optional[ui.timer] = None

        # Placeholder settings
        self.settings = {
            "sensitivity": 50,
            "fps": 30,
            "resolution": "640x480 (30fps)",
            "roi_enabled": False,
            "email": "",
            "alert_delay": 5,
        }

        # Initialize email alert configurations with demo data
        self.alert_configurations = create_demo_configurations()
        self.alert_display = EmailAlertStatusDisplay(self.alert_configurations)
        self.alert_display.update_callback = self._on_alert_config_changed

        # Track if we have active alerts
        self._update_alerts_status()

        from typing import cast

        # Retrieve and cast controllers to their concrete types
        self.camera_controller = cast(
            Optional[CameraCaptureController],
            self.controller_manager._controllers.get("camera_capture"),
        )

        self.motion_controller = cast(
            Optional[MotionDetectionController],
            self.controller_manager._controllers.get("motion_detection"),
        )

    def create_header(self):
        """Create application header with status indicators"""
        with ui.header().classes("cvd-header text-white"):
            with ui.row().classes("w-full items-center justify-between px-4"):
                ui.label("CVD Tracker - Simple Monitor").classes("text-h4 flex-grow")

                # Status indicators
                with ui.row().classes("gap-4 items-center"):
                    # Camera status
                    self.camera_status_icon = (
                        ui.icon("videocam")
                        .classes(
                            "text-green-300" if self.camera_active else "text-gray-400"
                        )
                        .tooltip("Camera Status")
                    )

                    # Motion detection status
                    self.motion_status_icon = (
                        ui.icon("motion_photos_on")
                        .classes(
                            "text-orange-300"
                            if self.motion_detected
                            else "text-gray-400"
                        )
                        .tooltip("Motion Detection Status")
                    )

                    # Alert status
                    self.alert_status_icon = (
                        ui.icon("notifications")
                        .classes(
                            "text-yellow-300"
                            if self.alerts_enabled
                            else "text-gray-400"
                        )
                        .tooltip("Email Alerts Status")
                    )
                    # Experiment status
                    self.experiment_status_icon = (
                        ui.icon("science")
                        .classes(
                            "text-green-300"
                            if self.experiment_running
                            else "text-gray-400"
                        )
                        .tooltip("Experiment Status")
                    )

                    # Separator
                    ui.separator().props("vertical inset").classes(
                        "bg-white opacity-30 mx-2"
                    )

                    # Control buttons
                    ui.button(
                        icon="fullscreen",
                        on_click=self.toggle_fullscreen,
                    ).props("flat round").classes("text-white").tooltip(
                        "Toggle Fullscreen"
                    )

                    ui.button(
                        icon="refresh",
                        on_click=self.reload_page,
                    ).props("flat round").classes("text-white").tooltip("Reload Page")

                    # Dark/Light mode toggle
                    self.dark_mode_btn = (
                        ui.button(
                            icon="light_mode" if self.dark_mode.value else "dark_mode",
                            on_click=self.toggle_dark_mode,
                        )
                        .props("flat round")
                        .classes("text-white")
                        .tooltip("Toggle Dark/Light Mode")
                    )

                    # Separator
                    ui.separator().props("vertical inset").classes(
                        "bg-white opacity-30 mx-2"
                    )

                    # Current time
                    self.time_label = ui.label("")
                    # schedule update_time every second
                    ui.timer(1.0, lambda: self.update_time())

    def create_main_layout(self):
        """Create the main application layout"""
        ui.page_title("CVD Tracker - Simple Monitor")

        # Setup global styles using shared theme
        setup_global_styles()

        # Header
        self.create_header()  # Instantiate shared UI sections
        self.webcam_stream = WebcamStreamElement(
            self.settings,
            callbacks={
                "update_sensitivity": self.update_sensitivity,
                "update_fps": self.update_fps,
                "update_resolution": self.update_resolution,
                "set_roi": self.set_roi,
                "apply_uvc_settings": self.apply_uvc_settings,
                "take_snapshot": self.take_snapshot_context,
                "adjust_roi": self.adjust_roi_context,
                "show_camera_settings": self.show_camera_settings_context,
                "reset_view": self.reset_view_context,
                "camera_toggle": self.toggle_camera,
            },
            on_camera_status_change=self.update_camera_status,
        )
        self.motion_section = MotionStatusSection(
            self.settings, controller_manager=self.controller_manager
        )
        self.experiment_section = ExperimentManagementSection(self.settings)
        # Note: EmailAlertsSection replaced with new alert system

        # Main content area - Masonry-style layout with CSS Grid
        with ui.element("div").classes("w-full p-4 masonry-grid"):
            # Camera section (top-left, spans full height if needed)
            with ui.element("div").style("grid-area: camera;"):
                self.webcam_stream.create_camera_section()

            # Motion Detection Status (top-right)
            with ui.element("div").style("grid-area: motion;"):
                self.motion_section.create_motion_status_section()

            # Experiment Management (bottom-left)
            with ui.element("div").style("grid-area: experiment;"):
                self.experiment_section.create_experiment_section()
                self.experiment_section.start_experiment_btn.on(
                    "click", self.toggle_experiment
                )
                self.experiment_section.stop_experiment_btn.on(
                    "click", self.toggle_experiment
                )

            # Email Alerts (bottom-right) - New Alert System
            with ui.element("div").style("grid-area: alerts;"):
                self._create_enhanced_alerts_section()
            # Event handlers - placeholder implementations

    def update_time(self):
        """Update the time display in header"""
        self.time_label.text = datetime.now().strftime("%H:%M:%S")

    def update_camera_status(self, active: bool):
        """Update camera icon color based on active state."""
        self.camera_active = active
        if not hasattr(self, "camera_status_icon"):
            return
        if active:
            self.camera_status_icon.classes(
                add="text-green-300", remove="text-gray-400"
            )
        else:
            self.camera_status_icon.classes(
                add="text-gray-400", remove="text-green-300"
            )

    # Header button handlers
    def toggle_fullscreen(self):
        """Toggle fullscreen mode"""
        ui.run_javascript(
            "document.fullscreenElement ? document.exitFullscreen() : document.documentElement.requestFullscreen()"
        )

    def reload_page(self):
        """Reload the current page"""
        ui.navigate.reload()

    def toggle_dark_mode(self):
        """Toggle between dark and light mode"""
        self.dark_mode.value = not self.dark_mode.value
        icon = "light_mode" if self.dark_mode.value else "dark_mode"
        self.dark_mode_btn.set_icon(icon)

    # Context menu handlers
    def show_camera_settings_context(self):
        """Show camera settings from context menu"""
        if self.webcam_stream:
            self.webcam_stream.show_camera_settings()

    def start_recording_context(self):
        """Start or stop recording from context menu"""
        if self.webcam_stream:
            self.webcam_stream.toggle_recording()

    def take_snapshot_context(self):
        """Take snapshot from context menu"""
        if self.webcam_stream:
            self.webcam_stream.take_snapshot()

    def adjust_roi_context(self):
        """Adjust ROI from context menu"""
        if self.webcam_stream:
            self.webcam_stream.adjust_roi()

    def reset_view_context(self):
        """Reset view from context menu"""
        if self.webcam_stream:
            self.webcam_stream.reset_view()

    def take_snapshot(self):
        """Trigger snapshot on the webcam element."""
        if self.webcam_stream:
            self.webcam_stream.take_snapshot()

    def adjust_roi(self):
        """Open ROI adjustment dialog on the webcam element."""
        if self.webcam_stream:
            self.webcam_stream.adjust_roi()

    # Main event handlers - placeholder implementations
    def toggle_camera(self):
        """Start or stop the camera capture controller."""

        async def _start():
            if self.camera_controller is None:
                cfg = ControllerConfig(
                    controller_id="camera_capture",
                    controller_type="camera_capture",
                    parameters={"device_index": 0},
                )
                self.camera_controller = CameraCaptureController("camera_capture", cfg)
            await self.camera_controller.start()

        async def _stop():
            if self.camera_controller is not None:
                await self.camera_controller.stop()
                await self.camera_controller.cleanup()
                self.camera_controller = None

        if not self.camera_active:
            asyncio.create_task(_start())
            self.camera_active = True
            if hasattr(self, "camera_status_icon"):
                self.camera_status_icon.classes(replace="text-green-300")
            if getattr(self.webcam_stream, "start_camera_btn", None):
                self.webcam_stream.start_camera_btn.set_icon("pause")
                self.webcam_stream.start_camera_btn.set_text("Pause Video")
        else:
            asyncio.create_task(_stop())
            self.camera_active = False
            if hasattr(self, "camera_status_icon"):
                self.camera_status_icon.classes(replace="text-gray-400")
            if getattr(self.webcam_stream, "start_camera_btn", None):
                self.webcam_stream.start_camera_btn.set_icon("play_arrow")
                self.webcam_stream.start_camera_btn.set_text("Play Video")

    def update_sensitivity(self, e):
        """Update motion detection sensitivity"""
        value = int(getattr(e, "value", e))
        self.settings["sensitivity"] = value
        if self.motion_controller:
            self.motion_controller.motion_threshold_percentage = value / 100.0
        self.webcam_stream.sensitivity_number.value = value
        self.webcam_stream.sensitivity_slider.value = value
        ui.notify(f"Sensitivity set to {value}%", type="positive")

    def update_fps(self, e):
        """Update camera FPS setting"""
        value = int(getattr(e, "value", e))
        self.settings["fps"] = value
        if self.camera_controller:
            self.camera_controller.fps = value
        if self.motion_controller:
            self.motion_controller.fps = value
        self.webcam_stream.fps_select.value = value
        ui.notify(f"FPS set to {value}", type="positive")

    def update_resolution(self, e):
        """Update camera resolution setting"""
        res = getattr(e, "value", e)
        self.settings["resolution"] = res
        try:
            dims = res.split()[0]
            width, height = map(int, dims.split("x"))
        except Exception:
            width = height = None
        if width and height:
            if self.camera_controller:
                self.camera_controller.width = width
                self.camera_controller.height = height
            if self.motion_controller:
                self.motion_controller.width = width
                self.motion_controller.height = height
        self.webcam_stream.resolution_select.value = res
        ui.notify(f"Resolution set to {res}", type="positive")

    def set_roi(self):
        """Set region of interest"""
        enabled = self.webcam_stream.roi_checkbox.value
        self.settings["roi_enabled"] = enabled
        if self.motion_controller:
            if not enabled:
                self.motion_controller.roi_x = 0
                self.motion_controller.roi_y = 0
                self.motion_controller.roi_width = None
                self.motion_controller.roi_height = None
            else:
                width = self.motion_controller.width or 640
                height = self.motion_controller.height or 480
                self.motion_controller.roi_x = width // 4
                self.motion_controller.roi_y = height // 4
                self.motion_controller.roi_width = width // 2
                self.motion_controller.roi_height = height // 2
        ui.notify("ROI updated", type="positive")

    def apply_uvc_settings(self):
        """Apply UVC camera settings"""
        settings = {
            "brightness": self.webcam_stream.brightness_number.value,
            "contrast": self.webcam_stream.contrast_number.value,
            "saturation": self.webcam_stream.saturation_number.value,
            "hue": self.webcam_stream.hue_number.value,
            "sharpness": self.webcam_stream.sharpness_number.value,
            "gain": self.webcam_stream.gain_number.value,
            "gamma": self.webcam_stream.gamma_number.value,
            "backlight_compensation": self.webcam_stream.backlight_comp_number.value,
            "white_balance_auto": self.webcam_stream.wb_auto_checkbox.value,
            "white_balance": self.webcam_stream.wb_manual_number.value,
            "exposure_auto": self.webcam_stream.exposure_auto_checkbox.value,
            "exposure": self.webcam_stream.exposure_manual_number.value,
        }
        self.settings.update(settings)
        # Apply UVC settings asynchronously if capture objects are available
        if (
            self.camera_controller is not None
            and self.camera_controller._capture is not None
        ):
            capture = self.camera_controller._capture
            asyncio.create_task(apply_uvc_settings(capture, settings))
        if (
            self.motion_controller is not None
            and self.motion_controller._capture is not None
        ):
            capture = self.motion_controller._capture
            asyncio.create_task(apply_uvc_settings(capture, settings))
        if self.camera_controller:
            self.camera_controller.uvc_settings.update(settings)
        if self.motion_controller:
            self.motion_controller.uvc_settings.update(settings)
        ui.notify("UVC settings applied", type="positive")

    def toggle_alerts(self, value):
        """Enable or disable alerts based on checkbox value."""
        value = getattr(value, "value", value)
        self.alerts_enabled = bool(value)
        self._update_alerts_status()

    def send_test_alert(self):
        """Send a test email alert"""
        self._send_test_to_all_configs()

    def show_alert_history(self):
        """Show alert history dialog"""
        self._show_alert_history()

    def toggle_experiment(self):
        """Toggle experiment running state"""

        import asyncio

        async def _toggle() -> None:
            if not self.experiment_running:
                name = self.experiment_section.experiment_name_input.value
                duration = self.experiment_section.experiment_duration_input.value
                self._experiment_duration = int(duration) if duration else None

                config = ExperimentConfig(
                    name=name,
                    duration_minutes=self._experiment_duration,
                )
                exp_id = self.experiment_manager.create_experiment(config)
                success = await self.experiment_manager.start_experiment(exp_id)
                if not success:
                    ui.notify("Failed to start experiment", type="negative")
                    return

                self._current_experiment_id = exp_id
                self.experiment_running = True
                self._experiment_start = datetime.now()
                self.experiment_section.start_experiment_btn.disable()
                self.experiment_section.stop_experiment_btn.enable()
                self.experiment_section.experiment_icon.classes("text-green-600")
                self.experiment_section.experiment_status_label.text = (
                    "Experiment running"
                )
                self.experiment_section.experiment_name_label.text = f"Name: {name}"
                dur_text = (
                    f"Duration: {self._experiment_duration} min"
                    if self._experiment_duration
                    else "Duration: unlimited"
                )
                self.experiment_section.experiment_duration_label.text = dur_text
                self.experiment_section.experiment_elapsed_label.text = "Elapsed: 0s"
                self.experiment_section.experiment_progress.value = 0.0
                self.experiment_section.experiment_details.set_visibility(True)
                if self._experiment_timer:
                    self._experiment_timer.cancel()
                self._experiment_timer = ui.timer(1.0, self._update_experiment_status)
                ui.notify(f'Started experiment "{name}"', type="positive")
            else:
                success = await self.experiment_manager.stop_experiment()
                if not success:
                    ui.notify("Failed to stop experiment", type="negative")
                    return

                self.experiment_running = False
                self._current_experiment_id = None
                self.experiment_section.start_experiment_btn.enable()
                self.experiment_section.stop_experiment_btn.disable()
                self.experiment_section.experiment_icon.classes("text-gray-500")
                self.experiment_section.experiment_status_label.text = (
                    "No experiment running"
                )
                self.experiment_section.experiment_details.set_visibility(False)
                if self._experiment_timer:
                    self._experiment_timer.cancel()
                    self._experiment_timer = None
                ui.notify("Experiment stopped", type="info")

        asyncio.create_task(_toggle())

    def _update_experiment_status(self) -> None:
        """Update elapsed time and progress display while running"""
        if not self.experiment_running or not self._experiment_start:
            return

        elapsed = (datetime.now() - self._experiment_start).total_seconds()
        self.experiment_section.experiment_elapsed_label.text = (
            f"Elapsed: {int(elapsed)}s"
        )

        if self._experiment_duration:
            total = self._experiment_duration * 60
            progress = min(elapsed / total, 1.0)
            self.experiment_section.experiment_progress.value = progress

    def _update_alerts_status(self):
        """Update the alerts_enabled status based on current configurations"""
        # Check if any alert configuration has active alert types
        self.alerts_enabled = any(
            any(
                settings.get("enabled", False)
                for settings in config.get("settings", {}).values()
            )
            for config in self.alert_configurations
        )

        if hasattr(self, "alert_status_icon"):
            cls = "text-yellow-300" if self.alerts_enabled else "text-gray-400"
            self.alert_status_icon.classes(cls)

    def _on_alert_config_changed(self) -> None:
        """Handle alert configuration updates from the status display."""
        if hasattr(self, "alert_overview_container"):
            self.alert_overview_container.clear()
            with self.alert_overview_container:
                self.alert_display.create_alert_overview()
        self._update_alerts_status()

    def show_alert_setup_wizard(self):
        """Show the email alert setup wizard in a dialog"""

        def _on_save(config: Dict[str, Any]):
            self.alert_configurations.append(config)
            self.alert_display.alert_configurations = self.alert_configurations
            self._update_alerts_status()
            service = get_email_alert_service()
            if service and config.get("emails"):
                service.recipient = config["emails"][0]

        with ui.dialog() as dialog, ui.card().classes("w-full max-w-4xl"):
            create_email_alert_wizard(on_save=_on_save)
            with ui.row().classes("w-full justify-end mt-4"):
                ui.button("Schließen", on_click=dialog.close).props("flat")

        dialog.open()

    def show_alert_management(self):
        """Show the alert management interface in a dialog"""
        with ui.dialog() as dialog, ui.card().classes("w-full max-w-6xl"):
            ui.label("E-Mail Alert Verwaltung").classes("text-xl font-bold mb-4")

            with ui.column() as self.alert_overview_container:
                self.alert_display.create_alert_overview()

            with ui.row().classes("w-full justify-end mt-4"):
                ui.button("Schließen", on_click=dialog.close).props("flat")
        dialog.open()

    def _create_enhanced_alerts_section(self):
        """Create the enhanced email alerts section using the new alert system"""
        with ui.card().classes("w-full h-full"):
            with ui.card_section():
                # Header with action buttons
                with ui.row().classes("w-full items-center justify-between mb-4"):
                    ui.label("E-Mail Alerts").classes("text-lg font-semibold")

                    with ui.row().classes("gap-2"):
                        ui.button(
                            "Konfigurieren",
                            icon="settings",
                            on_click=self.show_alert_setup_wizard,
                        ).props("size=sm color=primary")

                        ui.button(
                            "Verwalten",
                            icon="list",
                            on_click=self.show_alert_management,
                        ).props("size=sm color=secondary")

                        ui.button(
                            "Alert-Verlauf",
                            icon="history",
                            on_click=self.show_alert_history,
                        ).props("size=sm color=secondary")

                        ui.button(
                            "Test-Alert",
                            icon="send",
                            on_click=self.send_test_alert,
                        ).props("size=sm color=warning")

                # Status overview
                total_configs = len(self.alert_configurations)
                active_configs = sum(
                    1
                    for config in self.alert_configurations
                    if sum(
                        1
                        for settings in config.get("settings", {}).values()
                        if settings.get("enabled", False)
                    )
                    > 0
                )

                # Quick status display
                with ui.row().classes("items-center gap-3 mb-4"):
                    # Status icon
                    if active_configs > 0:
                        ui.icon("check_circle").classes("text-green-600 text-2xl")
                        status_text = "Aktiv"
                    else:
                        ui.icon("warning").classes("text-orange-600 text-2xl")
                        status_text = "Inaktiv"

                    with ui.column().classes("gap-1"):
                        ui.label(f"Status: {status_text}").classes("font-medium")
                        ui.label(
                            f"{active_configs} von {total_configs} Konfigurationen aktiv"
                        ).classes(
                            "text-sm text-gray-600"
                        )  # Quick summary of active configurations
                if active_configs > 0:
                    ui.separator().classes("my-3")
                    ui.label("Aktive Konfigurationen:").classes(
                        "text-sm font-medium mb-2"
                    )

                    for config in self.alert_configurations:
                        active_alerts = sum(
                            1
                            for settings in config.get("settings", {}).values()
                            if settings.get("enabled", False)
                        )
                        if active_alerts > 0:
                            with ui.row().classes(
                                "items-center justify-between w-full mb-2 p-2 bg-gray-50 rounded"
                            ):
                                # Left side: Icon and name
                                with ui.row().classes("items-center gap-2"):
                                    ui.icon("label").classes("text-blue-600")
                                    ui.label(config.get("name", "Unbenannt")).classes(
                                        "text-sm font-medium"
                                    )

                                # Right side: Alerts and recipients in same line
                                with ui.row().classes("items-center gap-2"):
                                    ui.chip(
                                        f"{active_alerts} Alert(s)", color="positive"
                                    ).props("dense")

                                    # Show recipient count
                                    email_count = len(config.get("emails", []))
                                    if email_count > 0:
                                        ui.chip(
                                            f"{email_count} Empfänger", color="blue"
                                        ).props("dense")

    def _send_test_to_all_configs(self):
        """Send test alerts to all active configurations"""
        active_configs = [
            config
            for config in self.alert_configurations
            if sum(
                1
                for settings in config.get("settings", {}).values()
                if settings.get("enabled", False)
            )
            > 0
        ]

        if not active_configs:
            ui.notify("Keine aktiven Alert-Konfigurationen vorhanden", type="warning")
            return

        service = get_email_alert_service()
        if service is None:
            ui.notify("EmailAlertService nicht verfügbar", type="warning")
            return

        total_sent = 0
        for cfg in active_configs:
            subject = f"Test-Alert ({cfg.get('name', 'Alert')})"
            body = "Dies ist ein Test des E-Mail-Alert-Systems."
            for email in cfg.get("emails", []):
                if service.send_alert(subject, body, recipient=email):
                    total_sent += 1

        ui.notify(
            f"Test-Alerts an {total_sent} Empfänger in {len(active_configs)} Konfigurationen gesendet",
            type="positive" if total_sent else "warning",
        )

    def _show_alert_history(self):
        """Show alert history dialog"""
        with ui.dialog() as dialog, ui.card().classes("w-full max-w-4xl"):
            ui.label("Alert-Verlauf").classes("text-xl font-bold mb-4")

            service = get_email_alert_service()
            history_entries = service.get_history() if service else []

            with ui.column().classes("gap-3"):
                ui.label("Letzte gesendete Alerts:").classes("font-medium")

                for entry in history_entries:
                    with ui.card().classes("w-full p-3"):
                        with ui.row().classes("items-center justify-between"):
                            with ui.row().classes("items-center gap-3"):
                                ui.icon("schedule").classes("text-gray-600")
                                ui.label(entry["time"]).classes("font-mono")
                                ui.label(entry.get("subject", "Alert")).classes(
                                    "font-medium"
                                )
                                ui.label(entry["recipient"]).classes("text-gray-600")

                            ui.icon("email").classes("text-blue-600")

            with ui.row().classes("w-full justify-end mt-4"):
                ui.button("Schließen", on_click=dialog.close).props("flat")

        dialog.open()

    def run(self, host: str = "localhost", port: int = 8081):
        """Run the simple GUI application"""

        @ui.page("/")
        def index():
            self.create_main_layout()

        @ui.page("/video_feed")
        async def video_feed(request: Request):
            async def gen():
                while True:
                    try:
                        if await request.is_disconnected():
                            break
                    except asyncio.CancelledError:
                        break

                    frame = None
                    if self.camera_controller is not None:
                        output = self.camera_controller.get_output()
                        if isinstance(output, dict):
                            frame = output.get("frame") or output.get("image")
                        elif output is not None:
                            frame = output

                    if frame is not None:
                        success, buf = cv2.imencode(".jpg", frame)
                        if success:
                            jpeg = buf.tobytes()
                            yield (
                                b"--frame\r\nContent-Type: image/jpeg\r\n\r\n"
                                + jpeg
                                + b"\r\n"
                            )
                    await asyncio.sleep(0.03)

            return StreamingResponse(
                gen(), media_type="multipart/x-mixed-replace; boundary=frame"
            )

        @app.on_startup
        async def _startup() -> None:
            install_signal_handlers(self.experiment_manager._task_manager)
            await self.sensor_manager.start_all_configured_sensors()
            await self.controller_manager.start_all_controllers()
            # Ensure camera status reflects that controllers started
            self.camera_active = True
            self.update_camera_status(True)

        @app.on_shutdown
        async def _shutdown() -> None:
            await self.controller_manager.stop_all_controllers()
            await self.sensor_manager.shutdown()

        print(f"Starting Simple CVD GUI on http://{host}:{port}")

        ui.run(
            host=host,
            port=port,
            title="CVD Tracker - Simple",
            favicon="https://www.tuhh.de/favicon.ico",
            dark=False,
            show=True,
        )


# Entry point
def main():
    """Main entry point for the simple GUI application"""
    controller_manager = create_cvd_controller_manager()
    app = SimpleGUIApplication(controller_manager)

    # Startup logic is defined in ``SimpleGUIApplication.run``.
    app.run()


if __name__ in {"__main__", "__mp_main__"}:
    main()

# Integration Notes:
# =================
# The enhanced email alert system has been successfully integrated:
#
# 1. New Imports:
#    - EmailAlertStatusDisplay and factory functions from alert_element_new.py
#    - Demo configurations for testing
#
# 2. Enhanced Features:
#    - Compact alert status widget in the main dashboard
#    - Full alert management interface accessible via dialogs
#    - Integration with existing header status indicators
#    - Test alert functionality for all active configurations
#    - Alert history viewing (with mock data for demonstration)
#
# 3. User Interface:
#    - "Konfigurieren" button opens the 4-step setup wizard
#    - "Verwalten" button opens the full alert overview
#    - Quick status display shows active configurations
#    - Header alert icon reflects the current alert status
#
# 4. Demo Data:
#    - 3 sample configurations are loaded by default
#    - Includes active and inactive configurations for testing
#    - Email addresses are partially anonymized in the display
#
# Usage:
#   python src/gui/alt_application.py
# or
#   python -m src.gui.alt_application
# The email alert section will show in the bottom-right grid area.
# Click "Konfigurieren" to set up new alerts or "Verwalten" to view existing ones.
