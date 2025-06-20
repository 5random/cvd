# alternative gui application for the program that enables only basic functionality of the program those are:
# - live view of webcam with basic controls (start/stop webcam, adjust ROI, sensitivity settings, fps settings, resolution settings)
# - live status of motion detection algorithm applied to the webcam with ROI and sensitivity settings
# - email alert service for critical events (e.g. when motion is not detected) with alert delay settings (email alert shall include webcam image, motion detection status, timestamp, and other relevant information)
# - basic experiment management (start/stop experiment, view results/status, alert on critical events)

from nicegui import ui, app
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any
from program.src.utils.email_alert_service import get_email_alert_service

from src.utils.config_service import ConfigurationService
from src.data_handler.sources.sensor_source_manager import SensorManager
from src.controllers.controller_manager import create_cvd_controller_manager, ControllerManager
from src.experiment_handler.experiment_manager import ExperimentManager

from alt_gui import (
    setup_global_styles,
    WebcamStreamElement,
    ExperimentManagementSection,
    MotionStatusSection,
    create_compact_alert_widget,
    create_demo_configurations,
    create_email_alert_status_display,
    create_email_alert_wizard,
    EmailAlertStatusDisplay,
)


class SimpleGUIApplication:
    """Simple GUI application skeleton with basic CVD functionality"""

    
    def __init__(self, config_dir: Optional[Path] = None):
        self.camera_active = False
        self.motion_detected = False
        self.experiment_running = False
        self.alerts_enabled = False

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

        # Track if we have active alerts
        self._update_alerts_status()

        # --- Backend services -------------------------------------------------
        if config_dir is None:
            config_dir = Path(__file__).resolve().parents[3] / "config"

        self.config_service = ConfigurationService(
            config_dir / "config.json",
            config_dir / "default_config.json",
        )
        self.sensor_manager = SensorManager(self.config_service)
        self.controller_manager: ControllerManager = create_cvd_controller_manager()
        self.experiment_manager = ExperimentManager(
            config_service=self.config_service,
            sensor_manager=self.sensor_manager,
            controller_manager=self.controller_manager,
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
                    ui.button(icon="fullscreen", on_click=self.toggle_fullscreen).props(
                        "flat round"
                    ).classes("text-white").tooltip("Toggle Fullscreen")

                    ui.button(icon="refresh", on_click=self.reload_page).props(
                        "flat round"
                    ).classes("text-white").tooltip("Reload Page")

                    # Dark/Light mode toggle
                    self.dark_mode = ui.dark_mode()
                    self.dark_mode_btn = (
                        ui.button(icon="dark_mode", on_click=self.toggle_dark_mode)
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
        setup_global_styles(self)

        # Header
        self.create_header()  # Instantiate shared UI sections
        self.webcam_stream = WebcamStreamElement(
            self.settings, self.update_camera_status
        )
        self.motion_section = MotionStatusSection(self.settings)
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

    # Context menu handlers - all placeholder implementations
    def show_camera_settings_context(self):
        """Show camera settings from context menu"""
        ui.notify("Camera Settings (Rechtsklick) noch nicht implementiert", type="info")

    def start_recording_context(self):
        """Start recording from context menu"""
        ui.notify("Start Recording (Rechtsklick) noch nicht implementiert", type="info")

    def take_snapshot_context(self):
        """Take snapshot from context menu"""
        ui.notify("Take Snapshot (Rechtsklick) noch nicht implementiert", type="info")

    def adjust_roi_context(self):
        """Adjust ROI from context menu"""
        ui.notify("Adjust ROI (Rechtsklick) noch nicht implementiert", type="info")

    def reset_view_context(self):
        """Reset view from context menu"""
        ui.notify("Reset View (Rechtsklick) noch nicht implementiert", type="info")

    # Main event handlers - placeholder implementations
    def toggle_camera(self):
        """Toggle camera on/off"""
        ui.notify("toggle_camera noch nicht implementiert", type="info")

    def update_sensitivity(self, e):
        """Update motion detection sensitivity"""
        ui.notify("update_sensitivity noch nicht implementiert", type="info")

    def update_fps(self, e):
        """Update camera FPS setting"""
        ui.notify("update_fps noch nicht implementiert", type="info")

    def update_resolution(self, e):
        """Update camera resolution setting"""
        ui.notify("update_resolution noch nicht implementiert", type="info")

    def set_roi(self):
        """Set region of interest"""
        ui.notify("set_roi noch nicht implementiert", type="info")

    def apply_camera_settings(self):
        """Apply all camera settings"""
        ui.notify("apply_camera_settings noch nicht implementiert", type="info")

    def toggle_alerts(self, e):
        """Toggle email alerts on/off - opens alert management"""
        self.show_alert_management()

    def send_test_alert(self):
        """Send a test email alert"""
        self._send_test_to_all_configs()

    def show_alert_history(self):
        """Show alert history dialog"""
        self._show_alert_history()

    def toggle_experiment(self):
        """Toggle experiment running state"""
        ui.notify("toggle_experiment noch nicht implementiert", type="info")

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

        if hasattr(self, 'alert_status_icon'):
            cls = 'text-yellow-300' if self.alerts_enabled else 'text-gray-400'
            self.alert_status_icon.classes(cls)
    
    def show_alert_setup_wizard(self):
        """Show the email alert setup wizard in a dialog"""
        def _on_save(config: Dict[str, Any]):
            self.alert_configurations.append(config)
            self.alert_display.alert_configurations = self.alert_configurations
            self._update_alerts_status()
            service = get_email_alert_service()
            if service and config.get('emails'):
                service.recipient = config['emails'][0]

        with ui.dialog() as dialog, ui.card().classes('w-full max-w-4xl'):
            wizard_card = create_email_alert_wizard(on_save=_on_save)
            with ui.row().classes('w-full justify-end mt-4'):
                ui.button('Schließen', on_click=dialog.close).props('flat')

        dialog.open()

    def show_alert_management(self):
        """Show the alert management interface in a dialog"""
        with ui.dialog() as dialog, ui.card().classes("w-full max-w-6xl"):
            ui.label("E-Mail Alert Verwaltung").classes("text-xl font-bold mb-4")

            # Create the full alert overview
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
                        status_color = "positive"
                    else:
                        ui.icon("warning").classes("text-orange-600 text-2xl")
                        status_text = "Inaktiv"
                        status_color = "warning"

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
            if any(settings.get('enabled', False) for settings in config.get('settings', {}).values())
        ]

        if not active_configs:
            ui.notify("Keine aktiven Alert-Konfigurationen vorhanden", type="warning")
            return

        service = get_email_alert_service()
        if service is None:
            ui.notify('EmailAlertService nicht verfügbar', type='warning')
            return

        total_sent = 0
        for cfg in active_configs:
            subject = f"Test-Alert ({cfg.get('name', 'Alert')})"
            body = 'Dies ist ein Test des E-Mail-Alert-Systems.'
            for email in cfg.get('emails', []):
                if service.send_alert(subject, body, recipient=email):
                    total_sent += 1

        ui.notify(
            f'Test-Alerts an {total_sent} Empfänger in {len(active_configs)} Konfigurationen gesendet',
            type='positive' if total_sent else 'warning'
        )
    
    def _show_alert_history(self):
        """Show alert history dialog"""
        with ui.dialog() as dialog, ui.card().classes('w-full max-w-4xl'):
            ui.label('Alert-Verlauf').classes('text-xl font-bold mb-4')

            service = get_email_alert_service()
            history_entries = service.get_history() if service else []

            with ui.column().classes('gap-3'):
                ui.label('Letzte gesendete Alerts:').classes('font-medium')

                for entry in history_entries:
                    with ui.card().classes('w-full p-3'):
                        with ui.row().classes('items-center justify-between'):
                            with ui.row().classes('items-center gap-3'):
                                ui.icon('schedule').classes('text-gray-600')
                                ui.label(entry['time']).classes('font-mono')
                                ui.label(entry.get('subject', 'Alert')).classes('font-medium')
                                ui.label(entry['recipient']).classes('text-gray-600')

                            ui.icon('email').classes('text-blue-600')

            with ui.row().classes('w-full justify-end mt-4'):
                ui.button('Schließen', on_click=dialog.close).props('flat')
        
        dialog.open()

    def run(self, host: str = "localhost", port: int = 8081):
        """Run the simple GUI application"""

        @ui.page("/")
        def index():
            self.create_main_layout()

        @app.on_startup
        async def _startup() -> None:
            await self.sensor_manager.start_all_configured_sensors()
            await self.controller_manager.start_all_controllers()

        @app.on_shutdown
        async def _shutdown() -> None:
            await self.controller_manager.stop_all_controllers()
            await self.sensor_manager.shutdown()
        
        print(f'Starting Simple CVD GUI on http://{host}:{port}')

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
    app = SimpleGUIApplication()
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
# ------
# Run the application with: python alt_application.py
# The email alert section will show in the bottom-right grid area.
# Click "Konfigurieren" to set up new alerts or "Verwalten" to view existing ones.
