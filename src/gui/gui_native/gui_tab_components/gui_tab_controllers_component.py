"""
Controllers component for displaying and managing all configured controllers.
"""

from typing import Dict, Any, Optional, List, Callable
from datetime import datetime, timedelta
from dataclasses import dataclass
from nicegui import ui
import time
import asyncio

from .dialog_utils import CancelableDialogMixin

from src.utils.config_service import ConfigurationService
from src.utils.log_service import info, warning, error, debug

from src.controllers.controller_manager import ControllerManager
from src.controllers.controller_base import (
    ControllerStage,
    ControllerStatus,
    ControllerType,
)
from src.gui.gui_tab_components.gui_tab_base_component import (
    TimedComponent,
    BaseComponent,
    ComponentConfig,
    get_component_registry,
)
from src.gui.gui_elements.gui_controller_setup_wizard_element import (
    ControllerSetupWizardComponent,
)


@dataclass
class ControllerCardConfig:
    """Configuration for controller display cards"""

    controller_id: str
    name: str
    controller_type: str
    enabled: bool = True


class ControllerConfigDialog(CancelableDialogMixin):
    """Dialog for creating new controllers with webcam settings."""

    def __init__(
        self,
        config_service: ConfigurationService,
        controller_manager: ControllerManager,
        on_save_callback=None,
    ):
        self.config_service = config_service
        self.controller_manager = controller_manager
        self.on_save_callback = on_save_callback
        self._dialog: Optional[ui.dialog] = None
        self._form_data: Dict[str, Any] = {}

    def show_add_dialog(self) -> None:
        self._form_data = {
            "controller_id": self.config_service.generate_next_controller_id(),
            "name": "",
            # Default to reactor_state controller type
            "type": "reactor_state",
            "enabled": True,
            "webcam_id": self.config_service.generate_next_webcam_id(),
            "webcam_name": "",
            "device_index": 0,
            "width": 640,
            "height": 480,
            "fps": 30,
            "rotation": 0,
            "brightness": 128,
            "contrast": 32,
            "saturation": 64,
        }
        self._show_dialog("Add Controller")

    def _show_dialog(self, title: str) -> None:
        with ui.dialog().props("persistent") as dialog:
            self._dialog = dialog
            with ui.card().classes("w-96"):
                ui.label(title).classes("text-lg font-bold mb-4")

                with ui.column().classes("gap-4"):
                    ui.label("Controller Settings").classes("font-semibold")
                    ui.label(f"ID: {self._form_data['controller_id']}").classes(
                        "text-sm text-gray-500"
                    )
                    ui.input("Name", value=self._form_data["name"]).bind_value_to(
                        self._form_data, "name"
                    ).props("outlined").classes("w-full")
                    ui.select(
                        ConfigurationService.CONTROLLER_SCHEMA["properties"]["type"]["enum"],
                        value=self._form_data["type"],
                        label="Type",
                    ).bind_value_to(self._form_data, "type").props("outlined").classes(
                        "w-full"
                    )
                    ui.checkbox(
                        "Enabled", value=self._form_data["enabled"]
                    ).bind_value_to(self._form_data, "enabled")
                ui.separator()
                ui.label("Webcam Settings").classes("font-semibold")
                with ui.column().classes("gap-4"):
                    ui.input(
                        "Webcam ID", value=self._form_data["webcam_id"]
                    ).bind_value_to(self._form_data, "webcam_id").props(
                        "outlined"
                    ).classes(
                        "w-full"
                    )
                    ui.input(
                        "Webcam Name", value=self._form_data["webcam_name"]
                    ).bind_value_to(self._form_data, "webcam_name").props(
                        "outlined"
                    ).classes(
                        "w-full"
                    )
                    ui.number(
                        "Device Index", value=self._form_data["device_index"]
                    ).bind_value_to(self._form_data, "device_index").props(
                        "outlined"
                    ).classes(
                        "w-full"
                    )
                    with ui.row().classes("gap-2 w-full"):
                        ui.number(
                            "Width", value=self._form_data["width"]
                        ).bind_value_to(self._form_data, "width").props(
                            "outlined"
                        ).classes(
                            "flex-1"
                        )
                        ui.number(
                            "Height", value=self._form_data["height"]
                        ).bind_value_to(self._form_data, "height").props(
                            "outlined"
                        ).classes(
                            "flex-1"
                        )
                    ui.number("FPS", value=self._form_data["fps"]).bind_value_to(
                        self._form_data, "fps"
                    ).props("outlined").classes("w-full")
                    ui.select(
                        [0, 90, 180, 270],
                        label="Rotation",
                        value=self._form_data["rotation"],
                    ).bind_value_to(self._form_data, "rotation").props(
                        "outlined"
                    ).classes(
                        "w-full"
                    )
                    ui.label("UVC Settings").classes("font-semibold mt-2")
                    ui.number(
                        "Brightness", value=self._form_data["brightness"]
                    ).bind_value_to(self._form_data, "brightness").props(
                        "outlined"
                    ).classes(
                        "w-full"
                    )
                    ui.number(
                        "Contrast", value=self._form_data["contrast"]
                    ).bind_value_to(self._form_data, "contrast").props(
                        "outlined"
                    ).classes(
                        "w-full"
                    )
                    ui.number(
                        "Saturation", value=self._form_data["saturation"]
                    ).bind_value_to(self._form_data, "saturation").props(
                        "outlined"
                    ).classes(
                        "w-full"
                    )
                with ui.row().classes("gap-2 justify-end mt-4 w-full"):
                    ui.button("Cancel", on_click=self._cancel).props("flat")
                    ui.button("Save", on_click=self._save).props("color=primary")

        dialog.open()


    def _save(self) -> None:
        try:
            controller_id = self._form_data["controller_id"].strip()
            name = self._form_data["name"].strip() or controller_id
            webcam_id = self._form_data["webcam_id"].strip()
            webcam_config = {
                "webcam_id": webcam_id,
                "name": self._form_data["webcam_name"].strip() or webcam_id,
                "device_index": int(self._form_data["device_index"]),
                "resolution": [
                    int(self._form_data["width"]),
                    int(self._form_data["height"]),
                ],
                "fps": int(self._form_data["fps"]),
                "rotation": int(self._form_data["rotation"]),
                "uvc_settings": {
                    "brightness": float(self._form_data["brightness"]),
                    "contrast": float(self._form_data["contrast"]),
                    "saturation": float(self._form_data["saturation"]),
                },
            }

            # Avoid duplicate webcam entries by reusing existing configs
            if not self.config_service.get_webcam_config(webcam_id):
                self.config_service.add_webcam_config(webcam_config)

            controller_config = {
                "controller_id": controller_id,
                "name": name,
                "type": self._form_data["type"],
                "parameters": {"cam_id": self._form_data["webcam_id"].strip()},
                "enabled": bool(self._form_data["enabled"]),
            }

            self.config_service.add_controller_config(controller_config)

            # Register new controller immediately
            if self.controller_manager:
                new_controller = self.controller_manager.add_controller_from_config(
                    controller_config
                )
                if new_controller is None:
                    warning(f"Failed to register controller {controller_id}")
                else:
                    info(f"Registered new controller {controller_id}")

            ui.notify(f"Controller {controller_id} added", color="positive")
            if self._dialog:
                self._dialog.close()
            if self.on_save_callback:
                self.on_save_callback()
        except Exception as e:
            error(f"Error saving controller configuration: {e}")
            ui.notify(f"Error: {str(e)}", color="negative")


