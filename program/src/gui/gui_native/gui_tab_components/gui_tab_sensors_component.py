"""
Sensor management component for the CVD Tracker application.
Provides comprehensive sensor configuration, monitoring, and control capabilities.
"""

import asyncio
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple, TYPE_CHECKING
from dataclasses import dataclass
from pathlib import Path

from nicegui import ui
from nicegui.element import Element
from nicegui.elements.dialog import Dialog
from nicegui.elements.label import Label
from nicegui.elements.button import Button
from nicegui.elements.icon import Icon

from src.gui.gui_tab_components.gui_tab_base_component import (
    TimedComponent,
    BaseComponent,
    ComponentConfig,
    get_component_registry,
)

from .dialog_utils import CancelableDialogMixin
from src.controllers.controller_manager import create_cvd_controller_manager
from src.data_handler.interface.sensor_interface import SensorStatus, SensorReading
from src.data_handler.sources.sensor_source_manager import (
    SensorManager,
    SENSOR_REGISTRY,
)
from program.src.utils.config_service import ConfigurationService
from program.src.utils.log_service import info, warning, error, debug

if TYPE_CHECKING:
    from src.gui.gui_tab_components.gui_setup_wizard_component import (
        SetupWizardComponent,
    )


@dataclass
class SensorInfo:
    """Data class for sensor information"""

    sensor_id: str
    name: str
    sensor_type: str
    source: str
    interface: str
    port: str
    enabled: bool
    connected: bool
    polling: bool
    last_reading: Optional[float]
    status: str
    current_value: Optional[float]
    poll_interval_ms: int
    config: Dict[str, Any]
    unit: str = "°C"


