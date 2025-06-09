"""
Main web application class for managing the NiceGUI interface.
"""

import asyncio
import contextlib
import json
from typing import Optional

from nicegui import app, ui
import cv2
from src.controllers.controller_manager import create_cvd_controller_manager
from src.data_handler.sources.sensor_source_manager import SensorManager
from src.gui.gui_elements.gui_live_plot_element import LivePlotComponent, PlotConfig
from src.gui.gui_elements.gui_notification_center_element import (
    create_notification_center,
)
from src.gui.gui_tab_components.gui_tab_base_component import (
    ComponentRegistry,
    get_component_registry,
)
from src.gui.gui_tab_components.gui_tab_controllers_component import (
    ControllersComponent,
)
from src.gui.gui_tab_components.gui_tab_dashboard_component import DashboardComponent
from src.gui.gui_tab_components.gui_tab_data_component import (
    create_data_component,
    DataComponent,
)
from src.gui.gui_tab_components.gui_tab_experiment_component import (
    create_experiment_component,
    ExperimentComponent,
)
from src.gui.gui_tab_components.gui_tab_log_component import LogComponent
from src.gui.gui_tab_components.gui_tab_sensors_component import (
    SensorsComponent,
)
from src.gui.gui_tab_components.gui_setup_wizard_component import SetupWizardComponent
from src.utils.config_utils.config_service import (
    ConfigurationService,
    ConfigurationError,
)
from src.utils.data_utils.data_manager import get_data_manager
from src.utils.log_utils.log_service import debug, error, info, warning
from src.gui.gui_elements.gui_webcam_stream_element import CameraStreamComponent
from starlette.staticfiles import StaticFiles
from fastapi.responses import StreamingResponse
from fastapi import Request, HTTPException


