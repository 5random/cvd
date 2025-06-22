"""Setup wizard component using NiceGUI stepper for comprehensive sensor configuration."""

from typing import Optional, Callable, List
from nicegui import ui
from serial.tools import list_ports

from src.gui.gui_tab_components.gui_tab_base_component import (
    BaseComponent,
    ComponentConfig,
)
from .gui_wizard_mixin import WizardMixin
from src.data_handler.sources.sensor_source_manager import (
    SensorManager,
    SENSOR_REGISTRY,
)
from src.data_handler.interface.sensor_interface import SensorStatus
from src.gui.ui_helpers import notify_later
from src.utils.config_service import ConfigurationService
from src.utils.log_service import info, warning, error


class SensorSetupWizardComponent(WizardMixin, BaseComponent):
    """Comprehensive 4-step sensor setup wizard using NiceGUI stepper."""

    def __init__(
        self,
        config_service: ConfigurationService,
        sensor_manager: SensorManager,
        on_close: Optional[Callable[[], None]] = None,
    ):
        config = ComponentConfig("sensor_setup_wizard")
        super().__init__(config)
        self.config_service = config_service
        self.sensor_manager = sensor_manager
        self.on_close = on_close

        self._dialog = None
        self._stepper = None

        # Wizard data
        self._wizard_data = {
            "sensor_id": "",
            "name": "",
            "type": "temperature",
            "source": "",
            "interface": "serial",
            "port": "COM3",
            "channel": 0,
            "poll_interval_ms": 1000,
            "baudrate": 9600,
            "timeout": 2.0,
            "enabled": True,
            "show_on_dashboard": True,
            "filters": [],  # List of filter configurations
        }

        # UI elements for each step
        self._step1_elements = {}
        self._step2_elements = {}
        self._step3_elements = {}
        self._step4_elements = {}

        # Available filter types with their parameters
        self._available_filters = {
            "Moving Average": {
                "class": "MovingAverageFilter",
                "description": "Smooths sensor readings using a moving average",
                "parameters": {
                    "window_size": {
                        "type": "int",
                        "default": 5,
                        "min": 2,
                        "max": 50,
                        "label": "Window Size",
                    }
                },
            },
            "Range Validation": {
                "class": "RangeValidationFilter",
                "description": "Validates readings are within expected range",
                "parameters": {
                    "min_value": {
                        "type": "float",
                        "default": None,
                        "label": "Minimum Value (optional)",
                    },
                    "max_value": {
                        "type": "float",
                        "default": None,
                        "label": "Maximum Value (optional)",
                    },
                },
            },
            "Outlier Detection": {
                "class": "OutlierDetectionFilter",
                "description": "Detects and removes statistical outliers",
                "parameters": {
                    "threshold_std": {
                        "type": "float",
                        "default": 2.0,
                        "min": 0.5,
                        "max": 5.0,
                        "label": "Std Dev Threshold",
                    },
                    "min_samples": {
                        "type": "int",
                        "default": 10,
                        "min": 3,
                        "max": 100,
                        "label": "Min Samples",
                    },
                },
            },
        }

    def render(self) -> ui.column:
        """Render method required by BaseComponent."""
        with ui.column().classes("w-full") as container:
            ui.label("Sensor Setup Wizard Component").classes("text-lg font-bold")
            ui.label("Use show_dialog() to display the wizard").classes(
                "text-sm text-gray-500"
            )
        return container

    def show_dialog(self) -> None:
        """Display the sensor setup wizard in a dialog."""
        self._reset_wizard_data()

        with ui.dialog().props("persistent") as dialog:
            self._dialog = dialog
            with ui.card().classes("w-[800px] max-w-[90vw] h-[600px]"):
                with ui.column().classes("w-full h-full"):
                    # Header
                    with ui.row().classes(
                        "items-center justify-between w-full p-4 border-b"
                    ):
                        ui.label("Sensor Setup Wizard").classes("text-xl font-bold")
                        ui.button(icon="close", on_click=self._close_dialog).props(
                            "flat round"
                        )

                    # Stepper content
                    with ui.column().classes("flex-1 p-4"):
                        self._render_stepper()

        dialog.open()

    def _reset_wizard_data(self) -> None:
        """Reset wizard data to defaults."""
        self._wizard_data = {
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
            "show_on_dashboard": True,
            "filters": [],
        }

    def _render_stepper(self) -> None:
        """Render the 4-step wizard stepper."""
        with ui.stepper().props("vertical") as stepper:
            self._stepper = stepper

            # Step 1: Basic Sensor Information
            with ui.step("basic_info", title="Basic Information", icon="info"):
                self._render_step1()
                with ui.stepper_navigation():
                    ui.button("Next", on_click=self._stepper.next).props(
                        "color=primary"
                    )
                    ui.button("Cancel", on_click=self._close_dialog).props("flat")

            # Step 2: Source and Interface Configuration
            with ui.step(
                "source_config",
                title="Source & Interface",
                icon="settings_input_component",
            ):
                self._render_step2()
                with ui.stepper_navigation():
                    ui.button("Previous", on_click=self._stepper.previous)
                    ui.button("Next", on_click=self._validate_and_next_step2).props(
                        "color=primary"
                    )
                    ui.button("Test Connection", on_click=self._test_connection).props(
                        "color=secondary"
                    )
                    ui.button("Cancel", on_click=self._close_dialog).props("flat")

            # Step 3: Data Processing Pipeline
            with ui.step("processing", title="Data Processing", icon="tune"):
                self._render_step3()
                with ui.stepper_navigation():
                    ui.button("Previous", on_click=self._stepper.previous)
                    ui.button("Next", on_click=self._stepper.next).props(
                        "color=primary"
                    )
                    ui.button("Cancel", on_click=self._close_dialog).props("flat")

            # Step 4: Review and Confirmation
            with ui.step("review", title="Review & Confirm", icon="check_circle"):
                self._render_step4()
                with ui.stepper_navigation():
                    ui.button("Previous", on_click=self._stepper.previous)
                    ui.button("Create Sensor", on_click=self._create_sensor).props(
                        "color=positive"
                    )
                    ui.button("Cancel", on_click=self._close_dialog).props("flat")

    def _render_step1(self) -> None:
        """Render step 1: Basic sensor information."""
        ui.label("Configure basic sensor information").classes("text-lg mb-4")

        with ui.column().classes("gap-4 w-full"):
            # Sensor ID (auto-generated, not editable)
            with ui.row().classes("items-center gap-4"):
                ui.label("Sensor ID:").classes("w-32 font-semibold")
                self._step1_elements["sensor_id"] = (
                    ui.input(value=self._wizard_data["sensor_id"])
                    .props("readonly outlined")
                    .classes("flex-1")
                )
                ui.button(icon="refresh", on_click=self._regenerate_sensor_id).props(
                    "flat"
                ).tooltip("Generate new ID")

            # Sensor name
            with ui.row().classes("items-center gap-4"):
                ui.label("Display Name:").classes("w-32 font-semibold")
                self._step1_elements["name"] = (
                    ui.input(placeholder="Enter sensor display name")
                    .bind_value_to(self._wizard_data, "name")
                    .props("outlined")
                    .classes("flex-1")
                )

            # Sensor type
            with ui.row().classes("items-center gap-4"):
                ui.label("Sensor Type:").classes("w-32 font-semibold")
                self._step1_elements["type"] = (
                    ui.select(
                        ["temperature", "pressure", "flow", "level", "ph"],
                        value=self._wizard_data["type"],
                    )
                    .bind_value_to(self._wizard_data, "type")
                    .props("outlined")
                    .classes("flex-1")
                )

            # Dashboard visibility
            with ui.row().classes("items-center gap-4"):
                ui.label("Dashboard:").classes("w-32 font-semibold")
                self._step1_elements["show_on_dashboard"] = ui.checkbox(
                    "Show on Dashboard", value=self._wizard_data["show_on_dashboard"]
                ).bind_value_to(self._wizard_data, "show_on_dashboard")

    def _render_step2(self) -> None:
        """Render step 2: Source selection and interface configuration."""
        ui.label("Configure sensor source and communication interface").classes(
            "text-lg mb-4"
        )

        with ui.column().classes("gap-4 w-full"):
            # Source selection
            with ui.row().classes("items-center gap-4"):
                ui.label("Sensor Source:").classes("w-32 font-semibold")
                self._step2_elements["source"] = (
                    ui.select(
                        list(SENSOR_REGISTRY.keys()),
                        value=self._wizard_data["source"],
                        on_change=self._on_source_change,
                    )
                    .bind_value_to(self._wizard_data, "source")
                    .props("outlined")
                    .classes("flex-1")
                )

            # Interface type
            with ui.row().classes("items-center gap-4"):
                ui.label("Interface:").classes("w-32 font-semibold")
                self._step2_elements["interface"] = (
                    ui.select(
                        ["serial", "usb", "ethernet", "modbus"],
                        value=self._wizard_data["interface"],
                        on_change=self._on_interface_change,
                    )
                    .bind_value_to(self._wizard_data, "interface")
                    .props("outlined")
                    .classes("flex-1")
                )

            # Dynamic interface configuration
            self._step2_elements["interface_config"] = ui.column().classes(
                "gap-4 w-full"
            )
            self._update_interface_config()

    def _render_step3(self) -> None:
        """Render step 3: Data processing pipeline setup."""
        ui.label("Configure data processing filters and algorithms").classes(
            "text-lg mb-4"
        )

        with ui.column().classes("gap-4 w-full"):  # Add filter section
            with ui.card().classes("w-full"):
                with ui.card_section():
                    ui.label("Add Data Processing Filter").classes("font-semibold mb-2")

                    with ui.row().classes("items-center gap-4"):
                        filter_select = (
                            ui.select(
                                list(self._available_filters.keys()),
                                label="Filter Type",
                            )
                            .props("outlined")
                            .classes("flex-1")
                        )

                        ui.button(
                            "Add Filter",
                            on_click=lambda: self._add_filter(
                                filter_select.value if filter_select.value else ""
                            ),
                            icon="add",
                        ).props("color=primary")

            # Current filters
            self._step3_elements["filters_container"] = ui.column().classes(
                "gap-2 w-full"
            )
            self._update_filters_display()

    def _render_step4(self) -> None:
        """Render step 4: Review and confirmation."""
        ui.label("Review sensor configuration before creation").classes("text-lg mb-4")

        self._step4_elements["review_container"] = ui.column().classes("gap-4 w-full")
        self._update_review_display()

    def _regenerate_sensor_id(self) -> None:
        """Generate a new sensor ID."""
        new_id = self.config_service.generate_next_sensor_id()
        self._wizard_data["sensor_id"] = new_id
        if "sensor_id" in self._step1_elements:
            self._step1_elements["sensor_id"].set_value(new_id)

    def _on_source_change(self, e) -> None:
        """Handle source selection change."""
        # Update interface options based on source
        self._update_interface_config()

    def _on_interface_change(self, e) -> None:
        """Handle interface type change."""
        self._update_interface_config()

    def _update_interface_config(self) -> None:
        """Update interface configuration fields based on selected interface."""
        if "interface_config" not in self._step2_elements:
            return

        container = self._step2_elements["interface_config"]
        container.clear()

        interface = self._wizard_data["interface"]

        with container:
            if interface in ["serial", "usb"]:
                # Serial/USB configuration
                port_names: List[str] = []
                try:
                    port_names = [p.device for p in list_ports.comports()]
                except Exception as e:  # pragma: no cover - extremely unlikely
                    warning(f"Failed to list serial ports: {e}")

                default_port = self._wizard_data.get("port")
                if not port_names:
                    port_names = [default_port] if default_port else []

                with ui.row().classes("items-center gap-4"):
                    ui.label("Port:").classes("w-32 font-semibold")
                    ui.select(
                        port_names,
                        value=self._wizard_data["port"],
                        with_input=True,
                        new_value_mode="add-unique",
                    ).bind_value_to(self._wizard_data, "port").props(
                        "outlined"
                    ).classes(
                        "flex-1"
                    )

                with ui.row().classes("items-center gap-4"):
                    ui.label("Channel:").classes("w-32 font-semibold")
                    ui.number(
                        min=0, max=15, value=self._wizard_data["channel"]
                    ).bind_value_to(self._wizard_data, "channel").props(
                        "outlined"
                    ).classes(
                        "flex-1"
                    )

                with ui.row().classes("items-center gap-4"):
                    ui.label("Baudrate:").classes("w-32 font-semibold")
                    ui.select(
                        [9600, 19200, 38400, 57600, 115200],
                        value=self._wizard_data["baudrate"],
                    ).bind_value_to(self._wizard_data, "baudrate").props(
                        "outlined"
                    ).classes(
                        "flex-1"
                    )

                with ui.row().classes("items-center gap-4"):
                    ui.label("Timeout (s):").classes("w-32 font-semibold")
                    ui.number(
                        min=0.1, max=30.0, step=0.1, value=self._wizard_data["timeout"]
                    ).bind_value_to(self._wizard_data, "timeout").props(
                        "outlined"
                    ).classes(
                        "flex-1"
                    )

            elif interface == "modbus":
                # Modbus configuration
                with ui.row().classes("items-center gap-4"):
                    ui.label("Address:").classes("w-32 font-semibold")
                    ui.input(placeholder="192.168.1.100:502").bind_value_to(
                        self._wizard_data, "port"
                    ).props("outlined").classes("flex-1")

                with ui.row().classes("items-center gap-4"):
                    ui.label("Unit ID:").classes("w-32 font-semibold")
                    ui.number(
                        min=1, max=255, value=self._wizard_data.get("unit_id", 1)
                    ).bind_value_to(self._wizard_data, "unit_id").props(
                        "outlined"
                    ).classes(
                        "flex-1"
                    )

            elif interface == "ethernet":
                # Ethernet configuration
                with ui.row().classes("items-center gap-4"):
                    ui.label("IP Address:").classes("w-32 font-semibold")
                    ui.input(placeholder="192.168.1.100").bind_value_to(
                        self._wizard_data, "ip_address"
                    ).props("outlined").classes("flex-1")

                with ui.row().classes("items-center gap-4"):
                    ui.label("Port:").classes("w-32 font-semibold")
                    ui.number(
                        min=1, max=65535, value=self._wizard_data.get("port", 502)
                    ).bind_value_to(self._wizard_data, "port").props(
                        "outlined"
                    ).classes(
                        "flex-1"
                    )

            # Common settings
            with ui.row().classes("items-center gap-4"):
                ui.label("Poll Interval:").classes("w-32 font-semibold")
                ui.number(
                    suffix="ms",
                    min=100,
                    max=60000,
                    step=100,
                    value=self._wizard_data["poll_interval_ms"],
                ).bind_value_to(self._wizard_data, "poll_interval_ms").props(
                    "outlined"
                ).classes(
                    "flex-1"
                )

    def _add_filter(self, filter_type: str) -> None:
        """Add a filter to the processing pipeline."""
        if not filter_type or filter_type not in self._available_filters:
            ui.notify("Please select a valid filter type", color="warning")
            return

        filter_config = self._available_filters[filter_type]
        filter_id = f"filter_{len(self._wizard_data['filters']) + 1}"

        # Create filter configuration with default parameters
        new_filter = {
            "id": filter_id,
            "type": filter_type,
            "class": filter_config["class"],
            "parameters": {},
        }

        # Set default parameter values
        for param_name, param_config in filter_config["parameters"].items():
            new_filter["parameters"][param_name] = param_config["default"]

        self._wizard_data["filters"].append(new_filter)
        self._update_filters_display()
        ui.notify(f"Added {filter_type} filter", color="positive")

    def _remove_filter(self, filter_index: int) -> None:
        """Remove a filter from the processing pipeline."""
        if 0 <= filter_index < len(self._wizard_data["filters"]):
            removed_filter = self._wizard_data["filters"].pop(filter_index)
            self._update_filters_display()
            ui.notify(f"Removed {removed_filter['type']} filter", color="info")

    def _update_filters_display(self) -> None:
        """Update the filters display in step 3."""
        if "filters_container" not in self._step3_elements:
            return

        container = self._step3_elements["filters_container"]
        container.clear()

        if not self._wizard_data["filters"]:
            with container:
                ui.label("No filters configured").classes(
                    "text-gray-500 text-center py-4"
                )
            return

        with container:
            for i, filter_config in enumerate(self._wizard_data["filters"]):
                with ui.card().classes("w-full"):
                    with ui.card_section():
                        with ui.row().classes("items-center justify-between w-full"):
                            ui.label(f"{filter_config['type']} Filter").classes(
                                "font-semibold"
                            )
                            ui.button(
                                icon="delete",
                                on_click=lambda e, idx=i: self._remove_filter(idx),
                            ).props("flat color=negative")

                        # Show filter parameters
                        filter_def = self._available_filters[filter_config["type"]]
                        ui.label(filter_def["description"]).classes(
                            "text-sm text-gray-600 mb-2"
                        )

                        if filter_config["parameters"]:
                            with ui.column().classes("gap-2"):
                                for param_name, param_value in filter_config[
                                    "parameters"
                                ].items():
                                    param_def = filter_def["parameters"][param_name]
                                    with ui.row().classes("items-center gap-4"):
                                        ui.label(f"{param_def['label']}:").classes(
                                            "w-32"
                                        )

                                        if param_def["type"] == "int":
                                            ui.number(
                                                value=param_value,
                                                min=param_def.get("min"),
                                                max=param_def.get("max"),
                                            ).bind_value_to(
                                                filter_config["parameters"], param_name
                                            ).classes(
                                                "flex-1"
                                            )
                                        elif param_def["type"] == "float":
                                            ui.number(
                                                value=param_value,
                                                min=param_def.get("min"),
                                                max=param_def.get("max"),
                                                step=0.1,
                                            ).bind_value_to(
                                                filter_config["parameters"], param_name
                                            ).classes(
                                                "flex-1"
                                            )

    def _update_review_display(self) -> None:
        """Update the review display in step 4."""
        if "review_container" not in self._step4_elements:
            return

        container = self._step4_elements["review_container"]
        container.clear()

        with container:
            # Basic Information
            with ui.card().classes("w-full"):
                with ui.card_section():
                    ui.label("Basic Information").classes("text-lg font-semibold mb-2")

                    with ui.column().classes("gap-1"):
                        ui.label(
                            f"Sensor ID: {self._wizard_data['sensor_id']}"
                        ).classes("font-mono")
                        ui.label(
                            f"Name: {self._wizard_data['name'] or 'Not specified'}"
                        )
                        ui.label(f"Type: {self._wizard_data['type'].title()}")
                        ui.label(
                            f"Show on Dashboard: {'Yes' if self._wizard_data['show_on_dashboard'] else 'No'}"
                        )

            # Source & Interface Configuration
            with ui.card().classes("w-full"):
                with ui.card_section():
                    ui.label("Source & Interface").classes("text-lg font-semibold mb-2")

                    with ui.column().classes("gap-1"):
                        ui.label(f"Source: {self._wizard_data['source']}")
                        ui.label(f"Interface: {self._wizard_data['interface'].title()}")

                        if self._wizard_data["interface"] in ["serial", "usb"]:
                            ui.label(f"Port: {self._wizard_data['port']}")
                            ui.label(f"Channel: {self._wizard_data['channel']}")
                            ui.label(f"Baudrate: {self._wizard_data['baudrate']}")
                            ui.label(f"Timeout: {self._wizard_data['timeout']}s")
                        elif self._wizard_data["interface"] == "modbus":
                            ui.label(f"Address: {self._wizard_data['port']}")
                            ui.label(f"Unit ID: {self._wizard_data.get('unit_id', 1)}")
                        elif self._wizard_data["interface"] == "ethernet":
                            ui.label(
                                f"IP Address: {self._wizard_data.get('ip_address', 'Not specified')}"
                            )
                            ui.label(f"Port: {self._wizard_data.get('port', 502)}")

                        ui.label(
                            f"Poll Interval: {self._wizard_data['poll_interval_ms']}ms"
                        )
            # Data Processing
            with ui.card().classes("w-full"):
                with ui.card_section():
                    ui.label("Data Processing").classes("text-lg font-semibold mb-2")

                    if self._wizard_data["filters"]:
                        with ui.column().classes("gap-2"):
                            for i, filter_config in enumerate(
                                self._wizard_data["filters"]
                            ):
                                ui.label(
                                    f"{i+1}. {filter_config['type']} Filter"
                                ).classes("font-semibold")
                                if filter_config["parameters"]:
                                    with ui.column().classes("gap-1 ml-4"):
                                        for param_name, param_value in filter_config[
                                            "parameters"
                                        ].items():
                                            ui.label(
                                                f"• {param_name}: {param_value}"
                                            ).classes("text-sm")
                    else:
                        ui.label("No filters configured").classes("text-gray-500")

    def _validate_and_next_step2(self) -> None:
        """Validate step 2 configuration and proceed to next step."""
        # Validate required fields
        errors = []

        if not self._wizard_data["source"]:
            errors.append("Sensor source is required")

        if not self._wizard_data["interface"]:
            errors.append("Interface type is required")

        if (
            self._wizard_data["interface"] in ["serial", "usb"]
            and not self._wizard_data["port"]
        ):
            errors.append("Port is required for serial/USB interface")

        if self._wizard_data["interface"] == "modbus" and not self._wizard_data["port"]:
            errors.append("Address is required for Modbus interface")

        if self._wizard_data["interface"] == "ethernet":
            if not self._wizard_data.get("ip_address"):
                errors.append("IP address is required for Ethernet interface")

        if errors:
            ui.notify("; ".join(errors), color="negative")
            return

        if self._stepper:
            self._stepper.next()

    def _test_connection(self) -> None:
        """Create a temporary sensor and read a single value."""
        import asyncio

        asyncio.create_task(self._test_connection_async())

    async def _test_connection_async(self) -> None:
        """Asynchronously test the sensor connection."""
        try:
            # Build temporary sensor configuration using current wizard data
            sensor_config = {
                "sensor_id": self._wizard_data["sensor_id"],
                "name": self._wizard_data.get("name", "temp"),
                "type": self._wizard_data["type"],
                "source": self._wizard_data["source"],
                "interface": self._wizard_data["interface"],
                "enabled": True,
                "show_on_dashboard": False,
            }

            if self._wizard_data["interface"] in ["serial", "usb"]:
                sensor_config.update(
                    {
                        "port": self._wizard_data.get("port"),
                        "channel": self._wizard_data.get("channel", 0),
                        "baudrate": self._wizard_data.get("baudrate", 9600),
                        "timeout": self._wizard_data.get("timeout", 2.0),
                    }
                )
            elif self._wizard_data["interface"] == "modbus":
                sensor_config.update(
                    {
                        "port": self._wizard_data.get("port"),
                        "address": self._wizard_data.get("port"),
                        "unit_id": self._wizard_data.get("unit_id", 1),
                    }
                )
            elif self._wizard_data["interface"] == "ethernet":
                sensor_config.update(
                    {
                        "ip_address": self._wizard_data.get("ip_address"),
                        "port": self._wizard_data.get("port", 502),
                    }
                )

            # Create sensor instance without registering
            sensor = self.sensor_manager.create_sensor(sensor_config)
            if not sensor:
                notify_later(
                    "Failed to create sensor instance",
                    color="negative",
                    slot=self._dialog,
                )
                return

            if not await sensor.initialize():
                await sensor.cleanup()
                notify_later(
                    "Sensor initialization failed", color="negative", slot=self._dialog
                )
                return

            reading = await sensor.read()
            await sensor.cleanup()

            if reading.status == SensorStatus.OK:
                msg = f"Connection successful: {reading.value}"
                notify_later(msg, color="positive", slot=self._dialog)
            else:
                err = reading.error_message or reading.status.value
                notify_later(f"Read failed: {err}", color="negative", slot=self._dialog)

        except Exception as e:
            error(f"Connection test error: {e}")
            notify_later(
                f"Connection test failed: {e}", color="negative", slot=self._dialog
            )

    def _create_sensor(self) -> None:
        """Create the sensor with the configured settings."""
        try:
            # Validate required fields
            if not self._wizard_data["sensor_id"]:
                ui.notify("Sensor ID is required", color="negative")
                return

            if not self._wizard_data["name"]:
                ui.notify("Sensor name is required", color="negative")
                return

            # Create sensor configuration
            sensor_config = {
                "sensor_id": self._wizard_data["sensor_id"],
                "name": self._wizard_data["name"],
                "type": self._wizard_data["type"],
                "source": self._wizard_data["source"],
                "interface": self._wizard_data["interface"],
                "enabled": self._wizard_data["enabled"],
                "show_on_dashboard": self._wizard_data["show_on_dashboard"],
            }

            # Add interface-specific configuration
            if self._wizard_data["interface"] in ["serial", "usb"]:
                sensor_config.update(
                    {
                        "port": self._wizard_data["port"],
                        "channel": self._wizard_data["channel"],
                        "poll_interval_ms": self._wizard_data["poll_interval_ms"],
                        "baudrate": self._wizard_data["baudrate"],
                        "timeout": self._wizard_data["timeout"],
                    }
                )
            elif self._wizard_data["interface"] == "modbus":
                sensor_config.update(
                    {
                        "port": self._wizard_data["port"],  # Address for modbus
                        "address": self._wizard_data["port"],
                        "unit_id": self._wizard_data.get("unit_id", 1),
                        "poll_interval_ms": self._wizard_data["poll_interval_ms"],
                    }
                )
            elif self._wizard_data["interface"] == "ethernet":
                sensor_config.update(
                    {
                        "ip_address": self._wizard_data.get("ip_address"),
                        "port": self._wizard_data.get("port", 502),
                        "poll_interval_ms": self._wizard_data["poll_interval_ms"],
                    }
                )

            # Add filter algorithms if configured
            if self._wizard_data["filters"]:
                algorithms = []
                for filter_config in self._wizard_data["filters"]:
                    algorithm_config = {
                        "algorithm_id": f"{self._wizard_data['sensor_id']}_{filter_config['id']}",
                        "name": f"{filter_config['type']} for {self._wizard_data['name']}",
                        "type": "filtering",
                        "enabled": True,
                        "settings": {
                            "class": filter_config["class"],
                            "parameters": filter_config["parameters"],
                        },
                    }

                    # Add algorithm configuration to config service
                    try:
                        self.config_service.add_algorithm_config(algorithm_config)
                        algorithms.append(algorithm_config["algorithm_id"])
                        info(
                            f"Added algorithm configuration: {algorithm_config['algorithm_id']}"
                        )
                    except Exception as e:
                        warning(f"Failed to add algorithm configuration: {e}")

                # Add algorithm references to sensor config
                if algorithms:
                    sensor_config["algorithm"] = algorithms

            # Validate and add sensor configuration
            self.config_service.validate_sensor_config(sensor_config)
            self.config_service.add_sensor_config(sensor_config)

            info(f"Created sensor configuration: {sensor_config['sensor_id']}")
            ui.notify(
                f"Sensor '{sensor_config['name']}' created successfully!",
                color="positive",
            )

            # Close dialog and notify parent
            self._close_dialog()

        except Exception as e:
            error(f"Failed to create sensor: {e}")
            ui.notify(f"Failed to create sensor: {str(e)}", color="negative")


# Legacy compatibility class - redirect to new wizard
class SetupWizardComponent(SensorSetupWizardComponent):
    """Legacy compatibility wrapper for SensorSetupWizardComponent."""

    def __init__(self, config_service, sensor_manager, controller_manager):
        super().__init__(config_service, sensor_manager)
        self.controller_manager = controller_manager  # Keep for compatibility

    def show_dialog(
        self, start_step: str = "sensors", on_close: Optional[Callable[[], None]] = None
    ) -> None:
        """Legacy compatibility method."""
        if start_step == "sensors":
            super().show_dialog()
        else:
            # For non-sensor steps, show the original simple wizard
            self._show_legacy_wizard(start_step)

    def _show_legacy_wizard(self, start_step: str) -> None:
        """Show simplified legacy wizard for non-sensor steps."""
        with ui.dialog().props("persistent") as dialog:
            self._dialog = dialog
            with ui.card().classes("w-[600px] max-w-[90vw]"):
                ui.label("Setup Wizard").classes("text-xl font-bold mb-4")
                ui.label("This wizard will be expanded in future versions.").classes(
                    "mb-4"
                )

                with ui.row().classes("gap-2 justify-end"):
                    ui.button("Close", on_click=dialog.close).props("flat")

        dialog.open()