class SensorConfigDialog(CancelableDialogMixin):
    """Dialog for sensor configuration"""

    def __init__(
        self,
        config_service: ConfigurationService,
        sensor_manager: SensorManager,
        on_save_callback=None,
    ):
        self.config_service = config_service
        self.sensor_manager = sensor_manager
        self.on_save_callback = on_save_callback
        self._dialog: Optional[Dialog] = None
        self._form_data: Dict[str, Any] = {}
        self._is_edit_mode = False
        self._original_sensor_id: Optional[str] = None

    def show_add_dialog(self) -> None:
        """Show dialog for adding new sensor"""
        self._is_edit_mode = False
        self._original_sensor_id = None
        self._form_data = {
            "sensor_id": self.config_service.generate_next_sensor_id(),
            "name": "",
            "type": "temperature",
            "source": (
                list(SENSOR_REGISTRY.keys())[0]
                if SENSOR_REGISTRY
                else "arduino_tc_board"
            ),
            "interface": "serial",
            "port": "COM3",
            "channel": 0,
            "poll_interval_ms": 1000,
            "baudrate": 9600,
            "timeout": 2.0,
            "enabled": True,
        }
        self._show_dialog("Add New Sensor")

    def show_edit_dialog(self, sensor_info: SensorInfo) -> None:
        """Show dialog for editing existing sensor"""
        self._is_edit_mode = True
        self._original_sensor_id = sensor_info.sensor_id
        self._form_data = {
            "sensor_id": sensor_info.sensor_id,
            "name": sensor_info.name,
            "type": sensor_info.sensor_type,
            "source": sensor_info.source,
            "interface": sensor_info.interface,
            "port": sensor_info.port,
            "channel": sensor_info.config.get("channel", 0),
            "poll_interval_ms": sensor_info.poll_interval_ms,
            "baudrate": sensor_info.config.get("baudrate", 9600),
            "timeout": sensor_info.config.get("timeout", 2.0),
            "enabled": sensor_info.enabled,
        }
        self._show_dialog(f"Edit Sensor: {sensor_info.sensor_id}")

    def _show_dialog(self, title: str) -> None:
        """Show the configuration dialog"""
        with ui.dialog().props("persistent") as dialog:
            self._dialog = dialog
            with ui.card().classes("w-96"):
                ui.label(title).classes("text-lg font-bold mb-4")

                with ui.column().classes("gap-4"):
                    # Basic Information
                    ui.label("Basic Information").classes("font-semibold")

                    ui.input(
                        "Sensor ID", value=self._form_data["sensor_id"]
                    ).bind_value_to(self._form_data, "sensor_id").props(
                        "outlined"
                    ).classes(
                        "w-full"
                    )

                    ui.input(
                        "Display Name", value=self._form_data["name"]
                    ).bind_value_to(self._form_data, "name").props("outlined").classes(
                        "w-full"
                    )

                    ui.select(
                        ["temperature", "pressure", "flow", "other"],
                        value=self._form_data["type"],
                        label="Sensor Type",
                    ).bind_value_to(self._form_data, "type").props("outlined").classes(
                        "w-full"
                    )

                    # Connection Settings
                    ui.separator()
                    ui.label("Connection Settings").classes("font-semibold")

                    ui.select(
                        list(SENSOR_REGISTRY.keys()),
                        value=self._form_data["source"],
                        label="Sensor Source",
                    ).bind_value_to(self._form_data, "source").props(
                        "outlined"
                    ).classes(
                        "w-full"
                    )

                    ui.select(
                        ["serial", "usb", "ethernet"],
                        value=self._form_data["interface"],
                        label="Interface",
                    ).bind_value_to(self._form_data, "interface").props(
                        "outlined"
                    ).classes(
                        "w-full"
                    )

                    ui.input("Port", value=self._form_data["port"]).bind_value_to(
                        self._form_data, "port"
                    ).props("outlined").classes("w-full")

                    with ui.row().classes("gap-2 w-full"):
                        ui.number(
                            "Channel", value=self._form_data["channel"], min=0, max=7
                        ).bind_value_to(self._form_data, "channel").props(
                            "outlined"
                        ).classes(
                            "flex-1"
                        )

                        ui.number(
                            "Poll Interval (ms)",
                            value=self._form_data["poll_interval_ms"],
                            min=100,
                            max=60000,
                            step=100,
                        ).bind_value_to(self._form_data, "poll_interval_ms").props(
                            "outlined"
                        ).classes(
                            "flex-1"
                        )

                    # Advanced Settings
                    ui.separator()
                    ui.label("Advanced Settings").classes("font-semibold")

                    with ui.row().classes("gap-2 w-full"):
                        ui.number(
                            "Baudrate",
                            value=self._form_data["baudrate"],
                            min=9600,
                            max=115200,
                        ).bind_value_to(self._form_data, "baudrate").props(
                            "outlined"
                        ).classes(
                            "flex-1"
                        )

                        ui.number(
                            "Timeout (s)",
                            value=self._form_data["timeout"],
                            min=0.1,
                            max=30.0,
                            step=0.1,
                        ).bind_value_to(self._form_data, "timeout").props(
                            "outlined"
                        ).classes(
                            "flex-1"
                        )

                    ui.checkbox(
                        "Enabled", value=self._form_data["enabled"]
                    ).bind_value_to(self._form_data, "enabled")

                    # Buttons
                    with ui.row().classes("gap-2 justify-end w-full"):
                        ui.button("Cancel", on_click=self._cancel).props("flat")
                        ui.button("Save", on_click=self._save).props("color=primary")

        dialog.open()

    def _save(self) -> None:
        """Save sensor configuration"""
        try:
            # Validate required fields
            if not self._form_data["sensor_id"].strip():
                ui.notify("Sensor ID is required", color="negative")
                return

            if not self._form_data["name"].strip():
                ui.notify("Display name is required", color="negative")
                return

            # Create configuration
            sensor_config = {
                "sensor_id": self._form_data["sensor_id"].strip(),
                "name": self._form_data["name"].strip(),
                "type": self._form_data["type"],
                "source": self._form_data["source"],
                "interface": self._form_data["interface"],
                "port": self._form_data["port"].strip(),
                "channel": int(self._form_data["channel"]),
                "poll_interval_ms": int(self._form_data["poll_interval_ms"]),
                "baudrate": int(self._form_data["baudrate"]),
                "timeout": float(self._form_data["timeout"]),
                "enabled": bool(self._form_data["enabled"]),
            }

            # Save configuration
            success = False
            if self._is_edit_mode and self._original_sensor_id:
                # Prevent duplicate sensor ID if changed
                new_id = sensor_config["sensor_id"]
                if new_id != self._original_sensor_id:
                    existing_configs = self.config_service.get_sensor_configs()
                    for existing_id, _ in existing_configs:
                        if existing_id == new_id:
                            ui.notify(
                                f"Sensor ID {new_id} already exists", color="negative"
                            )
                            return
                if self.config_service.update_sensor_config(
                    self._original_sensor_id, sensor_config
                ):
                    ui.notify(
                        f"Sensor {self._original_sensor_id} updated successfully",
                        color="positive",
                    )
                    success = True
                else:
                    ui.notify("Failed to update sensor configuration", color="negative")
                    success = False
            else:
                # Check if sensor ID already exists
                existing_configs = self.config_service.get_sensor_configs()
                for existing_id, _ in existing_configs:
                    if existing_id == sensor_config["sensor_id"]:
                        ui.notify(
                            f'Sensor ID {sensor_config["sensor_id"]} already exists',
                            color="negative",
                        )
                        return

                try:
                    self.config_service.add_sensor_config(sensor_config)
                    ui.notify(
                        f'Sensor {sensor_config["sensor_id"]} added successfully',
                        color="positive",
                    )
                    success = True
                except Exception as e:
                    ui.notify(f"Failed to add sensor: {str(e)}", color="negative")
                    success = False

            if success:
                if self._dialog:
                    self._dialog.close()
                if self.on_save_callback:
                    self.on_save_callback()

        except Exception as e:
            error(f"Error saving sensor configuration: {e}")
            ui.notify(f"Error: {str(e)}", color="negative")