class ControllerCardComponent(TimedComponent):
    """Individual controller display card"""

    timer_attributes = ["_update_timer"]

    def __init__(
        self,
        config: ComponentConfig,
        controller_config: ControllerCardConfig,
        controller_manager: ControllerManager,
        config_service: ConfigurationService,
        pause_refresh: Optional[Callable] = None,
        resume_refresh: Optional[Callable] = None,
    ):
        super().__init__(config)
        self.controller_config = controller_config
        self.controller_manager = controller_manager
        self.config_service = config_service
        self._pause_refresh = pause_refresh
        self._resume_refresh = resume_refresh

        # UI elements
        self._status_icon: Optional[ui.icon] = None
        self._status_label: Optional[ui.label] = None
        self._name_label: Optional[ui.label] = None
        self._type_label: Optional[ui.label] = None
        self._stats_labels: Dict[str, ui.label] = {}
        self._start_button: Optional[ui.button] = None
        self._stop_button: Optional[ui.button] = None
        self._config_button: Optional[ui.button] = None
        self._update_timer: Optional[ui.timer] = None

        # State
        self._expanded = False

    def render(self) -> ui.card:
        """Render controller card"""
        with ui.card().classes("p-4 cvd-card min-w-96") as card:
            # Header with controller name and status
            with ui.row().classes("w-full items-center mb-3"):
                self._name_label = ui.label(self.controller_config.name).classes(
                    "text-lg font-semibold flex-grow"
                )
                self._status_icon = ui.icon("circle", size="sm").classes("ml-2")
                self._status_label = ui.label("Unknown").classes("text-sm ml-2")

            # Controller type and ID
            with ui.row().classes("w-full items-center mb-3"):
                self._type_label = ui.label(
                    f"Type: {self.controller_config.controller_type}"
                ).classes("text-sm text-gray-500")
                ui.label(f"ID: {self.controller_config.controller_id}").classes(
                    "text-xs text-gray-400 ml-auto"
                )

            # Action buttons
            with ui.row().classes("w-full gap-2 mb-3"):
                self._start_button = (
                    ui.button("Start", icon="play_arrow", color="green")
                    .props("size=sm")
                    .on("click", self._start_controller)
                )
                self._stop_button = (
                    ui.button("Stop", icon="stop", color="red")
                    .props("size=sm")
                    .on("click", self._stop_controller)
                )
                self._config_button = (
                    ui.button("Configure", icon="settings", color="blue")
                    .props("size=sm")
                    .on("click", self._show_config_dialog)
                )

                # Expand/collapse button
                ui.button("Details", icon="expand_more", color="grey").props(
                    "size=sm flat"
                ).on("click", self._toggle_details)

            # Expandable details section
            with ui.expansion("Details", icon="info").bind_visibility_from(
                self, "_expanded"
            ) as expansion:
                with expansion:
                    self._render_details()

            # Start update timer
            self._update_timer = ui.timer(1.0, self._update_display)

        return card

    def _render_details(self) -> None:
        """Render detailed controller information"""
        with ui.column().classes("w-full gap-3"):
            # Statistics section
            ui.label("Statistics").classes("text-md font-semibold")
            with ui.grid(columns=2).classes("w-full gap-2"):
                self._stats_labels["processing_time"] = ui.label(
                    "Processing Time: --"
                ).classes("text-sm")
                self._stats_labels["error_count"] = ui.label("Error Count: --").classes(
                    "text-sm"
                )
                self._stats_labels["last_success"] = ui.label(
                    "Last Success: --"
                ).classes("text-sm")
                self._stats_labels["uptime"] = ui.label("Uptime: --").classes("text-sm")

            # Configuration section
            ui.label("Configuration").classes("text-md font-semibold mt-3")
            self._render_configuration()

    def _render_configuration(self) -> None:
        """Render current configuration"""
        controller_settings = self.config_service.get_controller_settings(
            self.controller_config.controller_id
        )

        if controller_settings:
            with ui.column().classes("w-full"):
                for key, value in controller_settings.items():
                    with ui.row().classes("w-full items-center"):
                        ui.label(f"{key}:").classes("text-sm font-medium min-w-24")
                        ui.label(str(value)).classes("text-sm text-gray-600")
        else:
            ui.label("No configuration available").classes("text-sm text-gray-500")

    def _update_display(self) -> None:
        """Update controller display with latest status"""
        try:
            controller = self.controller_manager.get_controller(
                self.controller_config.controller_id
            )

            if controller:
                self._update_status(controller)
                self._update_buttons(controller)
                if self._expanded:
                    self._update_statistics(controller)
            else:
                self._show_not_registered()
        except Exception as e:
            error(
                f"Error updating controller card {self.controller_config.controller_id}: {e}"
            )

    def _update_status(self, controller: ControllerStage) -> None:
        """Update status display"""
        if not self._status_icon or not self._status_label:
            return

        status_config = {
            ControllerStatus.RUNNING: ("play_circle", "text-green-500", "Running"),
            ControllerStatus.STOPPED: ("stop_circle", "text-gray-500", "Stopped"),
            ControllerStatus.ERROR: ("error", "text-red-500", "Error"),
            ControllerStatus.PAUSED: ("pause_circle", "text-yellow-500", "Paused"),
        }

        icon, color, text = status_config.get(
            controller.status, ("help", "text-gray-400", "Unknown")
        )
        self._status_icon.name = icon
        self._status_icon.classes(replace=color)
        self._status_label.text = text

    def _update_buttons(self, controller: ControllerStage) -> None:
        """Update button states based on controller status"""
        if not self._start_button or not self._stop_button:
            return

        if controller.status == ControllerStatus.RUNNING:
            self._start_button.disable()
            self._stop_button.enable()
        elif controller.status in [ControllerStatus.STOPPED, ControllerStatus.ERROR]:
            self._start_button.enable()
            self._stop_button.disable()
        else:  # PAUSED
            self._start_button.enable()
            self._stop_button.enable()

    def _update_statistics(self, controller: ControllerStage) -> None:
        """Update statistics display"""
        if not self._stats_labels:
            return

        stats = controller.get_stats()

        # Processing time
        processing_time = stats.get("processing_time_ms", 0)
        self._stats_labels["processing_time"].text = (
            f"Processing Time: {processing_time:.2f}ms"
        )

        # Error count
        error_count = stats.get("error_count", 0)
        self._stats_labels["error_count"].text = f"Error Count: {error_count}"

        # Last success
        last_success = stats.get("last_success", None)
        if isinstance(last_success, bool):
            success_text = "Yes" if last_success else "No"
        elif last_success:
            try:
                ts = float(last_success)
                success_text = datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S")
            except Exception:
                success_text = str(last_success)
        else:
            success_text = "Unknown"

        self._stats_labels["last_success"].text = f"Last Success: {success_text}"

        start_time = stats.get("start_time")
        if start_time is not None:
            uptime_s = time.time() - start_time
            uptime_text = str(timedelta(seconds=int(uptime_s)))
        else:
            uptime_text = "--"
        self._stats_labels["uptime"].text = f"Uptime: {uptime_text}"

    def _show_not_registered(self) -> None:
        """Show state when controller is not registered"""
        if self._status_icon and self._status_label:
            self._status_icon.name = "warning"
            self._status_icon.classes(replace="text-orange-500")
            self._status_label.text = "Not Registered"

        if self._start_button and self._stop_button:
            self._start_button.disable()
            self._stop_button.disable()

    async def _start_controller(self) -> None:
        """Start the controller"""
        try:
            controller = self.controller_manager.get_controller(
                self.controller_config.controller_id
            )
            if controller:
                success = await controller.start()
                if success:
                    ui.notify(
                        f"Controller {self.controller_config.name} started",
                        type="positive",
                    )
                else:
                    ui.notify(
                        f"Failed to start controller {self.controller_config.name}",
                        type="negative",
                    )
            else:
                ui.notify(
                    f"Controller {self.controller_config.name} not found",
                    type="warning",
                )
        except Exception as e:
            error(
                f"Error starting controller {self.controller_config.controller_id}: {e}"
            )
            ui.notify(f"Error starting controller: {str(e)}", type="negative")

    async def _stop_controller(self) -> None:
        """Stop the controller"""
        try:
            controller = self.controller_manager.get_controller(
                self.controller_config.controller_id
            )
            if controller:
                await controller.stop()
                ui.notify(
                    f"Controller {self.controller_config.name} stopped", type="info"
                )
            else:
                ui.notify(
                    f"Controller {self.controller_config.name} not found",
                    type="warning",
                )
        except Exception as e:
            error(
                f"Error stopping controller {self.controller_config.controller_id}: {e}"
            )
            ui.notify(f"Error stopping controller: {str(e)}", type="negative")

    def _toggle_details(self) -> None:
        """Toggle details visibility"""
        self._expanded = not self._expanded

    def _show_config_dialog(self) -> None:
        """Show configuration dialog"""
        if self._pause_refresh:
            self._pause_refresh()
        self._create_config_dialog()

    def _create_config_dialog(self) -> None:
        """Create configuration dialog"""
        controller_settings = self.config_service.get_controller_settings(
            self.controller_config.controller_id
        )
        controller_parameters = self.config_service.get_controller_parameters(
            self.controller_config.controller_id
        )

        with ui.dialog().props("persistent") as dialog:
            # ensure resume_refresh is callable before binding
            resume = self._resume_refresh
            if resume:
                dialog.on("close", lambda _: resume())
            with ui.card().classes("w-96"):
                ui.label(f"Configure {self.controller_config.name}").classes(
                    "text-lg font-bold mb-4"
                )

                if controller_settings or controller_parameters:
                    parameter_inputs: Dict[str, Any] = {}
                    settings_inputs: Dict[str, Any] = {}

                    if controller_parameters:
                        ui.label("Parameters").classes("font-semibold")
                        with ui.column().classes("w-full gap-3"):
                            for key, value in controller_parameters.items():
                                with ui.row().classes("w-full items-center"):
                                    ui.label(f"{key}:").classes("min-w-24")
                                    options = None
                                    if key == "cam_id":
                                        options = self.config_service.get_webcam_ids()
                                    else:
                                        options = self.config_service.get_controller_enum_options(
                                            "parameters", key
                                        )

                                    if options:
                                        parameter_inputs[key] = ui.select(
                                            options, value=value
                                        )
                                    elif isinstance(value, bool):
                                        parameter_inputs[key] = ui.checkbox(
                                            "", value=value
                                        )
                                    elif isinstance(value, (int, float)):
                                        parameter_inputs[key] = ui.number(
                                            "", value=value, format="%.2f"
                                        )
                                    else:
                                        parameter_inputs[key] = ui.input(
                                            "", value=str(value)
                                        )

                    if controller_settings:
                        ui.label("Settings").classes("font-semibold mt-2")
                        with ui.column().classes("w-full gap-3"):
                            for key, value in controller_settings.items():
                                with ui.row().classes("w-full items-center"):
                                    ui.label(f"{key}:").classes("min-w-24")
                                    options = self.config_service.get_controller_enum_options(
                                        "settings", key
                                    )

                                    if options:
                                        settings_inputs[key] = ui.select(
                                            options, value=value
                                        )
                                    elif isinstance(value, bool):
                                        settings_inputs[key] = ui.checkbox(
                                            "", value=value
                                        )
                                    elif isinstance(value, (int, float)):
                                        settings_inputs[key] = ui.number(
                                            "", value=value, format="%.2f"
                                        )
                                    else:
                                        settings_inputs[key] = ui.input(
                                            "", value=str(value)
                                        )

                    with ui.row().classes("w-full justify-end gap-2 mt-4"):
                        ui.button("Cancel", color="grey").on("click", dialog.close)
                        ui.button("Save", color="primary").on(
                            "click",
                            lambda: self._save_configuration(
                                dialog, parameter_inputs, settings_inputs
                            ),
                        )
                else:
                    ui.label("No configurable settings available").classes(
                        "text-gray-500 mb-4"
                    )
                    ui.button("Close", color="grey").on("click", dialog.close)

        dialog.open()

    def _save_configuration(
        self,
        dialog,
        parameter_inputs: Dict[str, Any],
        settings_inputs: Dict[str, Any],
    ) -> None:
        """Save configuration changes"""
        try:
            param_updates: Dict[str, Any] = {}
            for key, input_element in parameter_inputs.items():
                if hasattr(input_element, "value"):
                    param_updates[key] = input_element.value

            settings_updates: Dict[str, Any] = {}
            for key, input_element in settings_inputs.items():
                if hasattr(input_element, "value"):
                    settings_updates[key] = input_element.value

            success_params = True
            if param_updates:
                success_params = self.config_service.update_controller_parameters(
                    self.controller_config.controller_id,
                    param_updates,
                )

            success_settings = True
            if settings_updates:
                success_settings = self.config_service.update_controller_settings(
                    self.controller_config.controller_id,
                    settings_updates,
                )

            if success_params and success_settings:
                ui.notify("Configuration saved successfully", type="positive")
                dialog.close()
            else:
                ui.notify("Failed to save configuration", type="negative")
        except Exception as e:
            error(f"Error saving controller configuration: {e}")
            ui.notify(f"Error saving configuration: {str(e)}", type="negative")

    def _update_element(self, data: Any) -> None:
        """Update element with new data"""
        # Data updates are handled by timer
        pass



