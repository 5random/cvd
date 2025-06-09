"""
Dashboard component for displaying sensor data and system status.
"""

from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from nicegui import ui
import time
import psutil

from src.utils.config_utils.config_service import ConfigurationService
from src.utils.log_utils.log_service import info, warning, error, debug
from src.utils.log_utils import log_service

from src.data_handler.sources.sensor_source_manager import SensorManager
from src.data_handler.interface.sensor_interface import SensorReading, SensorStatus
from src.gui.gui_tab_components.gui_tab_base_component import (
    TimedComponent,
    BaseComponent,
    ComponentConfig,
    get_component_registry,
)
from src.gui.gui_elements.gui_webcam_stream_element import CameraStreamComponent
from src.controllers.controller_manager import ControllerManager
from src.controllers.controller_base import ControllerStatus


@dataclass
class SensorCardConfig:
    """Configuration for sensor display cards"""

    sensor_id: str
    title: str
    unit: str = "°C"
    precision: int = 1
    warning_threshold: Optional[float] = None
    error_threshold: Optional[float] = None


class SensorCardComponent(TimedComponent):
    """Individual sensor display card"""

    timer_attributes = ["_update_timer"]

    def __init__(
        self,
        config: ComponentConfig,
        sensor_config: SensorCardConfig,
        sensor_manager: SensorManager,
    ):
        super().__init__(config)
        self.sensor_config = sensor_config
        self.sensor_manager = sensor_manager
        self._value_label: Optional[ui.label] = None
        self._status_icon: Optional[ui.icon] = None
        self._timestamp_label: Optional[ui.label] = None
        self._update_timer: Optional[ui.timer] = None

    def render(self) -> ui.card:
        """Render sensor card"""
        with ui.card().classes("p-4 cvd-card min-w-48") as card:
            # Header with title and status
            with ui.row().classes("w-full items-center mb-2"):
                ui.label(self.sensor_config.title).classes(
                    "text-lg font-semibold flex-grow"
                )
                self._status_icon = ui.icon("circle", size="sm").classes("ml-2")

            # Value display
            with ui.row().classes("w-full items-baseline"):
                self._value_label = ui.label("--").classes("cvd-sensor-value text-2xl")
                ui.label(self.sensor_config.unit).classes("text-sm text-gray-500 ml-1")

            # Timestamp
            self._timestamp_label = ui.label("No data").classes(
                "text-xs text-gray-400 mt-1"
            )

            # Start update timer
            self._update_timer = ui.timer(1.0, self._update_display)

        # mark as rendered so the element can be moved later
        self._rendered = True
        self._element = card

        return card

    def _update_display(self) -> None:
        """Update sensor display with latest reading"""
        try:
            reading = self.sensor_manager.get_sensor_reading(
                self.sensor_config.sensor_id
            )

            if reading:
                self._update_value(reading)
                self._update_status(reading)
                self._update_timestamp(reading)
            else:
                self._show_no_data()
        except Exception as e:
            error(f"Error updating sensor card {self.sensor_config.sensor_id}: {e}")

    def _update_value(self, reading: SensorReading) -> None:
        """Update value display"""
        if self._value_label and reading.value is not None:
            formatted_value = f"{reading.value:.{self.sensor_config.precision}f}"
            self._value_label.text = formatted_value

            # Apply color based on thresholds
            color_class = self._get_value_color(reading.value)
            self._value_label.classes(
                replace=f"cvd-sensor-value text-2xl {color_class}"
            )

    def _update_status(self, reading: SensorReading) -> None:
        """Update status icon"""
        if not self._status_icon:
            return

        status_config = {
            SensorStatus.OK: ("check_circle", "text-green-500"),
            SensorStatus.ERROR: ("error", "text-red-500"),
            SensorStatus.OFFLINE: ("radio_button_unchecked", "text-gray-400"),
            SensorStatus.CALIBRATING: ("schedule", "text-yellow-500"),
            SensorStatus.TIMEOUT: ("timer_off", "text-orange-500"),
        }

        icon, color = status_config.get(reading.status, ("help", "text-gray-400"))
        self._status_icon.name = icon
        self._status_icon.classes(replace=color)

    def _update_timestamp(self, reading: SensorReading) -> None:
        """Update timestamp display"""
        if self._timestamp_label:
            time_diff = time.time() - reading.timestamp
            if time_diff < 60:
                time_str = f"{int(time_diff)}s ago"
            elif time_diff < 3600:
                time_str = f"{int(time_diff/60)}m ago"
            else:
                time_str = f"{int(time_diff/3600)}h ago"

            self._timestamp_label.text = time_str

    def _get_value_color(self, value: float) -> str:
        """Get color class based on value thresholds"""
        if (
            self.sensor_config.error_threshold
            and value >= self.sensor_config.error_threshold
        ):
            return "text-red-500"
        elif (
            self.sensor_config.warning_threshold
            and value >= self.sensor_config.warning_threshold
        ):
            return "text-yellow-500"
        else:
            return "text-green-600"

    def _show_no_data(self) -> None:
        """Show no data state"""
        if self._value_label:
            self._value_label.text = "--"
        if self._status_icon:
            self._status_icon.name = "radio_button_unchecked"
            self._status_icon.classes(replace="text-gray-400")
        if self._timestamp_label:
            self._timestamp_label.text = "No data"

    def _update_element(self, data: Any) -> None:
        """Update element with new data"""
        # Data updates are handled by timer
        pass