class SensorCardComponent(BaseComponent):
    """Individual sensor display card"""

    def __init__(
        self,
        sensor_info: SensorInfo,
        sensor_manager: SensorManager,
        config_service: ConfigurationService,
        on_edit_callback=None,
        on_deleted=None,
    ):
        config = ComponentConfig(
            component_id=f"sensor_card_{sensor_info.sensor_id}",
            title=f"Sensor Card - {sensor_info.sensor_id}",
        )
        super().__init__(config)

        self.sensor_info = sensor_info
        self.sensor_manager = sensor_manager
        self.config_service = config_service
        self.on_edit_callback = on_edit_callback
        self.on_deleted = on_deleted

        # UI elements
        self._container: Optional[Element] = None
        self._status_icon: Optional[Icon] = None
        self._value_label: Optional[Label] = None
        self._status_label: Optional[Label] = None
        self._unit_label: Optional[Label] = None
        self._timestamp_label: Optional[Label] = None
        self._polling_button: Optional[Button] = None

    def render(self) -> Element:
        """Render sensor card"""
        with ui.card().classes("w-full max-w-sm") as card:
            self._container = card

            with ui.card_section():
                # Header with name and controls
                with ui.row().classes("items-center justify-between w-full"):
                    with ui.column().classes("gap-1"):
                        ui.label(self.sensor_info.name).classes("text-lg font-bold")
                        ui.label(self.sensor_info.sensor_id).classes(
                            "text-sm text-gray-500"
                        )

                    with ui.row().classes("gap-1"):
                        # Status icon
                        self._status_icon = ui.icon("help", size="sm").classes(
                            "text-gray-400"
                        )

                        # Control buttons
                        with ui.button(icon="more_vert").props("flat round size=sm"):
                            with ui.menu():
                                ui.menu_item("Edit", on_click=self._edit_sensor)
                                ui.menu_item("Delete", on_click=self._delete_sensor)

                # Status and value display
                with ui.row().classes("items-center gap-4 w-full"):
                    with ui.column().classes("gap-1 flex-1"):
                        ui.label("Current Value").classes("text-sm text-gray-600")
                        self._value_label = ui.label("--").classes("text-xl font-mono")

                    with ui.column().classes("gap-1"):
                        ui.label("Status").classes("text-sm text-gray-600")
                        self._status_label = ui.label(
                            self.sensor_info.status.upper()
                        ).classes("text-sm font-semibold")

                # Connection info
                with ui.row().classes("items-center gap-4 w-full mt-2"):
                    ui.label(f"Type: {self.sensor_info.sensor_type}").classes("text-sm")
                    ui.label(f"Port: {self.sensor_info.port}").classes("text-sm")

                # Polling control
                with ui.row().classes("items-center justify-between w-full mt-2"):
                    self._timestamp_label = ui.label("Last reading: Never").classes(
                        "text-xs text-gray-500"
                    )

                    self._polling_button = ui.button(
                        "Stop" if self.sensor_info.polling else "Start",
                        on_click=self._toggle_polling,
                    ).props("size=sm")

        self._update_display()
        return card

    def _update_display(self) -> None:
        """Update display with current sensor data"""
        if not self._container:
            return

        # Update status icon
        self._update_status_icon()

        # Update status label
        if self._status_label:
            self._status_label.text = self.sensor_info.status.upper()

        # Update value
        if self._value_label:
            if self.sensor_info.current_value is not None:
                self._value_label.set_text(f"{self.sensor_info.current_value:.2f}")
            else:
                self._value_label.set_text("--")

        if self._unit_label:
            self._unit_label.text = self.sensor_info.unit

        # Update timestamp
        if self._timestamp_label and self.sensor_info.last_reading:
            last_time = datetime.fromtimestamp(self.sensor_info.last_reading)
            self._timestamp_label.set_text(f"Last: {last_time.strftime('%H:%M:%S')}")

        # Update polling button
        if self._polling_button:
            self._polling_button.set_text(
                "Stop" if self.sensor_info.polling else "Start"
            )
            self._polling_button.props(
                f'color={"negative" if self.sensor_info.polling else "positive"}'
            )

    def _update_status_icon(self) -> None:
        """Update status icon based on sensor status"""
        if not self._status_icon:
            return

        status_config = {
            "ok": ("check_circle", "text-green-500"),
            "error": ("error", "text-red-500"),
            "offline": ("radio_button_unchecked", "text-gray-400"),
            "calibrating": ("schedule", "text-yellow-500"),
            "timeout": ("timer_off", "text-orange-500"),
            "unknown": ("help", "text-gray-400"),
        }

        icon, color = status_config.get(
            self.sensor_info.status.lower(), ("help", "text-gray-400")
        )
        # props() does not update the icon name dynamically; use set_name
        # to properly update the underlying DOM element
        self._status_icon.set_name(icon)
        self._status_icon.classes(replace=color)

    async def _toggle_polling(self) -> None:
        """Toggle sensor polling"""
        try:
            if self.sensor_info.polling:
                await self.sensor_manager.stop_sensor(self.sensor_info.sensor_id)
                ui.notify(f"Stopped polling {self.sensor_info.sensor_id}", color="info")
            else:
                success = await self.sensor_manager.start_sensor(
                    self.sensor_info.sensor_id
                )
                if success:
                    ui.notify(
                        f"Started polling {self.sensor_info.sensor_id}",
                        color="positive",
                    )
                else:
                    ui.notify(
                        f"Failed to start {self.sensor_info.sensor_id}",
                        color="negative",
                    )
        except Exception as e:
            error(f"Error toggling sensor polling: {e}")
            ui.notify(f"Error: {str(e)}", color="negative")

    def _edit_sensor(self) -> None:
        """Edit sensor configuration"""
        if self.on_edit_callback:
            self.on_edit_callback(self.sensor_info)

    def _delete_sensor(self) -> None:
        """Delete sensor configuration"""

        async def confirm_delete():
            try:
                # Stop sensor if running
                if self.sensor_info.polling:
                    await self.sensor_manager.stop_sensor(self.sensor_info.sensor_id)

                # Remove configuration
                if self.config_service.remove_sensor_config(self.sensor_info.sensor_id):
                    ui.notify(
                        f"Sensor {self.sensor_info.sensor_id} deleted successfully",
                        color="positive",
                    )
                    if self.on_deleted:
                        self.on_deleted(self.sensor_info)
                else:
                    ui.notify("Failed to delete sensor configuration", color="negative")

            except Exception as e:
                error(f"Error deleting sensor: {e}")
                ui.notify(f"Error: {str(e)}", color="negative")

        with ui.dialog() as dialog:
            with ui.card():
                ui.label(f"Delete Sensor: {self.sensor_info.sensor_id}").classes(
                    "text-lg font-bold"
                )
                ui.label(
                    "Are you sure you want to delete this sensor? This action cannot be undone."
                ).classes("mt-2")

                with ui.row().classes("gap-2 justify-end mt-4"):
                    ui.button("Cancel", on_click=dialog.close).props("flat")

                    async def _on_delete_confirm():
                        await confirm_delete()
                        dialog.close()

                    ui.button("Delete", on_click=_on_delete_confirm).props(
                        "color=negative"
                    )

        dialog.open()

    def update_sensor_info(self, sensor_info: SensorInfo) -> None:
        """Update sensor information and refresh display"""
        self.sensor_info = sensor_info
        self._update_display()

    def _update_element(self, data: Any) -> None:
        """Refresh the card UI when updated through the BaseComponent API."""
        self._update_display()