class WebApplication:
    """Main web application managing NiceGUI interface and routing"""

    def __init__(
        self, config_service: ConfigurationService, sensor_manager: SensorManager
    ):
        self.config_service = config_service
        self.sensor_manager = sensor_manager
        # Initialize controller manager for dashboard and other components
        self.controller_manager = create_cvd_controller_manager()
        self.component_registry = get_component_registry()
        self._routes_registered = False

        # Initialize attributes that will be assigned later
        self._processing_task: Optional[asyncio.Task] = None
        self._title_label: Optional[ui.label] = None
        self._title_input: Optional[ui.input] = None
        self._refresh_rate_input: Optional[ui.number] = None
        self._sensors_component: Optional[SensorsComponent] = None
        self._controllers_component: Optional[ControllersComponent] = None
        self._log_component: Optional[LogComponent] = None
        self._experiment_component: Optional[ExperimentComponent] = None
        self._data_component: Optional[DataComponent] = None
        self._dashboard_component: Optional[DashboardComponent] = None
        self._live_plot: Optional[LivePlotComponent] = None

        # Initialize notification center with error handling
        try:
            self._notification_center = create_notification_center(
                config_service=self.config_service,
                sensor_manager=self.sensor_manager,
                controller_manager=self.controller_manager,
                experiment_manager=None,
            )
            # Register notification center for proper cleanup
            self.component_registry.register(self._notification_center)
        except Exception as e:
            error(f"Error initializing notification center: {e}")
            self._notification_center = None

    async def startup(self) -> None:
        """Async startup for web application"""
        info("Web application starting up...")
        # Apply persisted dark mode setting before starting controllers
        ui.dark_mode().value = self.config_service.get("ui.dark_mode", bool, True)
        await self.controller_manager.start_all_controllers()
        self._processing_task = asyncio.create_task(self._processing_loop())
        info("Web application startup complete")

    async def shutdown(self) -> None:
        """Async shutdown for web application"""
        info("Web application shutting down...")
        # Cancel processing task if running
        if self._processing_task:
            # self._processing_task is an asyncio.Task
            self._processing_task.cancel()
            with contextlib.suppress(Exception):
                await self._processing_task
        await self.controller_manager.stop_all_controllers()
        if self._dashboard_component:
            self.component_registry.unregister(self._dashboard_component.component_id)
            self._dashboard_component = None
        if self._live_plot:
            self.component_registry.unregister(self._live_plot.component_id)
            self._live_plot = None
        self.component_registry.cleanup_all()
        info("Web application shutdown complete")

    async def _processing_loop(self) -> None:
        while True:
            interval_ms = self.config_service.get(
                "controller_manager.processing_interval_ms", int, 30
            )
            interval = max(0.001, interval_ms / 1000.0)
            await self.sensor_manager.wait_for_new_data(timeout=interval)
            sensor_data = self.sensor_manager.get_latest_readings()
            await self.controller_manager.process_data(sensor_data)

    def register_components(self) -> None:
        """Register all UI components and routes with NiceGUI"""
        if self._routes_registered:
            warning("Routes already registered, skipping...")
            return

        self._setup_routes()
        self._setup_layout()
        self._routes_registered = True
        info("UI components and routes registered")

    def _setup_routes(self) -> None:
        """Setup web routes"""

        @ui.page("/")
        def index():
            """Main dashboard page"""
            return self._create_main_layout()

        @ui.page("/sensors")
        def sensors():
            """Sensor management page"""
            return self._create_sensor_page()

        @ui.page("/config")
        def config():
            """Configuration page"""
            return self._create_config_page()

        @ui.page("/setup")
        def setup():
            """Initial setup wizard"""
            return self._create_setup_wizard_page()

        @ui.page("/status")
        def status():
            """System status page"""
            return self._create_status_page()

        async def _video_feed(request: Request, cid: Optional[str] = None):
            """Stream MJPEG frames from the specified dashboard camera"""
            camera = None
            if cid:
                camera = self.component_registry.get_component(
                    f"dashboard_camera_stream_{cid}"
                )
                if camera is None:
                    camera = self.component_registry.get_component(cid)

            if camera is None:
                camera = self.component_registry.get_component("dashboard_camera_stream")

            if camera is None:
                for comp in self.component_registry.get_all_components():
                    comp_id = getattr(comp, "component_id", "")
                    if str(comp_id).startswith("dashboard_camera_stream_"):
                        camera = comp
                        break

            if camera is None:
                raise HTTPException(status_code=503, detail="Camera stream unavailable")

            async def gen():
                while True:
                    try:
                        if await request.is_disconnected():
                            info("Client disconnected from video feed")
                            break
                    except asyncio.CancelledError:
                        info("Video feed cancelled")
                        break
                    if isinstance(camera, CameraStreamComponent):
                        frame = camera.get_latest_frame()
                        if frame is not None:
                            success, buf = cv2.imencode("jpg", frame)
                            if success:
                                jpeg_bytes = buf.tobytes()
                                yield (
                                    b"--frame\r\nContent-Type: image/jpeg\r\n\r\n"
                                    + jpeg_bytes
                                    + b"\r\n"
                                )
                    await asyncio.sleep(
                        camera.update_interval
                        if isinstance(camera, CameraStreamComponent)
                        else 0.03
                    )

            return StreamingResponse(
                gen(), media_type="multipart/x-mixed-replace; boundary=frame"
            )

        @ui.page("/video_feed")
        async def video_feed(request: Request):
            return await _video_feed(request=request, cid=None)

        @ui.page("/video_feed/{cid}")
        async def video_feed_param(request: Request, cid: str):
            return await _video_feed(request=request, cid=cid)

    def _setup_layout(self) -> None:
        """Setup common layout elements"""
        # Add global CSS and JavaScript if needed
        ui.add_head_html(
            """
            <style>
                .cvd-header { background: linear-gradient(90deg, #1976d2, #1565c0); }
                .cvd-card { border-radius: 8px; box-shadow: 0 2px 8px rgba(0,0,0,0.1); }
                .cvd-sensor-value { font-size: 1.5rem; font-weight: bold; }
            </style>
        """
        )
        # Serve download files directory via StaticFiles for generated packages

        dm = get_data_manager()
        if dm and dm.downloads_dir.exists():
            try:
                app.mount(
                    "/downloads",
                    StaticFiles(directory=str(dm.downloads_dir)),
                    name="downloads",
                )
                debug(f"Mounted downloads directory at /downloads: {dm.downloads_dir}")
            except Exception as e:
                error(f"Error mounting downloads directory {dm.downloads_dir}: {e}")

    def _create_main_layout(self) -> None:
        """Create main dashboard layout"""
        # Header
        with ui.header().classes("cvd-header text-white"):
            with ui.row().classes("w-full items-center"):
                self._title_label = ui.label(
                    self.config_service.get("ui.title", str, "CVD Tracker Dashboard")
                ).classes("text-h4 flex-grow")
                self._create_quick_settings()

        # Main content with tabs
        with ui.tabs().classes("w-full") as tabs:
            ui.tab("dashboard", label="Dashboard", icon="space_dashboard")
            ui.tab("sensors", label="Sensoren", icon="sensors")
            ui.tab("controllers", label="Controller", icon="speed")
            ui.tab("experiments", label="Experimente", icon="science")
            ui.tab("data", label="Daten", icon="folder")
            ui.tab("logs", label="Logs", icon="feed")
            ui.tab("settings", label="Einstellungen", icon="settings")
        # Tab panels
        with ui.tab_panels(tabs).classes("w-full h-full"):
            # Dashboard tab
            with ui.tab_panel("dashboard").classes("p-4"):
                self._create_dashboard_content()

            # Sensors tab
            with ui.tab_panel("sensors").classes("p-4"):
                self._sensors_component = SensorsComponent(
                    self.sensor_manager, self.config_service
                )
                self.component_registry.register(self._sensors_component)
                self._sensors_component.render()

            # Controllers tab
            with ui.tab_panel("controllers").classes("p-4"):
                self._controllers_component = ControllersComponent(
                    self.config_service, self.controller_manager
                )
                self.component_registry.register(self._controllers_component)
                self._controllers_component.render()

            # Experiments tab
            with ui.tab_panel("experiments").classes("p-4"):
                ui.label("Experiment Management").classes("text-xl mb-4")
                self._experiment_component = create_experiment_component(
                    component_id="experiment_component",
                    config_service=self.config_service,
                    sensor_manager=self.sensor_manager,
                    controller_manager=self.controller_manager,
                )
                self.component_registry.register(self._experiment_component)
                self._experiment_component.render()

            # Data tab
            with ui.tab_panel("data").classes("p-4"):
                ui.label("Data Management").classes("text-xl mb-4")
                self._data_component = create_data_component(
                    component_id="data_component"
                )
                self.component_registry.register(self._data_component)
                self._data_component.render()

            # Logs tab
            with ui.tab_panel("logs").classes("p-4"):
                self._log_component = LogComponent()
                self.component_registry.register(self._log_component)
                self._log_component.render()

            # Settings tab
            with ui.tab_panel("settings").classes("p-4"):
                self._create_settings_content()

    def _create_dashboard_content(self) -> None:
        """Create dashboard tab content"""
        with ui.row().classes("w-full h-full gap-4"):
            # Left column - sensor dashboard

            dashboard_sensors = [
                sid
                for sid, cfg in self.config_service.get_sensor_configs()
                if cfg.get("show_on_dashboard")
            ]


            with ui.column().classes('w-1/2'):

                self._dashboard_component = DashboardComponent(
                    self.config_service,
                    self.sensor_manager,
                    self.controller_manager,
                    self._notification_center,
                )
                self.component_registry.register(self._dashboard_component)
                self._dashboard_component.render()
            # use dashboard's configured sensors for live plot

            dashboard_sensors = getattr(self._dashboard_component, '_dashboard_sensors', [])


            # Right column - live plot
            if dashboard_sensors:
                with ui.column().classes("w-1/2"):

                    plot_config = PlotConfig(max_points=2000, refresh_rate_ms=1000, history_seconds=3600)
                    self._live_plot = LivePlotComponent(self.sensor_manager, plot_config, dashboard_sensors)

                    self.component_registry.register(self._live_plot)
                    self._live_plot.render()

    def _create_sensors_content(self) -> None:
        """Create sensors tab content"""
        ui.label("Sensor Management").classes("text-xl mb-4")

        # Sensor status table
        with ui.card().classes("w-full p-4"):
            ui.label("Sensor Status").classes("text-lg font-semibold mb-2")

            # Get sensor status
            sensor_status = self.sensor_manager.get_sensor_status()

            if sensor_status:
                columns = [
                    {"name": "sensor_id", "label": "Sensor ID", "field": "sensor_id"},
                    {"name": "type", "label": "Type", "field": "sensor_type"},
                    {"name": "connected", "label": "Connected", "field": "connected"},
                    {"name": "polling", "label": "Polling", "field": "polling"},
                    {"name": "status", "label": "Status", "field": "status"},
                    {
                        "name": "last_reading",
                        "label": "Last Reading",
                        "field": "last_reading",
                    },
                ]

                rows = []
                for sensor_id, status in sensor_status.items():
                    rows.append(
                        {
                            "sensor_id": sensor_id,
                            "sensor_type": status.get("sensor_type", "unknown"),
                            "connected": "✓" if status.get("connected", False) else "✗",
                            "polling": "✓" if status.get("polling", False) else "✗",
                            "status": status.get("status", "unknown"),
                            "last_reading": status.get("last_reading", "Never"),
                        }
                    )

                ui.table(columns=columns, rows=rows).classes("w-full")
            else:
                ui.label("No sensors configured").classes("text-gray-500")

    def _create_settings_content(self) -> None:
        """Create settings tab content"""
        ui.label("System Settings").classes("text-xl mb-4")

        with ui.row().classes("w-full gap-4"):
            # Configuration section
            with ui.card().classes("w-1/2 p-4"):
                ui.label("Configuration").classes("text-lg font-semibold mb-2")

                # Basic settings
                self._title_input = ui.input(
                    label="System Title",
                    value=self.config_service.get("ui.title", str, "CVD Tracker"),
                )
                self._title_input.classes("w-full mb-2")

                self._refresh_rate_input = ui.number(
                    label="Refresh Rate (ms)",
                    value=self.config_service.get("ui.refresh_rate_ms", int, 1000),
                    min=100,
                    max=10000,
                )
                self._refresh_rate_input.classes("w-full mb-2")

                with ui.row().classes("gap-2 mt-4"):
                    ui.button(
                        "Save Settings", on_click=self._save_settings
                    ).props("color=primary")
                    ui.button(
                        "Reset Config", on_click=self._open_reset_config_dialog
                    ).props("outline")

            # System status section
            with ui.card().classes("w-1/2 p-4"):
                ui.label("System Status").classes("text-lg font-semibold mb-2")

                # This is a simplified status display
                ui.label("✓ Configuration Service: Running").classes("text-green-600")
                ui.label("✓ Sensor Manager: Running").classes("text-green-600")
                ui.label("✓ Web Application: Running").classes("text-green-600")

    def _save_settings(self) -> None:
        """Persist settings from input fields to configuration"""
        try:
            if hasattr(self, "_title_input") and self._title_input is not None:
                self.config_service.set("ui.title", str(self._title_input.value))
                if hasattr(self, "_title_label") and self._title_label is not None:
                    self._title_label.text = str(self._title_input.value)

            if (
                hasattr(self, "_refresh_rate_input")
                and self._refresh_rate_input is not None
            ):
                self.config_service.set(
                    "ui.refresh_rate_ms", int(self._refresh_rate_input.value)
                )

            ui.notify("Settings saved successfully!", type="positive")
        except Exception as e:
            error(f"Error saving settings: {e}")
            ui.notify(f"Error saving settings: {e}", type="negative")

    def _create_quick_settings(self) -> None:
        """Create quick settings in header"""
        with ui.row().classes("gap-2"):
            # Dark mode toggle using NiceGUI's global dark mode object
            dark_mode = ui.dark_mode()

            def toggle_dark_mode() -> None:
                """Toggle UI dark mode and persist setting"""
                dark_mode.value = not dark_mode.value
                self.config_service.set("ui.dark_mode", dark_mode.value)

            ui.button(
                icon="dark_mode", color="#5898d4", on_click=toggle_dark_mode
            ).props("flat round")

            # Refresh button
            ui.button(
                icon="refresh", color="#5898d4", on_click=ui.navigate.reload
            ).props("flat round")

            # Full screen button
            ui.button(
                icon="fullscreen",
                color="#5898d4",
                on_click=lambda: ui.notify("Fullscreen mode"),
            ).props("flat round")

            # Notification center button
            # Only create notification button if attribute exists and not None
            if (
                hasattr(self, "_notification_center")
                and self._notification_center is not None
            ):
                self._notification_center.create_notification_button()
            else:
                debug(
                    "Notification center not initialized; skipping notification button"
                )

    def _save_configuration(self, config_json: str) -> None:
        """Save configuration from JSON text"""
        try:
            config_data = json.loads(config_json)
        except json.JSONDecodeError as e:
            ui.notify(f"Invalid configuration JSON: {e}", type="negative")
            return
        try:
            with open(self.config_service.config_path, "w", encoding="utf-8") as f:
                json.dump(config_data, f, indent=2, ensure_ascii=False)
            self.config_service.reload()
        except (OSError, ConfigurationError) as e:
            ui.notify(f"Error saving configuration: {e}", type="negative")
        else:
            ui.notify("Configuration saved successfully", type="positive")

    def _reset_configuration(self, config_textarea=None) -> None:
        """Reset configuration to defaults"""
        try:
            self.config_service.reset_to_defaults()
            if config_textarea is not None:
                config_textarea.value = self.config_service.get_raw_config_as_json()
            # Update settings inputs if available
            if hasattr(self, "_title_input") and self._title_input is not None:
                self._title_input.value = self.config_service.get("ui.title", str, "CVD Tracker")
            if hasattr(self, "_refresh_rate_input") and self._refresh_rate_input is not None:
                self._refresh_rate_input.value = self.config_service.get(
                    "ui.refresh_rate_ms", int, 1000
                )
        except (OSError, ConfigurationError) as e:
            ui.notify(f"Error resetting configuration: {e}", type="negative")
        else:
            ui.notify("Configuration reset to defaults", type="positive")

    def _open_reset_config_dialog(self) -> None:
        """Show confirmation dialog before resetting configuration"""

        with ui.dialog() as dialog:
            with ui.card():
                ui.label("Reset Configuration").classes("text-lg font-bold")
                ui.label(
                    "Are you sure you want to reset the configuration to defaults?"
                ).classes("mt-2")

                with ui.row().classes("gap-2 justify-end mt-4"):
                    ui.button("Cancel", on_click=dialog.close).props("flat")

                    def _on_reset_confirm() -> None:
                        self._reset_configuration()
                        dialog.close()

                    ui.button("Reset", on_click=_on_reset_confirm).props(
                        "color=negative"
                    )

        dialog.open()

    def _create_sensor_page(self) -> None:
        """Create standalone sensor management page"""
        ui.label("Sensor Management").classes("text-h4 mb-4")
        sensors_component = SensorsComponent(self.sensor_manager, self.config_service)
        self.component_registry.register(sensors_component)
        sensors_component.render()

    def _create_config_page(self) -> None:
        """Create standalone configuration page"""
        ui.label("Configuration").classes("text-h4 mb-4")
        # JSON editor for configuration
        config_textarea = ui.textarea(
            value=self.config_service.get_raw_config_as_json()
        )
        config_textarea.classes("w-full h-64")
        with ui.row().classes("gap-2 mt-2"):
            ui.button(
                "Save", on_click=lambda: self._save_configuration(config_textarea.value)
            ).props("color=primary")
            ui.button(
                "Reset", on_click=lambda: self._reset_configuration(config_textarea)
            ).props("outline")

    def _create_setup_wizard_page(self) -> None:
        """Create setup wizard page"""
        ui.label("Setup Wizard").classes("text-h4 mb-4")
        wizard = SetupWizardComponent(
            self.config_service,
            self.sensor_manager,
            self.controller_manager,
        )
        self.component_registry.register(wizard)
        wizard.render()

    def _create_status_page(self) -> None:
        """Create system status page"""
        ui.label("System Status").classes("text-h4 mb-4")
        # Reuse dashboard content for status overview
        self._create_dashboard_content()