@dataclass
class ControllerCardConfig:
    """Configuration for controller display cards"""

    controller_id: str
    title: str


class ControllerCardComponent(TimedComponent):
    """Dashboard card for a controller"""

    timer_attributes = ["_update_timer"]

    def __init__(
        self,
        config: ComponentConfig,
        card_config: ControllerCardConfig,
        controller_manager: ControllerManager,
    ):
        super().__init__(config)
        self.card_config = card_config
        self.controller_manager = controller_manager
        self._status_icon: Optional[ui.icon] = None
        self._output_label: Optional[ui.label] = None
        self._update_timer: Optional[ui.timer] = None

    def render(self) -> ui.card:
        with ui.card().classes("p-4 cvd-card min-w-48") as card:
            with ui.row().classes("items-center mb-2"):
                ui.label(self.card_config.title).classes(
                    "text-lg font-semibold flex-grow"
                )
                self._status_icon = ui.icon("circle", size="sm")

            self._output_label = ui.label("-").classes("text-sm")

            self._update_timer = ui.timer(1.0, self._update_display)

        self._rendered = True
        self._element = card
        return card

    def _update_display(self) -> None:
        try:
            controller = self.controller_manager.get_controller(
                self.card_config.controller_id
            )
            if controller is None:
                if self._output_label:
                    self._output_label.text = "Unavailable"
                if self._status_icon:
                    self._status_icon.name = "warning"
                    self._status_icon.classes(replace="text-orange-500")
                return

            output = None
            try:
                output = controller.get_output()
            except Exception:
                pass

            if self._output_label:
                self._output_label.text = (
                    str(output) if output is not None else "No output"
                )

            if self._status_icon:
                status_config = {
                    ControllerStatus.RUNNING: ("play_circle", "text-green-500"),
                    ControllerStatus.STOPPED: ("stop_circle", "text-gray-500"),
                    ControllerStatus.ERROR: ("error", "text-red-500"),
                    ControllerStatus.PAUSED: ("pause_circle", "text-yellow-500"),
                }
                icon, color = status_config.get(
                    controller.status, ("help", "text-gray-400")
                )
                self._status_icon.name = icon
                self._status_icon.classes(replace=color)
        except Exception as exc:
            error(
                f"Error updating controller card {self.card_config.controller_id}: {exc}"
            )

    def _update_element(self, data: Any) -> None:  # pragma: no cover - handled by timer
        pass