class ControllersComponent(BaseComponent):
    """Main controllers component"""

    def __init__(
        self,
        config_service: ConfigurationService,
        controller_manager: ControllerManager,
    ):
        config = ComponentConfig("controllers")
        super().__init__(config)
        self.config_service = config_service
        self.controller_manager = controller_manager
        self._controller_cards: Dict[str, ControllerCardComponent] = {}
        self._refresh_timer: Optional[ui.timer] = None
        self._controllers_container: Optional[ui.row] = None
        self._config_dialog: Optional[ControllerConfigDialog] = None
        self._dialog_open: bool = False

    def pause_refresh_timer(self) -> None:
        """Pause the automatic refresh timer."""
        if self._refresh_timer:
            self._refresh_timer.deactivate()
        self._dialog_open = True

    def resume_refresh_timer(self) -> None:
        """Resume the automatic refresh timer."""
        if self._refresh_timer:
            self._refresh_timer.activate()
        self._dialog_open = False

    def render(self) -> ui.column:
        """Render controllers component"""
        with ui.column().classes("w-full") as controllers:
            # Header with title and controls
            with ui.row().classes("w-full justify-between items-center mb-4"):
                ui.label("Controllers").classes("text-2xl font-bold")

                with ui.row().classes("gap-2"):
                    ui.button("Add Controller", icon="add", color="primary").on("click", self._show_add_dialog)
                    ui.button("Start All", icon="play_arrow", color="green").on("click", self._start_all_controllers)
                    ui.button("Stop All", icon="stop", color="red").on("click", self._stop_all_controllers)
                    ui.button("Refresh", icon="refresh", color="blue").on("click", self._refresh_controllers)

            # System overview
            self._render_system_overview()
            # Controllers grid
            with ui.row().classes("w-full gap-4 flex-wrap") as controllers_container:
                self._controllers_container = controllers_container
                self._render_controller_cards()

            # Execution order visualization
            self._render_execution_order()

            # Start refresh timer
        self._refresh_timer = ui.timer(5.0, self._refresh_controllers)

        self._config_dialog = ControllerConfigDialog(
            self.config_service,
            self.controller_manager,
            self._on_config_saved,
        )

        return controllers

    def _render_system_overview(self) -> None:
        """Render system overview"""
        with ui.card().classes("w-full p-4 mb-4 cvd-card"):
            ui.label("System Overview").classes("text-lg font-semibold mb-3")

            stats = self.controller_manager.get_controller_stats()

            with ui.row().classes("w-full gap-6"):
                # Total controllers
                with ui.column().classes("text-center"):
                    ui.label(str(stats.get("total_controllers", 0))).classes(
                        "text-2xl font-bold text-blue-600"
                    )
                    ui.label("Total Controllers").classes("text-sm text-gray-500")

                # Running status
                running_status = "Running" if stats.get("running", False) else "Stopped"
                status_color = (
                    "text-green-600" if stats.get("running", False) else "text-red-600"
                )
                with ui.column().classes("text-center"):
                    ui.label(running_status).classes(
                        f"text-2xl font-bold {status_color}"
                    )
                    ui.label("Manager Status").classes("text-sm text-gray-500")

                # Processing stats
                processing_stats = stats.get("processing_stats", {})
                last_processing_time = processing_stats.get(
                    "total_processing_time_ms", 0
                )
                with ui.column().classes("text-center"):
                    ui.label(f"{last_processing_time:.2f}ms").classes(
                        "text-2xl font-bold text-purple-600"
                    )
                    ui.label("Last Processing Time").classes("text-sm text-gray-500")

    def _render_controller_cards(self) -> None:
        """Render controller cards"""
        # Clear existing cards
        for card in self._controller_cards.values():
            card.cleanup()
        self._controller_cards.clear()

        # Clear the DOM container to remove existing UI elements
        if self._controllers_container:
            self._controllers_container.clear()

        # Get configured controllers
        controller_configs = self.config_service.get_controller_configs()

        for controller_id, config_dict in controller_configs:
            # Create controller card config
            card_config = ControllerCardConfig(
                controller_id=controller_id,
                name=config_dict.get("name", controller_id),
                controller_type=config_dict.get("type", "unknown"),
                enabled=config_dict.get("enabled", True),
            )

            # Create component config
            component_config = ComponentConfig(f"controller_card_{controller_id}")

            # Create and render card within the container context
            if self._controllers_container:
                with self._controllers_container:
                    card_component = ControllerCardComponent(
                        component_config,
                        card_config,
                        self.controller_manager,
                        self.config_service,
                        self.pause_refresh_timer,
                        self.resume_refresh_timer,
                    )
                    card_component.render()
                    self._controller_cards[controller_id] = card_component

    def _render_execution_order(self) -> None:
        """Render execution order visualization"""
        with ui.card().classes("w-full p-4 mt-4 cvd-card"):
            ui.label("Execution Order").classes("text-lg font-semibold mb-3")

            stats = self.controller_manager.get_controller_stats()
            execution_order = stats.get("execution_order", [])
            dependencies = stats.get("dependencies", [])

            if execution_order:
                with ui.row().classes("w-full items-center gap-2 flex-wrap"):
                    for i, controller_id in enumerate(execution_order):
                        # Controller chip
                        ui.chip(controller_id, color="primary").classes("text-sm")

                        # Arrow (except for last item)
                        if i < len(execution_order) - 1:
                            ui.icon("arrow_forward").classes("text-gray-400")
            else:
                ui.label("No execution order defined").classes("text-gray-500")

            # Dependencies info
            if dependencies:
                ui.label(f"Dependencies: {len(dependencies)} total").classes(
                    "text-sm text-gray-500 mt-2"
                )

    def _show_add_dialog(self) -> None:
        """Show the controller setup wizard."""
        # Get sensor manager from the component registry
        registry = get_component_registry()
        sensors_component = registry.get_component("sensors_component")
        sensor_manager = getattr(sensors_component, "sensor_manager", None)

        if sensor_manager is None:
            # Fallback to old dialog if sensor manager is not available
            if self._config_dialog:
                self._config_dialog.show_add_dialog()
            return

        # Use the new controller setup wizard
        def _on_close() -> None:
            self._refresh_controllers()

            registry = get_component_registry()
            dashboard = registry.get_component("dashboard")
            if dashboard and hasattr(dashboard, "refresh_controllers"):
                dashboard.refresh_controllers()

        wizard = ControllerSetupWizardComponent(
            config_service=self.config_service,
            controller_manager=self.controller_manager,
            sensor_manager=sensor_manager,
            on_close=_on_close,
        )
        wizard.show_dialog()

    async def _start_all_controllers(self) -> None:
        """Start all controllers"""
        try:
            success = await self.controller_manager.start_all_controllers()
            if success:
                ui.notify("All controllers started successfully", type="positive")
            else:
                ui.notify("Some controllers failed to start", type="warning")
        except Exception as e:
            error(f"Error starting all controllers: {e}")
            ui.notify(f"Error starting controllers: {str(e)}", type="negative")

    async def _stop_all_controllers(self) -> None:
        """Stop all controllers"""
        try:
            await self.controller_manager.stop_all_controllers()
            ui.notify("All controllers stopped", type="info")
        except Exception as e:
            error(f"Error stopping all controllers: {e}")
            ui.notify(f"Error stopping controllers: {str(e)}", type="negative")

    def _refresh_controllers(self) -> None:
        """Refresh controller display"""
        if self._dialog_open:
            debug("Refresh skipped because configuration dialog is open")
            return
        try:
            # Re-render controller cards to pick up any new configurations
            self._render_controller_cards()
            debug("Refreshed controllers display")
        except Exception as e:
            error(f"Error refreshing controllers: {e}")

    def _on_config_saved(self) -> None:
        """Refresh controllers list and update dashboard."""
        self._refresh_controllers()

        registry = get_component_registry()
        dashboard = registry.get_component("dashboard")
        if dashboard and hasattr(dashboard, "refresh_controllers"):
            dashboard.refresh_controllers()

    def _update_element(self, data: Any) -> None:
        """Update element with new data"""
        # Updates are handled by individual cards and timers
        pass

    def cleanup(self) -> None:
        """Cleanup component"""
        if self._refresh_timer:
            self._refresh_timer.cancel()

        for card in self._controller_cards.values():
            card.cleanup()
        self._controller_cards.clear()

        super().cleanup()