class SensorsComponent(TimedComponent):
    """Main sensors management component"""

    timer_attributes = ["_refresh_timer"]

    def __init__(
        self, sensor_manager: SensorManager, config_service: ConfigurationService
    ):
        config = ComponentConfig(
            component_id="sensors_component", title="Sensors Management"
        )
        super().__init__(config)

        self.sensor_manager = sensor_manager
        self.config_service = config_service

        # State
        self._all_sensors_info: Dict[str, SensorInfo] = {}
        self._sensors_info: Dict[str, SensorInfo] = {}
        self._search_term: str = ""
        self._sensor_cards: Dict[str, SensorCardComponent] = {}
        self._config_dialog: Optional[SensorConfigDialog] = None
        # can hold any wizard component instance
        self._setup_wizard: Any = None
        self._refresh_timer: Optional[ui.timer] = None

        # UI elements
        self._sensors_container: Optional[Element] = None
        self._status_summary: Optional[Element] = None
        self._search_input: Optional[ui.input] = None

    def render(self) -> Element:
        """Render the sensors component"""
        with ui.column().classes("w-full gap-4") as container:
            # Header with controls
            with ui.row().classes("items-center justify-between w-full"):
                ui.label("Sensor Management").classes("text-2xl font-bold")

                with ui.row().classes("gap-2"):
                    ui.button(
                        "Add Sensor", on_click=self._show_add_dialog, icon="add"
                    ).props("color=primary")

                    ui.button("Refresh", on_click=self._refresh_sensors, icon="refresh")

                    ui.button(
                        "Start All", on_click=self._start_all_sensors, icon="play_arrow"
                    ).props("color=positive")

                    ui.button(
                        "Stop All", on_click=self._stop_all_sensors, icon="stop"
                    ).props("color=negative")

            # Status summary
            with ui.card().classes("w-full"):
                with ui.card_section():
                    ui.label("System Status").classes("text-lg font-semibold mb-2")
                    self._status_summary = ui.column().classes("gap-2")

            # Sensors grid
            with ui.row().classes("items-center justify-between w-full"):
                ui.label("Configured Sensors").classes("text-lg font-semibold")
                self._search_input = (
                    ui.input(
                        "Search...",
                        value=self._search_term,
                        on_change=self._on_search_change,
                    )
                    .props("dense outlined clearable")
                    .classes("w-64")
                )
            self._sensors_container = ui.grid(columns=3).classes("w-full gap-4")

        # Initialize config dialog
        self._config_dialog = SensorConfigDialog(
            self.config_service, self.sensor_manager, self._refresh_sensors
        )

        # Start auto-refresh
        self._start_auto_refresh()

        # Initial load
        self._refresh_sensors()

        return container

    def _start_auto_refresh(self) -> None:
        """Start auto-refresh timer"""
        if self._refresh_timer:
            self._refresh_timer.cancel()
        self._refresh_timer = ui.timer(2.0, self._update_sensor_data)

    def _refresh_sensors(self) -> None:
        """Refresh sensor configurations and data"""
        try:
            # Get sensor configurations
            sensor_configs = self.config_service.get_sensor_configs()

            # Get sensor status
            sensor_status = self.sensor_manager.get_sensor_status()

            # Get latest readings
            latest_readings = self.sensor_manager.get_latest_readings()

            # Update sensor info
            new_sensors_info = {}

            for sensor_id, config in sensor_configs:
                # Get status info
                status_info = sensor_status.get(sensor_id, {})

                # Get latest reading
                reading = latest_readings.get(sensor_id)

                sensor_info = SensorInfo(
                    sensor_id=sensor_id,
                    name=config.get("name", sensor_id),
                    sensor_type=config.get("type", "unknown"),
                    source=config.get("source", "unknown"),
                    interface=config.get("interface", "unknown"),
                    port=config.get("port", "unknown"),
                    enabled=config.get("enabled", True),
                    connected=status_info.get("connected", False),
                    polling=status_info.get("polling", False),
                    last_reading=status_info.get("last_reading"),
                    status=status_info.get("status", "unknown"),
                    current_value=reading.value if reading else None,
                    poll_interval_ms=config.get("poll_interval_ms", 1000),
                    unit=config.get("unit", "°C"),
                    config=config,
                )

                new_sensors_info[sensor_id] = sensor_info

            self._all_sensors_info = new_sensors_info
            self._apply_search_filter()

        except Exception as e:
            error(f"Error refreshing sensors: {e}")
            ui.notify(f"Error refreshing sensors: {str(e)}", color="negative")

    def _update_sensor_data(self) -> None:
        """Update sensor data without full refresh"""
        try:
            # Get sensor status
            sensor_status = self.sensor_manager.get_sensor_status()

            # Get latest readings
            latest_readings = self.sensor_manager.get_latest_readings()

            # Update existing sensor info
            for sensor_id, sensor_info in self._all_sensors_info.items():
                status_info = sensor_status.get(sensor_id, {})
                reading = latest_readings.get(sensor_id)

                # Update fields that can change
                sensor_info.connected = status_info.get("connected", False)
                sensor_info.polling = status_info.get("polling", False)
                sensor_info.last_reading = status_info.get("last_reading")
                sensor_info.status = status_info.get("status", "unknown")
                sensor_info.current_value = reading.value if reading else None

                # Update card display
                if sensor_id in self._sensor_cards:
                    self._sensor_cards[sensor_id].update_sensor_info(sensor_info)

            self._update_status_summary()

        except Exception as e:
            error(f"Error updating sensor data: {e}")

    def _update_sensor_cards(self) -> None:
        """Update sensor cards display"""
        if not self._sensors_container:
            return

        # Clear existing cards
        self._sensors_container.clear()
        self._sensor_cards.clear()

        # Create new cards
        for sensor_id, sensor_info in self._sensors_info.items():
            card = SensorCardComponent(
                sensor_info,
                self.sensor_manager,
                self.config_service,
                self._edit_sensor,
                self._sensor_deleted,
            )

            with self._sensors_container:
                card.render()

            self._sensor_cards[sensor_id] = card

    def _update_status_summary(self) -> None:
        """Update status summary"""
        if not self._status_summary:
            return

        self._status_summary.clear()

        # Count sensors by status
        total_sensors = len(self._sensors_info)
        connected_sensors = sum(1 for s in self._sensors_info.values() if s.connected)
        polling_sensors = sum(1 for s in self._sensors_info.values() if s.polling)
        error_sensors = sum(
            1
            for s in self._sensors_info.values()
            if s.status and s.status.lower() == "error"
        )

        with self._status_summary:
            with ui.row().classes("gap-6"):
                ui.label(f"Total: {total_sensors}").classes("font-semibold")
                ui.label(f"Connected: {connected_sensors}").classes(
                    "text-green-600" if connected_sensors > 0 else "text-gray-500"
                )
                ui.label(f"Polling: {polling_sensors}").classes(
                    "text-blue-600" if polling_sensors > 0 else "text-gray-500"
                )
                ui.label(f"Errors: {error_sensors}").classes(
                    "text-red-600" if error_sensors > 0 else "text-gray-500"
                )

    def _on_search_change(self, e) -> None:
        """Handle search input change"""
        self._search_term = e.value if e.value else ""
        self._apply_search_filter()

    def _apply_search_filter(self) -> None:
        """Filter sensors based on the current search term"""
        term = self._search_term.lower()
        if term:
            self._sensors_info = {
                sid: info
                for sid, info in self._all_sensors_info.items()
                if term in sid.lower() or term in info.name.lower()
            }
        else:
            self._sensors_info = dict(self._all_sensors_info)
        self._update_sensor_cards()
        self._update_status_summary()

    def _show_add_dialog(self) -> None:
        """Show sensor setup wizard."""
        from src.gui.gui_elements.gui_sensor_setup_wizard_element import (
            SensorSetupWizardComponent,
        )

        def _on_close() -> None:
            """Handle wizard close event."""
            self._setup_wizard = None
            self._refresh_sensors()

            registry = get_component_registry()
            dashboard = registry.get_component("dashboard")
            if dashboard and hasattr(dashboard, "refresh_sensors"):
                dashboard.refresh_sensors()

        self._setup_wizard = SensorSetupWizardComponent(
            self.config_service,
            self.sensor_manager,
            on_close=_on_close,
        )
        self._setup_wizard.show_dialog()

    def _edit_sensor(self, sensor_info: SensorInfo) -> None:
        """Edit sensor configuration"""
        if self._config_dialog:
            self._config_dialog.show_edit_dialog(sensor_info)

    def _sensor_deleted(self, sensor_info: SensorInfo) -> None:
        """Refresh list after sensor deletion"""
        self._refresh_sensors()

        registry = get_component_registry()
        dashboard = registry.get_component("dashboard")
        if dashboard and hasattr(dashboard, "refresh_sensors"):
            dashboard.refresh_sensors()

    async def _start_all_sensors(self) -> None:
        """Start all configured sensors"""
        try:
            count = await self.sensor_manager.start_all_configured_sensors()
            ui.notify(f"Started {count} sensors", color="positive")
        except Exception as e:
            error(f"Error starting all sensors: {e}")
            ui.notify(f"Error: {str(e)}", color="negative")

    async def _stop_all_sensors(self) -> None:
        """Stop all active sensors"""
        try:
            active_sensors = self.sensor_manager.get_active_sensors()
            for sensor_id in active_sensors:
                await self.sensor_manager.stop_sensor(sensor_id)
            ui.notify(f"Stopped {len(active_sensors)} sensors", color="info")
        except Exception as e:
            error(f"Error stopping all sensors: {e}")
            ui.notify(f"Error: {str(e)}", color="negative")

    def _update_element(self, data: Any) -> None:
        """Update element with new data (required by BaseComponent)"""
        # Data updates are handled by timer
        pass

    def cleanup(self) -> None:
        """Cleanup component resources"""
        super().cleanup()