class DashboardComponent(BaseComponent):
    """Main dashboard component"""

    def __init__(
        self,
        config_service: ConfigurationService,
        sensor_manager: SensorManager,
        controller_manager: Optional[ControllerManager],
    ):

        config = ComponentConfig("dashboard")
        super().__init__(config)
        self.config_service = config_service
        self.sensor_manager = sensor_manager
        self.controller_manager: Optional[ControllerManager] = controller_manager
        self.component_registry = get_component_registry()
        self._sensor_cards: Dict[str, SensorCardComponent] = {}
        self._controller_cards: Dict[str, ControllerCardComponent] = {}
        self._camera_stream: Optional[CameraStreamComponent] = None
        self._camera_streams: Dict[str, CameraStreamComponent] = {}

        # Filter state and timer
        self._sensor_filter: List[str] = []
        self._filter_timer: Optional[ui.timer] = None
        self._sensor_row: Optional[ui.row] = None
        self._badge: Optional[ui.badge] = None
        self._controller_row: Optional[ui.row] = None
        self._drag_sensor_id: Optional[str] = None
        self._drag_controller_id: Optional[str] = None

        # Determine which sensors and controllers should be displayed
        self._dashboard_sensors = [
            sid
            for sid, cfg in self.config_service.get_sensor_configs()
            if cfg.get("show_on_dashboard")
        ]
        self._dashboard_controllers = [
            cid
            for cid, cfg in self.config_service.get_controller_configs()
            if cfg.get("show_on_dashboard")
        ]

        layout = self.config_service.get_dashboard_layout()
        if isinstance(layout, dict):
            sensor_layout = layout.get("sensors", [])
            controller_layout = layout.get("controllers", [])
            if sensor_layout:
                ordered = [
                    sid for sid in sensor_layout if sid in self._dashboard_sensors
                ]
                ordered += [
                    sid for sid in self._dashboard_sensors if sid not in ordered
                ]
                self._dashboard_sensors = ordered
            if controller_layout:
                ordered = [
                    cid
                    for cid in controller_layout
                    if cid in self._dashboard_controllers
                ]
                ordered += [
                    cid for cid in self._dashboard_controllers if cid not in ordered
                ]
                self._dashboard_controllers = ordered

    def render(self) -> ui.column:
        """Render dashboard"""
        with ui.column().classes("w-full") as dashboard:
            # Dashboard header
            with ui.row().classes("items-center justify-between w-full"):
                ui.label("CVD Tracker Dashboard").classes("text-2xl font-bold mb-4")

            # System status overview
            self._render_system_status()

            # Main content area with camera stream and sensor data
            with ui.row().classes("w-full gap-4"):
                # Camera stream section (left side)
                if self._should_show_camera():
                    with ui.column().classes("flex-1"):
                        ui.label("Camera Stream").classes("text-lg font-semibold mb-2")
                        self._render_camera_stream()

                # Sensor data section (right side)
                if self._dashboard_sensors:
                    with ui.column().classes("flex-1"):
                        ui.label("Sensor Data").classes("text-lg font-semibold mb-2")

                        ui.select(
                            self._dashboard_sensors,
                            multiple=True,
                            value=self._sensor_filter,
                            on_change=self._on_sensor_filter_change,
                        ).props("outlined use-chips clearable").classes("w-full mb-2")
                        with ui.row().classes("w-full gap-4 flex-wrap") as sensor_row:
                            self._sensor_row = sensor_row

                            self._render_sensor_cards()

                if self._dashboard_controllers:
                    with ui.column().classes("flex-1"):
                        ui.label("Controller States").classes(
                            "text-lg font-semibold mb-2"
                        )
                        # allow drop targets by preventing default dragover behavior via event modifier
                        with (
                            ui.row()
                            .classes("w-full gap-4 flex-wrap")
                            .on("dragover.prevent", lambda _: None) as row
                        ):
                            self._controller_row = row
                            self._render_controller_cards()

        return dashboard

    def _render_system_status(self) -> None:
        """Render system status overview"""
        with ui.card().classes("w-full p-4 mb-4 cvd-card"):
            ui.label("System Status").classes("text-lg font-semibold mb-2")

            with ui.column().classes("w-full gap-2"):
                active_sensors = []
                if self.sensor_manager is not None:
                    try:
                        active_sensors = self.sensor_manager.get_active_sensors()
                    except Exception as exc:  # pragma: no cover - log and continue
                        error(f"Failed to get active sensors: {exc}")

                active_controllers = []
                if self.controller_manager is not None:
                    try:
                        for cid in self.controller_manager.list_controllers():
                            ctrl = self.controller_manager.get_controller(cid)
                            if (
                                ctrl is not None
                                and ctrl.status == ControllerStatus.RUNNING
                            ):
                                active_controllers.append(cid)
                    except Exception as exc:  # pragma: no cover - log and continue
                        error(f"Failed to get active controllers: {exc}")

                sensor_text = (
                    ", ".join(active_sensors)
                    if active_sensors
                    else ("0" if self.sensor_manager is None else "none")
                )
                controller_text = (
                    ", ".join(active_controllers)
                    if active_controllers
                    else ("0" if self.controller_manager is None else "none")
                )

                ui.label(f"Sensors running: {sensor_text}").classes("text-sm")
                ui.label(f"Controllers running: {controller_text}").classes("text-sm")

                self._cpu_label = ui.label("CPU: --%").classes("text-sm")
                self._memory_label = ui.label("RAM: --%").classes("text-sm")

                self._system_status_timer = ui.timer(1.0, self._update_system_status)

    def _update_system_status(self) -> None:
        """Update CPU and memory usage labels."""
        try:
            cpu = psutil.cpu_percent()
            mem = psutil.virtual_memory().percent
            if self._cpu_label:
                self._cpu_label.text = f"CPU: {cpu:.0f}%"
            if self._memory_label:
                self._memory_label.text = f"RAM: {mem:.0f}%"
        except Exception as exc:  # pragma: no cover - log and continue
            error(f"Failed to update system status: {exc}")

    def _should_show_camera(self) -> bool:

        return len(self._get_camera_controllers()) > 0

    def _get_camera_controllers(self) -> list[str]:
        camera_ids: list[str] = []
        for cid, cfg in self.config_service.get_controller_configs():
            if self._dashboard_controllers and cid not in self._dashboard_controllers:
                continue
            if not cfg.get("enabled", True):
                continue
            ctype = str(cfg.get("type", "")).lower()
            if ctype == "camera":
                camera_ids.append(cid)
                continue
            if ctype == "motion_detection":
                params = cfg.get("parameters", {})

                if isinstance(params, dict) and (
                    "cam_id" in params or "device_index" in params
                ):

                    camera_ids.append(cid)
        return camera_ids

    def _render_camera_stream(self) -> None:
        """Render camera stream component"""
        camera_ids = self._get_camera_controllers()
        if not camera_ids:
            return
        try:
            for cid in camera_ids:
                settings = self.config_service.get_controller_settings(cid) or {}
                resolution = settings.get("resolution")
                width, height = 480, 360
                if isinstance(resolution, list) and len(resolution) == 2:
                    width, height = int(resolution[0]), int(resolution[1])
                elif isinstance(resolution, str):
                    try:
                        parts = resolution.lower().split("x")
                        if len(parts) == 2:
                            width, height = int(parts[0]), int(parts[1])
                        else:
                            raise ValueError
                    except Exception:
                        error(
                            "Invalid resolution setting", resolution=resolution, controller_id=cid
                        )
                overlay = (
                    settings.get("overlay") if isinstance(settings, dict) else None
                )

                stream = CameraStreamComponent(
                    controller_manager=self.controller_manager,
                    update_interval=1 / 15,
                    max_width=width,
                    max_height=height,
                    component_id=f"dashboard_camera_stream_{cid}",
                    resolution=(width, height),
                    overlay_options=overlay,
                    stream_path=f"/video_feed/{cid}",
                )

                with ui.card().classes("p-2 cvd-card mb-2"):
                    ui.label(f"Camera {cid}").classes("text-sm font-semibold mb-2")
                    stream.render()
                    with ui.row().classes("gap-2 mt-2"):
                        options = ["320x240", "640x480", "1280x720"]
                        current_res = f"{width}x{height}"
                        if current_res not in options:
                            options.insert(0, current_res)
                        ui.select(
                            options,
                            value=current_res,
                            on_change=lambda e, s=stream: self._set_stream_resolution(
                                s, e.value
                            ),
                        ).classes("w-32")
                        ui.checkbox(
                            "Overlay",
                            value=stream.show_motion_overlay,
                            on_change=lambda e, s=stream: setattr(
                                s, "show_motion_overlay", e.value
                            ),
                        )

                self.component_registry.register(stream)
                self._camera_streams[cid] = stream

            # Create camera stream component
            self._camera_stream = CameraStreamComponent(
                controller_manager=self.controller_manager,
                update_interval=1 / 15,  # 15 FPS for dashboard
                max_width=480,
                max_height=360,
                component_id="dashboard_camera_stream",
                stream_path="/video_feed",
            )

            # Render the camera stream
            self._camera_stream.render()
            self.component_registry.register(self._camera_stream)

        except Exception as e:
            error(f"Error rendering camera stream: {e}")
            # Show error message instead
            with ui.card().classes("p-4 cvd-card"):
                with ui.column().classes("items-center"):
                    ui.icon("videocam_off", size="lg").classes("text-gray-400 mb-2")
                    ui.label("Camera Stream Unavailable").classes("text-gray-600")
                    ui.label(f"Error: {str(e)}").classes("text-xs text-red-500")

    def _on_sensor_filter_change(self, e) -> None:
        """Handle sensor filter selection"""
        self._sensor_filter = e.value or []
        if self._filter_timer:
            self._filter_timer.cancel()
        self._filter_timer = ui.timer(0.1, self._reload_sensor_cards, once=True)

    def _reload_sensor_cards(self) -> None:
        """Reload sensor cards based on current filter"""
        if not self._sensor_row:
            return
        for card in self._sensor_cards.values():
            card.cleanup()
        self._sensor_cards.clear()
        self._sensor_row.clear()
        self._render_sensor_cards()

    def refresh_sensors(self) -> None:
        """Reload dashboard sensors from configuration and re-render cards."""
        # Determine which sensors should be displayed on the dashboard
        self._dashboard_sensors = [
            sid
            for sid, cfg in self.config_service.get_sensor_configs()
            if cfg.get("show_on_dashboard")
        ]

        # Apply persisted layout ordering
        layout = self.config_service.get_dashboard_layout()
        if isinstance(layout, dict):
            sensor_layout = layout.get("sensors", [])
            if sensor_layout:
                ordered = [
                    sid for sid in sensor_layout if sid in self._dashboard_sensors
                ]
                ordered += [
                    sid for sid in self._dashboard_sensors if sid not in ordered
                ]
                self._dashboard_sensors = ordered

        # Remove existing cards and rebuild them
        if not self._sensor_row:
            return
        for card in self._sensor_cards.values():
            card.cleanup()
        self._sensor_cards.clear()
        self._sensor_row.clear()
        self._render_sensor_cards()

    def refresh_controllers(self) -> None:
        """Reload dashboard controllers and re-render cards."""
        if self.controller_manager is None:
            return
        self._dashboard_controllers = [
            cid
            for cid, cfg in self.config_service.get_controller_configs()
            if cfg.get("show_on_dashboard")
        ]

        layout = self.config_service.get_dashboard_layout()
        if isinstance(layout, dict):
            controller_layout = layout.get("controllers", [])
            if controller_layout:
                ordered = [
                    cid
                    for cid in controller_layout
                    if cid in self._dashboard_controllers
                ]
                ordered += [
                    cid for cid in self._dashboard_controllers if cid not in ordered
                ]
                self._dashboard_controllers = ordered

        if not self._controller_row:
            return

        for card in self._controller_cards.values():
            card.cleanup()
        self._controller_cards.clear()
        self._controller_row.clear()
        self._render_controller_cards()

    def _set_stream_resolution(self, stream: CameraStreamComponent, value: str) -> None:
        """Update resolution of a camera stream from dropdown selection."""
        try:
            width, height = (int(v) for v in value.split("x"))
            stream.max_width = width
            stream.max_height = height

        except Exception as e:
            log_service.error(f"Invalid value '{value}': {e}")
            ui.notify(f"Invalid resolution: {value}", type="negative")

    def _render_sensor_cards(self) -> None:
        """Render sensor cards"""
        cfgs = {sid: cfg for sid, cfg in self.config_service.get_sensor_configs()}

        for sensor_id in self._dashboard_sensors:
            sensor_config = cfgs.get(sensor_id)
            if not sensor_config or not sensor_config.get("enabled", True):
                continue

            if self._sensor_filter and sensor_id not in self._sensor_filter:
                continue

            # Create sensor card config
            card_config = SensorCardConfig(
                sensor_id=sensor_id,
                title=sensor_config.get("display_name", sensor_id),
                unit=sensor_config.get("unit", "°C"),
                precision=sensor_config.get("precision", 1),
                warning_threshold=sensor_config.get("warning_threshold"),
                error_threshold=sensor_config.get("error_threshold"),
            )

            # Create and render sensor card
            component_config = ComponentConfig(f"sensor_card_{sensor_id}")
            sensor_card = SensorCardComponent(
                component_config, card_config, self.sensor_manager
            )
            card_el = sensor_card.render()
            card_el.props("draggable=true")
            card_el.on(
                "dragstart", lambda e, sid=sensor_id: self._start_sensor_drag(sid)
            )
            card_el.on("drop", lambda e, sid=sensor_id: self._drop_sensor_on(sid))
            # prevent default dragover to allow drop
            card_el.on("dragover.prevent", lambda _: None)

            self._sensor_cards[sensor_id] = sensor_card

    def _render_controller_cards(self) -> None:
        if self.controller_manager is None:
            return
        cfgs = {cid: cfg for cid, cfg in self.config_service.get_controller_configs()}
        for controller_id in self._dashboard_controllers:
            cfg = cfgs.get(controller_id)
            title = cfg.get("display_name", controller_id) if cfg else controller_id

            card_config = ControllerCardConfig(
                controller_id=controller_id,
                title=title,
            )

            component_config = ComponentConfig(f"controller_card_{controller_id}")

            card_component = ControllerCardComponent(
                component_config,
                card_config,
                self.controller_manager,
            )

            card_el = card_component.render()
            card_el.props("draggable=true")
            card_el.on(
                "dragstart",
                lambda e, cid=controller_id: self._start_controller_drag(cid),
            )
            card_el.on(
                "drop", lambda e, cid=controller_id: self._drop_controller_on(cid)
            )
            card_el.on("dragover.prevent", lambda _: None)
            self._controller_cards[controller_id] = card_component

    def _start_sensor_drag(self, sensor_id: str) -> None:
        self._drag_sensor_id = sensor_id

    def _drop_sensor_on(self, target_id: str) -> None:
        if self._drag_sensor_id is None or self._sensor_row is None:
            return
        if target_id == self._drag_sensor_id:
            return
        source = self._sensor_cards.get(self._drag_sensor_id)
        target = self._sensor_cards.get(target_id)
        if not source or not target:
            return
        row_children = list(self._sensor_row.default_slot.children)
        target_index = row_children.index(target.get_element())
        source.get_element().move(
            target_container=self._sensor_row, target_index=target_index
        )
        self._update_sensor_layout()
        self._drag_sensor_id = None

    def _start_controller_drag(self, controller_id: str) -> None:
        self._drag_controller_id = controller_id

    def _drop_controller_on(self, target_id: str) -> None:
        if self._drag_controller_id is None or self._controller_row is None:
            return
        if target_id == self._drag_controller_id:
            return
        source = self._controller_cards.get(self._drag_controller_id)
        target = self._controller_cards.get(target_id)
        if not source or not target:
            return
        row_children = list(self._controller_row.default_slot.children)
        target_index = row_children.index(target.get_element())
        source.get_element().move(
            target_container=self._controller_row, target_index=target_index
        )
        self._update_controller_layout()
        self._drag_controller_id = None

    def _update_sensor_layout(self) -> None:
        if not self._sensor_row:
            return
        order: list[str] = []
        for child in self._sensor_row.default_slot.children:
            for sid, card in self._sensor_cards.items():
                if card.get_element() is child:
                    order.append(sid)
                    break
        layout = self.config_service.get_dashboard_layout()
        layout["sensors"] = order
        self.config_service.set_dashboard_layout(layout)

    def _update_controller_layout(self) -> None:
        if not self._controller_row:
            return
        order: list[str] = []
        for child in self._controller_row.default_slot.children:
            for cid, card in self._controller_cards.items():
                if card.get_element() is child:
                    order.append(cid)
                    break
        layout = self.config_service.get_dashboard_layout()
        layout["controllers"] = order
        self.config_service.set_dashboard_layout(layout)

    def _update_element(self, data: Any) -> None:
        """Update dashboard with new data"""
        # Individual sensor cards handle their own updates
        pass

    def cleanup(self) -> None:
        """Cleanup dashboard"""
        # Cleanup sensor cards
        for card in self._sensor_cards.values():
            card.cleanup()
        self._sensor_cards.clear()

        if self._filter_timer:
            self._filter_timer.cancel()
            self._filter_timer = None
        self._sensor_row = None

        for card in self._controller_cards.values():
            card.cleanup()
        self._controller_cards.clear()
        self._controller_row = None

        # Cleanup camera streams
        for stream in self._camera_streams.values():
            stream.cleanup()
        self._camera_streams.clear()

        if self._camera_stream:
            self._camera_stream.cleanup()
            self._camera_stream = None

        self._badge = None

        super().cleanup()
