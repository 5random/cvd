"""
Experiment management component for the CVD Tracker application.
Provides comprehensive experiment configuration, monitoring, and control capabilities.
"""

import asyncio
import json
from datetime import datetime, timedelta, date
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass
from pathlib import Path

from nicegui import ui
from nicegui.element import Element
from src.utils.ui_helpers import notify_later
from nicegui.elements.dialog import Dialog
from nicegui.elements.label import Label
from nicegui.elements.button import Button
from nicegui.elements.icon import Icon
from nicegui.elements.card import Card

from src.gui.gui_tab_components.gui_tab_base_component import (
    BaseComponent,
    ComponentConfig,
)
from .dialog_utils import CancelableDialogMixin
from src.experiment_handler.experiment_manager import (
    ExperimentManager,
    ExperimentConfig,
    ExperimentResult,
    ExperimentState,
    ExperimentPhase,
    ExperimentDataPoint,
    get_experiment_manager,
    set_experiment_manager,
)
from src.data_handler.sources.sensor_source_manager import SensorManager
from src.controllers.controller_manager import ControllerManager
from src.utils.config_utils.config_service import (
    ConfigurationService,
    get_config_service,
)
from src.utils.log_utils.log_service import info, warning, error, debug
from src.gui.gui_elements.gui_experiment_setup_wizard_element import (
    ExperimentSetupWizardComponent,
)
from typing import cast


@dataclass
class ExperimentInfo:
    """Data class for experiment display information"""

    experiment_id: str
    name: str
    description: str
    state: ExperimentState
    phase: ExperimentPhase
    start_time: Optional[datetime]
    end_time: Optional[datetime]
    duration_seconds: Optional[float]
    data_points_collected: int
    sensor_count: int
    controller_count: int
    errors_count: int
    progress_percent: float
    estimated_remaining: Optional[str]


class ExperimentConfigDialog(CancelableDialogMixin):
    """Dialog for experiment configuration"""

    def __init__(
        self,
        config_service: ConfigurationService,
        experiment_manager: ExperimentManager,
        sensor_manager: Optional[SensorManager] = None,
        controller_manager: Optional[ControllerManager] = None,
        on_save_callback=None,
    ):
        self.config_service = config_service
        self.experiment_manager = experiment_manager
        self.sensor_manager = sensor_manager
        self.controller_manager = controller_manager
        self.on_save_callback = on_save_callback
        self._dialog: Optional[Dialog] = None
        self._form_data: Dict[str, Any] = {}
        self._available_sensors: List[str] = []
        self._available_controllers: List[str] = []

    def show_dialog(self) -> None:
        """Show dialog for creating new experiment"""
        self._load_available_sources()
        self._form_data = {
            "name": "",
            "description": "",
            "duration_minutes": None,
            "duration_enabled": False,
            "auto_start_sensors": True,
            "auto_start_controllers": True,
            "sensor_ids": [],
            "controller_ids": [],
            "data_collection_interval_ms": 1000,
            "auto_compress": True,
            "custom_parameters": {},
        }
        self._show_dialog("Create New Experiment")

    def _load_available_sources(self) -> None:
        """Load available sensors and controllers"""
        # Load sensors
        if self.sensor_manager:
            try:
                sensor_configs = self.config_service.get_sensor_configs()
                self._available_sensors = [config[0] for config in sensor_configs]
            except Exception as e:
                warning(f"Failed to load sensor configs: {e}")
                self._available_sensors = []

        # Load controllers
        if self.controller_manager:
            try:
                controllers = self.controller_manager.list_controllers()
                self._available_controllers = list(controllers)
            except Exception as e:
                warning(f"Failed to load controller ids: {e}")
                self._available_controllers = []
        else:
            self._available_controllers = []

    def _show_dialog(self, title: str) -> None:
        """Show the configuration dialog"""
        with ui.dialog().props("persistent") as dialog:
            self._dialog = dialog
            with ui.card().classes("w-[600px] max-w-[90vw]"):
                ui.label(title).classes("text-xl font-bold mb-4")

                with ui.column().classes("gap-4"):
                    # Basic Information
                    ui.label("Basic Information").classes("font-semibold text-lg")

                    ui.input(
                        "Experiment Name",
                        value=self._form_data["name"],
                        placeholder="Enter a descriptive name for your experiment",
                    ).bind_value_to(self._form_data, "name").props("outlined").classes(
                        "w-full"
                    )

                    ui.textarea(
                        "Description",
                        value=self._form_data["description"],
                        placeholder="Optional description of the experiment purpose and goals",
                    ).bind_value_to(self._form_data, "description").props(
                        "outlined"
                    ).classes(
                        "w-full"
                    )

                    # Duration Settings
                    ui.separator()
                    ui.label("Duration Settings").classes("font-semibold text-lg")

                    duration_checkbox = ui.checkbox(
                        "Set maximum duration",
                        value=self._form_data["duration_enabled"],
                    ).bind_value_to(self._form_data, "duration_enabled")

                    duration_input = (
                        ui.number(
                            "Duration (minutes)",
                            value=self._form_data["duration_minutes"],
                            min=1,
                            max=43200,
                            step=1,  # Up to 30 days
                            placeholder="Leave empty for unlimited duration",
                        )
                        .bind_value_to(self._form_data, "duration_minutes")
                        .props("outlined")
                        .classes("w-full")
                    )

                    # Bind duration input visibility to checkbox
                    duration_input.bind_visibility_from(
                        self._form_data, "duration_enabled"
                    )

                    # Data Collection Settings
                    ui.separator()
                    ui.label("Data Collection Settings").classes(
                        "font-semibold text-lg"
                    )

                    ui.number(
                        "Collection Interval (ms)",
                        value=self._form_data["data_collection_interval_ms"],
                        min=100,
                        max=60000,
                        step=100,
                    ).bind_value_to(
                        self._form_data, "data_collection_interval_ms"
                    ).props(
                        "outlined"
                    ).classes(
                        "w-full"
                    )

                    ui.checkbox(
                        "Auto-compress results", value=self._form_data["auto_compress"]
                    ).bind_value_to(self._form_data, "auto_compress")

                    # Sensor Configuration
                    ui.separator()
                    ui.label("Sensor Configuration").classes("font-semibold text-lg")

                    ui.checkbox(
                        "Auto-start sensors",
                        value=self._form_data["auto_start_sensors"],
                    ).bind_value_to(self._form_data, "auto_start_sensors")

                    if self._available_sensors:
                        sensor_select = (
                            ui.select(
                                self._available_sensors,
                                multiple=True,
                                value=self._form_data["sensor_ids"],
                                label="Select specific sensors (empty = all sensors)",
                            )
                            .bind_value_to(self._form_data, "sensor_ids")
                            .props("outlined use-chips")
                            .classes("w-full")
                        )
                    else:
                        ui.label("No sensors configured").classes("text-orange-600")

                    # Controller Configuration
                    ui.separator()
                    ui.label("Controller Configuration").classes(
                        "font-semibold text-lg"
                    )

                    ui.checkbox(
                        "Auto-start controllers",
                        value=self._form_data["auto_start_controllers"],
                    ).bind_value_to(self._form_data, "auto_start_controllers")

                    if self._available_controllers:
                        controller_select = (
                            ui.select(
                                self._available_controllers,
                                multiple=True,
                                value=self._form_data["controller_ids"],
                                label="Select specific controllers (empty = all controllers)",
                            )
                            .bind_value_to(self._form_data, "controller_ids")
                            .props("outlined use-chips")
                            .classes("w-full")
                        )
                    else:
                        ui.label("No controllers configured").classes("text-gray-500")

                    # Buttons
                    with ui.row().classes("gap-2 justify-end w-full mt-6"):
                        ui.button("Cancel", on_click=self._cancel).props("flat")
                        ui.button(
                            "Create & Start", on_click=self._create_and_start
                        ).props("color=positive")
                        ui.button("Create Only", on_click=self._create_only).props(
                            "color=primary"
                        )

        dialog.open()

    def _create_only(self) -> None:
        """Create experiment without starting"""
        self._save_experiment(start_immediately=False)

    def _create_and_start(self) -> None:
        """Create and immediately start experiment"""
        self._save_experiment(start_immediately=True)

    def _save_experiment(self, start_immediately: bool = False) -> None:
        """Save experiment configuration"""
        try:
            # Validate required fields
            if not self._form_data["name"].strip():
                ui.notify("Experiment name is required", color="negative")
                return

            # Create configuration
            duration_minutes = None
            if (
                self._form_data["duration_enabled"]
                and self._form_data["duration_minutes"]
            ):
                duration_minutes = int(self._form_data["duration_minutes"])
            # instantiate ExperimentConfig (positionally) and ignore type checker for named params
            experiment_config = ExperimentConfig(  # type: ignore
                self._form_data["name"].strip(),
                self._form_data["description"].strip(),
                duration_minutes,
                bool(self._form_data["auto_start_sensors"]),
                bool(self._form_data["auto_start_controllers"]),
                list(self._form_data["sensor_ids"]),
                list(self._form_data["controller_ids"]),
                int(self._form_data["data_collection_interval_ms"]),
                bool(self._form_data["auto_compress"]),
            )

            # Create experiment
            experiment_id = self.experiment_manager.create_experiment(experiment_config)

            if start_immediately:
                # Start experiment asynchronously
                asyncio.create_task(self._start_experiment_async(experiment_id))
                ui.notify(
                    f'Experiment "{experiment_config.name}" created and starting...',
                    color="positive",
                )
            else:
                ui.notify(
                    f'Experiment "{experiment_config.name}" created successfully',
                    color="positive",
                )

            if self._dialog:
                self._dialog.close()

            if self.on_save_callback:
                self.on_save_callback()

        except Exception as e:
            error(f"Error creating experiment: {e}")
            ui.notify(f"Error: {str(e)}", color="negative")

    async def _start_experiment_async(self, experiment_id: str) -> None:
        """Start experiment asynchronously"""
        # Helper to schedule notifications in main UI context
        try:
            success = await self.experiment_manager.start_experiment(experiment_id)
            if success:
                notify_later("Experiment started successfully", color="positive")
            else:
                notify_later("Failed to start experiment", color="negative")
        except Exception as e:
            error(f"Error starting experiment: {e}")
            notify_later(f"Error starting experiment: {str(e)}", color="negative")


class ExperimentCard(BaseComponent):
    """Card component for displaying experiment information"""

    def __init__(
        self,
        experiment_info: ExperimentInfo,
        experiment_manager: ExperimentManager,
        on_action_callback=None,
    ):
        config = ComponentConfig(
            component_id=f"experiment_card_{experiment_info.experiment_id}",
            title=f"Experiment Card - {experiment_info.experiment_id}",
        )
        super().__init__(config)

        self.experiment_info = experiment_info
        self.experiment_manager = experiment_manager
        self.on_action_callback = on_action_callback

        # UI elements
        self._container: Optional[Card] = None
        self._status_icon: Optional[Icon] = None
        self._progress_bar: Any = None
        self._progress_label: Any = None
        self._state_label: Optional[Label] = None
        self._action_buttons: List[Button] = []

    def render(self) -> Element:
        """Render experiment card"""
        with ui.card().classes("w-full") as card:
            self._container = card

            with ui.card_section():
                # Header with name and status
                with ui.row().classes("items-center justify-between w-full"):
                    with ui.column().classes("gap-1 flex-1"):
                        ui.label(self.experiment_info.name).classes("text-lg font-bold")
                        ui.label(self.experiment_info.experiment_id).classes(
                            "text-sm text-gray-500"
                        )
                        if self.experiment_info.description:
                            ui.label(self.experiment_info.description).classes(
                                "text-sm text-gray-600 mt-1"
                            )

                    with ui.column().classes("items-end gap-1"):
                        # Status icon and label
                        with ui.row().classes("items-center gap-2"):
                            self._status_icon = ui.icon("help", size="sm").classes(
                                "text-gray-400"
                            )
                            self._state_label = ui.label(
                                self.experiment_info.state.value.upper()
                            ).classes("text-sm font-semibold")

                # Progress bar for running experiments
                if (
                    self.experiment_info.state == ExperimentState.RUNNING
                    and self.experiment_info.progress_percent > 0
                ):
                    self._progress_bar = ui.linear_progress(
                        value=self.experiment_info.progress_percent / 100
                    ).classes("w-full mt-2")
                    self._progress_label = ui.label(
                        f"Progress: {self.experiment_info.progress_percent:.1f}%"
                    ).classes("text-xs text-gray-600 mt-1")

                # Statistics row
                with ui.row().classes("items-center gap-6 w-full mt-3"):
                    with ui.column().classes("gap-1"):
                        ui.label("Data Points").classes("text-xs text-gray-600")
                        ui.label(
                            str(self.experiment_info.data_points_collected)
                        ).classes("text-sm font-mono")

                    with ui.column().classes("gap-1"):
                        ui.label("Duration").classes("text-xs text-gray-600")
                        duration_text = self._format_duration(
                            self.experiment_info.duration_seconds
                        )
                        ui.label(duration_text).classes("text-sm font-mono")

                    with ui.column().classes("gap-1"):
                        ui.label("Sensors").classes("text-xs text-gray-600")
                        ui.label(str(self.experiment_info.sensor_count)).classes(
                            "text-sm font-mono"
                        )

                    if self.experiment_info.errors_count > 0:
                        with ui.column().classes("gap-1"):
                            ui.label("Errors").classes("text-xs text-red-600")
                            ui.label(str(self.experiment_info.errors_count)).classes(
                                "text-sm font-mono text-red-600"
                            )

                # Action buttons
                with ui.row().classes("gap-2 justify-end w-full mt-4"):
                    self._render_action_buttons()

        self._update_display()
        return card

    def _render_action_buttons(self) -> None:
        """Render action buttons based on experiment state"""
        self._action_buttons.clear()

        state = self.experiment_info.state

        if state == ExperimentState.IDLE:
            start_btn = ui.button(
                "Start", icon="play_arrow", on_click=self._start_experiment
            ).props("size=sm color=positive")
            self._action_buttons.append(start_btn)

        elif state == ExperimentState.RUNNING:
            pause_btn = ui.button(
                "Pause", icon="pause", on_click=self._pause_experiment
            ).props("size=sm color=warning")
            stop_btn = ui.button(
                "Stop", icon="stop", on_click=self._stop_experiment
            ).props("size=sm color=negative")
            self._action_buttons.extend([pause_btn, stop_btn])

        elif state == ExperimentState.PAUSED:
            resume_btn = ui.button(
                "Resume", icon="play_arrow", on_click=self._resume_experiment
            ).props("size=sm color=positive")
            stop_btn = ui.button(
                "Stop", icon="stop", on_click=self._stop_experiment
            ).props("size=sm color=negative")
            self._action_buttons.extend([resume_btn, stop_btn])

        elif state in [
            ExperimentState.COMPLETED,
            ExperimentState.FAILED,
            ExperimentState.CANCELLED,
        ]:
            view_btn = ui.button(
                "View Results", icon="assessment", on_click=self._view_results
            ).props("size=sm")
            self._action_buttons.append(view_btn)

        # Cancel button for states that allow it
        if state in [
            ExperimentState.CONFIGURING,
            ExperimentState.STARTING,
            ExperimentState.RUNNING,
            ExperimentState.PAUSED,
        ]:
            cancel_btn = ui.button(
                "Cancel", icon="cancel", on_click=self._cancel_experiment
            ).props("size=sm flat")
            self._action_buttons.append(cancel_btn)

    def _update_display(self) -> None:
        """Update display elements"""
        if not self._container:
            return

        # Update status icon
        self._update_status_icon()

        # Update state label
        if self._state_label:
            self._state_label.set_text(self.experiment_info.state.value.upper())
            color_class = self._get_state_color_class(self.experiment_info.state)
            self._state_label.classes(replace=f"text-sm font-semibold {color_class}")

        # Update progress bar and label
        show_progress = (
            self.experiment_info.state == ExperimentState.RUNNING
            and self.experiment_info.progress_percent > 0
        )

        if show_progress:
            if not self._progress_bar:
                with self._container:
                    with ui.card_section():
                        self._progress_bar = ui.linear_progress(
                            value=self.experiment_info.progress_percent / 100
                        ).classes("w-full mt-2")
                        self._progress_label = ui.label(
                            f"Progress: {self.experiment_info.progress_percent:.1f}%"
                        ).classes("text-xs text-gray-600 mt-1")
            else:
                self._progress_bar.visible = True
                self._progress_bar.value = self.experiment_info.progress_percent / 100
                if self._progress_label:
                    self._progress_label.visible = True
                    self._progress_label.text = (
                        f"Progress: {self.experiment_info.progress_percent:.1f}%"
                    )
        else:
            if self._progress_bar:
                self._progress_bar.visible = False
            if self._progress_label:
                self._progress_label.visible = False

    def _update_status_icon(self) -> None:
        """Update status icon based on experiment state"""
        if not self._status_icon:
            return

        state_config = {
            ExperimentState.IDLE: ("radio_button_unchecked", "text-gray-400"),
            ExperimentState.CONFIGURING: ("settings", "text-blue-500"),
            ExperimentState.STARTING: ("play_circle_outline", "text-yellow-500"),
            ExperimentState.RUNNING: ("play_circle_filled", "text-green-500"),
            ExperimentState.PAUSED: ("pause_circle_filled", "text-orange-500"),
            ExperimentState.STOPPING: ("stop_circle", "text-red-500"),
            ExperimentState.COMPLETED: ("check_circle", "text-green-600"),
            ExperimentState.FAILED: ("error", "text-red-600"),
            ExperimentState.CANCELLED: ("cancel", "text-gray-600"),
        }

        icon, color = state_config.get(
            self.experiment_info.state, ("help", "text-gray-400")
        )
        self._status_icon.props(f"name={icon}")
        self._status_icon.classes(replace=color)

    def _get_state_color_class(self, state: ExperimentState) -> str:
        """Get CSS color class for experiment state"""
        color_map = {
            ExperimentState.IDLE: "text-gray-600",
            ExperimentState.CONFIGURING: "text-blue-600",
            ExperimentState.STARTING: "text-yellow-600",
            ExperimentState.RUNNING: "text-green-600",
            ExperimentState.PAUSED: "text-orange-600",
            ExperimentState.STOPPING: "text-red-600",
            ExperimentState.COMPLETED: "text-green-700",
            ExperimentState.FAILED: "text-red-700",
            ExperimentState.CANCELLED: "text-gray-700",
        }
        return color_map.get(state, "text-gray-600")

    def _format_duration(self, duration_seconds: Optional[float]) -> str:
        """Format duration in human-readable format"""
        if duration_seconds is None:
            return "--"

        if duration_seconds < 60:
            return f"{duration_seconds:.0f}s"
        elif duration_seconds < 3600:
            minutes = duration_seconds / 60
            return f"{minutes:.1f}m"
        else:
            hours = duration_seconds / 3600
            minutes = (duration_seconds % 3600) / 60
            return f"{hours:.0f}h {minutes:.0f}m"

    async def _start_experiment(self) -> None:
        """Start the experiment"""
        try:
            success = await self.experiment_manager.start_experiment(
                self.experiment_info.experiment_id
            )
            if success:
                ui.notify(
                    f"Started experiment: {self.experiment_info.name}", color="positive"
                )
            else:
                ui.notify("Failed to start experiment", color="negative")
        except Exception as e:
            error(f"Error starting experiment: {e}")
            ui.notify(f"Error: {str(e)}", color="negative")
        finally:
            if self.on_action_callback:
                self.on_action_callback()

    async def _stop_experiment(self) -> None:
        """Stop the experiment"""
        try:
            success = await self.experiment_manager.stop_experiment()
            if success:
                ui.notify(
                    f"Stopped experiment: {self.experiment_info.name}", color="info"
                )
            else:
                ui.notify("Failed to stop experiment", color="negative")
        except Exception as e:
            error(f"Error stopping experiment: {e}")
            ui.notify(f"Error: {str(e)}", color="negative")
        finally:
            if self.on_action_callback:
                self.on_action_callback()

    async def _pause_experiment(self) -> None:
        """Pause the experiment"""
        try:
            success = await self.experiment_manager.pause_experiment()
            if success:
                ui.notify(
                    f"Paused experiment: {self.experiment_info.name}", color="warning"
                )
            else:
                ui.notify("Failed to pause experiment", color="negative")
        except Exception as e:
            error(f"Error pausing experiment: {e}")
            ui.notify(f"Error: {str(e)}", color="negative")
        finally:
            if self.on_action_callback:
                self.on_action_callback()

    async def _resume_experiment(self) -> None:
        """Resume the experiment"""
        try:
            success = await self.experiment_manager.resume_experiment()
            if success:
                ui.notify(
                    f"Resumed experiment: {self.experiment_info.name}", color="positive"
                )
            else:
                ui.notify("Failed to resume experiment", color="negative")
        except Exception as e:
            error(f"Error resuming experiment: {e}")
            ui.notify(f"Error: {str(e)}", color="negative")
        finally:
            if self.on_action_callback:
                self.on_action_callback()

    async def _cancel_experiment(self) -> None:
        """Cancel the experiment"""
        # Show confirmation dialog
        with ui.dialog() as dialog:
            with ui.card():
                ui.label(f"Cancel Experiment: {self.experiment_info.name}").classes(
                    "text-lg font-bold"
                )
                ui.label(
                    "Are you sure you want to cancel this experiment? Unsaved progress will be lost."
                ).classes("mt-2")

                with ui.row().classes("gap-2 justify-end mt-4"):
                    ui.button("No", on_click=dialog.close).props("flat")

                    async def _on_cancel_confirm():
                        try:
                            success = await self.experiment_manager.cancel_experiment()
                            if success:
                                ui.notify(
                                    f"Cancelled experiment: {self.experiment_info.name}",
                                    color="warning",
                                )
                            else:
                                ui.notify(
                                    "Failed to cancel experiment", color="negative"
                                )
                        except Exception as e:
                            error(f"Error cancelling experiment: {e}")
                            ui.notify(f"Error: {str(e)}", color="negative")
                        finally:
                            dialog.close()
                            if self.on_action_callback:
                                self.on_action_callback()

                    ui.button("Yes, Cancel", on_click=_on_cancel_confirm).props(
                        "color=negative"
                    )

        dialog.open()

    def _view_results(self) -> None:
        """View experiment results"""
        try:
            result = self.experiment_manager.get_experiment_result(
                self.experiment_info.experiment_id
            )

            if not result:
                ui.notify("No results available", color="warning")
                return

            metadata: Dict[str, Any] = {}
            if result.result_directory:
                meta_path = result.result_directory / "experiment_metadata.json"
                if meta_path.exists():
                    try:
                        with open(meta_path, "r", encoding="utf-8") as f:
                            metadata = json.load(f)
                    except Exception as e:  # pragma: no cover - best effort
                        warning(f"Failed to read metadata: {e}")

            raw_files: List[str] = []
            proc_files: List[str] = []
            if result.raw_data_dir and result.raw_data_dir.exists():
                raw_files = [
                    p.name for p in result.raw_data_dir.iterdir() if p.is_file()
                ]
            if result.processed_data_dir and result.processed_data_dir.exists():
                proc_files = [
                    p.name for p in result.processed_data_dir.iterdir() if p.is_file()
                ]

            with ui.dialog() as dialog:
                with ui.card().classes("w-[600px] max-w-[95vw]"):
                    ui.label(f"Results: {result.name}").classes(
                        "text-lg font-bold mb-2"
                    )

                    with ui.column().classes("gap-1"):
                        ui.label(f"Experiment ID: {result.experiment_id}").classes(
                            "text-sm"
                        )
                        ui.label(f"State: {result.state.value}").classes("text-sm")
                        if result.start_time:
                            ui.label(
                                "Start: "
                                + result.start_time.strftime("%Y-%m-%d %H:%M:%S")
                            ).classes("text-sm")
                        if result.end_time:
                            ui.label(
                                "End: " + result.end_time.strftime("%Y-%m-%d %H:%M:%S")
                            ).classes("text-sm")
                        if result.duration_seconds:
                            ui.label(
                                "Duration: "
                                + self._format_duration(result.duration_seconds)
                            ).classes("text-sm")
                        ui.label(
                            f"Data Points: {result.data_points_collected}"
                        ).classes("text-sm")
                        if result.errors_count:
                            ui.label(f"Errors: {result.errors_count}").classes(
                                "text-sm text-red-600"
                            )

                    if metadata:
                        ui.separator()
                        ui.label("Metadata").classes("font-semibold")
                        with ui.column().classes("gap-1 max-h-40 overflow-y-auto"):
                            for key, value in metadata.items():
                                if isinstance(value, (dict, list)):
                                    continue
                                ui.label(f"{key}: {value}").classes(
                                    "text-sm text-gray-700"
                                )

                    if raw_files or proc_files:
                        ui.separator()
                        ui.label("Stored Files").classes("font-semibold")
                        with ui.column().classes("gap-1 max-h-40 overflow-y-auto"):
                            for fname in raw_files:
                                ui.label(fname).classes("text-sm text-gray-600")
                            for fname in proc_files:
                                ui.label(fname).classes("text-sm text-gray-600")

                    ui.button("Close", on_click=dialog.close).classes("self-end mt-4")

            dialog.open()
        except Exception as e:
            error(f"Error viewing results: {e}")
            ui.notify(f"Error viewing results: {e}", color="negative")

    def update_experiment_info(self, experiment_info: ExperimentInfo) -> None:
        """Update experiment information and refresh display"""
        self.experiment_info = experiment_info
        self._update_display()

        # Re-render action buttons if state changed
        if self._container:
            # Clear existing buttons
            for btn in self._action_buttons:
                btn.delete()
            self._action_buttons.clear()

            # Re-render buttons
            with self._container:
                with ui.card_section():
                    with ui.row().classes("gap-2 justify-end w-full mt-4"):
                        self._render_action_buttons()

    def _update_element(self, data: Any) -> None:
        """Update element with new data (required by BaseComponent)"""
        # Data updates are handled by update_experiment_info
        pass


class CurrentExperimentDisplay(BaseComponent):
    """Display component for the currently active experiment"""

    def __init__(self, experiment_manager: ExperimentManager):
        config = ComponentConfig(
            component_id="current_experiment_display",
            title="Current Experiment Display",
        )
        super().__init__(config)

        self.experiment_manager = experiment_manager
        self._container: Optional[Element] = None
        self._current_experiment_card: Optional[ExperimentCard] = None
        self._refresh_timer: Optional[ui.timer] = None

    def render(self) -> Element:
        """Render current experiment display"""
        with ui.column().classes("w-full gap-4") as container:
            self._container = container

            ui.label("Current Experiment").classes("text-xl font-bold")

            # Container for current experiment card
            with ui.column().classes("w-full") as card_container:
                self._card_container = card_container
                self._render_current_experiment()

            # Start auto-refresh timer
            self._refresh_timer = ui.timer(2.0, self._refresh_current_experiment)

        return container

    def _render_current_experiment(self) -> None:
        """Render the current experiment card or empty state"""
        # Clear existing content
        if self._current_experiment_card:
            self._current_experiment_card.cleanup()
            self._current_experiment_card = None

        self._card_container.clear()

        current_experiment_id = self.experiment_manager.get_current_experiment()

        if current_experiment_id:
            # Get experiment info
            experiment_info = self._get_experiment_info(current_experiment_id)
            if experiment_info:
                # Create and render experiment card
                self._current_experiment_card = ExperimentCard(
                    experiment_info=experiment_info,
                    experiment_manager=self.experiment_manager,
                    on_action_callback=self._on_experiment_action,
                )

                with self._card_container:
                    self._current_experiment_card.render()
            else:
                with self._card_container:
                    ui.label("Failed to load experiment information").classes(
                        "text-red-600"
                    )
        else:
            # No current experiment
            with self._card_container:
                with ui.card().classes("w-full border-2 border-dashed border-gray-300"):
                    with ui.card_section().classes("text-center py-8"):
                        ui.icon("science", size="3rem").classes("text-gray-400 mb-4")
                        ui.label("No experiment currently running").classes(
                            "text-lg text-gray-600"
                        )
                        ui.label(
                            "Create and start an experiment to begin data collection"
                        ).classes("text-sm text-gray-500 mt-2")

    def _get_experiment_info(self, experiment_id: str) -> Optional[ExperimentInfo]:
        """Get experiment information from manager"""
        try:
            config = self.experiment_manager.get_experiment_config(experiment_id)
            result = self.experiment_manager.get_experiment_result(experiment_id)

            if not config or not result:
                return None

            # Calculate progress for timed experiments
            progress_percent = 0.0
            estimated_remaining = None

            if config.duration_minutes and result.start_time:
                elapsed = (datetime.now() - result.start_time).total_seconds()
                total_duration = config.duration_minutes * 60
                progress_percent = min((elapsed / total_duration) * 100, 100.0)

                if progress_percent < 100:
                    remaining_seconds = total_duration - elapsed
                    estimated_remaining = self._format_duration(remaining_seconds)

            # Determine sensor count
            if config.sensor_ids:
                sensor_count = len(config.sensor_ids)
            elif self.experiment_manager.sensor_manager:
                try:
                    sensor_count = len(
                        self.experiment_manager.sensor_manager.get_all_sensors()
                    )
                except Exception:
                    sensor_count = 0
            else:
                sensor_count = 0

            # Determine controller count
            if config.controller_ids:
                controller_count = len(config.controller_ids)
            elif self.experiment_manager.controller_manager:
                try:
                    controller_count = len(
                        self.experiment_manager.controller_manager.list_controllers()
                    )
                except Exception:
                    controller_count = 0
            else:
                controller_count = 0

            return ExperimentInfo(
                experiment_id=experiment_id,
                name=config.name,
                description=config.description,
                state=self.experiment_manager.get_current_state(),
                phase=self.experiment_manager.get_current_phase(),
                start_time=result.start_time,
                end_time=result.end_time,
                duration_seconds=result.duration_seconds,
                data_points_collected=result.data_points_collected,
                sensor_count=sensor_count,
                controller_count=controller_count,
                errors_count=result.errors_count,
                progress_percent=progress_percent,
                estimated_remaining=estimated_remaining,
            )

        except Exception as e:
            error(f"Error getting experiment info: {e}")
            return None

    def _format_duration(self, seconds: float) -> str:
        """Format duration in human-readable format"""
        if seconds < 60:
            return f"{seconds:.0f}s"
        elif seconds < 3600:
            minutes = seconds / 60
            return f"{minutes:.0f}m {seconds % 60:.0f}s"
        else:
            hours = seconds / 3600
            minutes = (seconds % 3600) / 60
            return f"{hours:.0f}h {minutes:.0f}m"

    def _refresh_current_experiment(self) -> None:
        """Refresh current experiment display"""
        try:
            current_experiment_id = self.experiment_manager.get_current_experiment()

            if current_experiment_id and self._current_experiment_card:
                # Update existing card
                experiment_info = self._get_experiment_info(current_experiment_id)
                if experiment_info:
                    self._current_experiment_card.update_experiment_info(
                        experiment_info
                    )
            else:
                # Re-render if experiment changed
                self._render_current_experiment()

        except Exception as e:
            warning(f"Error refreshing current experiment display: {e}")

    def _on_experiment_action(self) -> None:
        """Handle experiment action callback"""
        # Refresh display after action
        self._render_current_experiment()

    def cleanup(self) -> None:
        """Cleanup component resources"""
        if self._refresh_timer:
            self._refresh_timer.cancel()

        if self._current_experiment_card:
            self._current_experiment_card.cleanup()

        super().cleanup()

    def _update_element(self, data: Any) -> None:
        """Update element with new data (required by BaseComponent)"""
        self._refresh_current_experiment()


class ExperimentHistoryTable(BaseComponent):
    """Table component for displaying experiment history"""

    def __init__(self, experiment_manager: ExperimentManager):
        config = ComponentConfig(
            component_id="experiment_history_table", title="Experiment History Table"
        )
        super().__init__(config)

        self.experiment_manager = experiment_manager
        self._table: Optional[ui.table] = None

        # Filter state
        self._name_filter = ""
        self._state_filter: Optional[ExperimentState] = None
        self._from_date: Optional[date] = None
        self._to_date: Optional[date] = None

        # Filter inputs
        self._name_input = None
        self._state_select = None
        self._date_range_input = None
        self._date_dialog = None
        self._date_from_picker = None
        self._date_to_picker = None

    def render(self) -> Element:
        """Render experiment history table"""
        with ui.column().classes("w-full gap-4") as container:
            ui.label("Experiment History").classes("text-xl font-bold")

            # Filters
            with ui.row().classes("gap-4 items-end"):
                self._name_input = ui.input(
                    label="Name contains",
                    on_change=lambda e: self._on_name_filter_change(e.value),
                ).classes("w-40")

                state_options = ["All"] + [s.value.title() for s in ExperimentState]
                self._state_select = ui.select(
                    options=state_options,
                    value="All",
                    on_change=lambda e: self._on_state_filter_change(e.value),
                ).classes("w-32")

                with ui.column().classes("w-48"):
                    ui.label("Date Range").classes("text-sm")
                    self._date_range_input = (
                        ui.input(placeholder="Select range")
                        .props("readonly")
                        .on("click", self._open_date_dialog)
                    )

                ui.button("Clear", on_click=self._clear_filters).props("flat")

            # Create table
            columns = [
                {
                    "name": "name",
                    "label": "Name",
                    "field": "name",
                    "align": "left",
                    "sortable": True,
                },
                {
                    "name": "state",
                    "label": "State",
                    "field": "state",
                    "align": "left",
                    "sortable": True,
                },
                {
                    "name": "start_time",
                    "label": "Start Time",
                    "field": "start_time",
                    "align": "left",
                    "sortable": True,
                },
                {
                    "name": "duration",
                    "label": "Duration",
                    "field": "duration",
                    "align": "left",
                    "sortable": True,
                },
                {
                    "name": "data_points",
                    "label": "Data Points",
                    "field": "data_points",
                    "align": "right",
                    "sortable": True,
                },
                {
                    "name": "actions",
                    "label": "Actions",
                    "field": "actions",
                    "align": "center",
                    "sortable": False,
                },
            ]

            self._table = ui.table(
                columns=columns, rows=[], selection="single", pagination=10
            ).classes("w-full")

            self._table.add_slot(
                "body",
                r"""
                <q-tr :props="props">
                    <q-td key="name" :props="props">{{ props.row.name }}</q-td>
                    <q-td key="state" :props="props">{{ props.row.state }}</q-td>
                    <q-td key="start_time" :props="props">{{ props.row.start_time }}</q-td>
                    <q-td key="duration" :props="props">{{ props.row.duration }}</q-td>
                    <q-td key="data_points" :props="props">{{ props.row.data_points }}</q-td>
                    <q-td key="actions" :props="props">
                        <q-btn size="sm" icon="visibility" flat dense @click="$parent.$emit('view', props.row)" />
                        <q-btn size="sm" icon="delete" flat dense color="negative" @click="$parent.$emit('delete', props.row)" />
                    </q-td>
                </q-tr>
            """,
            )

            self._table.on("view", self._on_view)
            self._table.on("delete", self._on_delete)

            # Load initial data
            self._load_experiments()

            # Refresh button
            ui.button("Refresh", icon="refresh", on_click=self._load_experiments).props(
                "flat"
            )

        return container

    def _load_experiments(self) -> None:
        """Load experiments into table"""
        try:
            experiment_ids = self.experiment_manager.list_experiments()
            rows = []

            for exp_id in experiment_ids:
                config = self.experiment_manager.get_experiment_config(exp_id)
                result = self.experiment_manager.get_experiment_result(exp_id)

                if config and result:
                    # Apply filters
                    if (
                        self._name_filter
                        and self._name_filter.lower() not in config.name.lower()
                    ):
                        continue
                    if self._state_filter and result.state != self._state_filter:
                        continue
                    if self._from_date and (
                        not result.start_time
                        or result.start_time.date() < self._from_date
                    ):
                        continue
                    if self._to_date and (
                        not result.start_time
                        or result.start_time.date() > self._to_date
                    ):
                        continue

                    # Format start time
                    start_time_str = "--"
                    if result.start_time:
                        start_time_str = result.start_time.strftime("%Y-%m-%d %H:%M:%S")

                    # Format duration
                    duration_str = "--"
                    if result.duration_seconds:
                        duration_str = self._format_duration(result.duration_seconds)

                    rows.append(
                        {
                            "id": exp_id,
                            "name": config.name,
                            "state": result.state.value.title(),
                            "start_time": start_time_str,
                            "duration": duration_str,
                            "data_points": result.data_points_collected,
                            "actions": "",  # Will be handled in template
                        }
                    )

            if self._table:
                sort_by = (
                    self._table.pagination.get("sortBy")
                    if self._table.pagination
                    else None
                )
                descending = (
                    self._table.pagination.get("descending", False)
                    if self._table.pagination
                    else False
                )
                if sort_by:
                    rows.sort(key=lambda r: r.get(sort_by), reverse=descending)
                self._table.rows = rows

        except Exception as e:
            error(f"Error loading experiments: {e}")
            ui.notify(f"Error loading experiments: {str(e)}", color="negative")

    def _format_duration(self, duration_seconds: float) -> str:
        """Format duration in human-readable format"""
        if duration_seconds < 60:
            return f"{duration_seconds:.0f}s"
        elif duration_seconds < 3600:
            minutes = duration_seconds / 60
            return f"{minutes:.1f}m"
        else:
            hours = duration_seconds / 3600

            return f"{hours:.1f}h"

    def _format_date_range(
        self, from_date: Optional[date], to_date: Optional[date]
    ) -> str:
        """Format date range for display"""
        if not from_date and not to_date:
            return ""
        from_str = from_date.strftime("%Y-%m-%d") if from_date else ""
        to_str = to_date.strftime("%Y-%m-%d") if to_date else ""
        if from_str and to_str:
            return f"{from_str} - {to_str}"
        if from_str:
            return f"from {from_str}"
        return f"until {to_str}"

    def _on_name_filter_change(self, value: str) -> None:
        self._name_filter = value.strip() if value else ""
        self._load_experiments()

    def _on_state_filter_change(self, value: str) -> None:
        if value and value != "All":
            self._state_filter = ExperimentState(value.lower())
        else:
            self._state_filter = None
        self._load_experiments()

    def _open_date_dialog(self) -> None:
        """Open dialog to select date range"""
        from_date = self._from_date
        to_date = self._to_date

        with ui.dialog() as dialog:
            self._date_dialog = dialog
            with ui.card():
                ui.label("Select Date Range").classes("text-lg font-bold")

                self._date_from_picker = ui.date(
                    value=from_date.strftime("%Y-%m-%d") if from_date else ""
                )
                self._date_to_picker = ui.date(
                    value=to_date.strftime("%Y-%m-%d") if to_date else ""
                )

                with ui.row().classes("gap-2 justify-end"):
                    ui.button("Cancel", on_click=dialog.close).props("flat")

                    def _apply() -> None:
                        self._apply_date_range()
                        dialog.close()

                    ui.button("Apply", on_click=_apply).props("color=primary")

        dialog.open()

    def _apply_date_range(self) -> None:
        """Apply date range from dialog"""
        raw_from = self._date_from_picker.value or ""
        raw_to = self._date_to_picker.value or ""

        from_date = None
        to_date = None
        if raw_from:
            try:
                from_date = datetime.strptime(raw_from, "%Y-%m-%d").date()
            except ValueError:
                ui.notify("Invalid date", color="negative")
                return
        if raw_to:
            try:
                to_date = datetime.strptime(raw_to, "%Y-%m-%d").date()
            except ValueError:
                ui.notify("Invalid date", color="negative")
                return

        self._from_date = from_date
        self._to_date = to_date
        if self._date_range_input:
            self._date_range_input.value = self._format_date_range(from_date, to_date)
        self._load_experiments()

    def _clear_filters(self) -> None:
        self._name_filter = ""
        self._state_filter = None
        self._from_date = None
        self._to_date = None
        if self._name_input:
            self._name_input.value = ""
        if self._state_select:
            self._state_select.value = "All"
        if self._date_range_input:
            self._date_range_input.value = ""
        self._load_experiments()

    def _on_view(self, e) -> None:
        row = e.args
        exp_id = row.get("id") if isinstance(row, dict) else None
        if exp_id:
            self._view_results(exp_id)

    def _on_delete(self, e) -> None:
        row = e.args
        exp_id = row.get("id") if isinstance(row, dict) else None
        if exp_id:
            self._delete_experiment(exp_id)

    def _view_results(self, experiment_id: str) -> None:
        try:
            result = self.experiment_manager.get_experiment_result(experiment_id)

            if not result:
                ui.notify("No results available", color="warning")
                return

            metadata: Dict[str, Any] = {}
            if result.result_directory:
                meta_path = result.result_directory / "experiment_metadata.json"
                if meta_path.exists():
                    try:
                        with open(meta_path, "r", encoding="utf-8") as f:
                            metadata = json.load(f)
                    except Exception as e:  # pragma: no cover - best effort
                        warning(f"Failed to read metadata: {e}")

            raw_files: List[str] = []
            proc_files: List[str] = []
            if result.raw_data_dir and result.raw_data_dir.exists():
                raw_files = [
                    p.name for p in result.raw_data_dir.iterdir() if p.is_file()
                ]
            if result.processed_data_dir and result.processed_data_dir.exists():
                proc_files = [
                    p.name for p in result.processed_data_dir.iterdir() if p.is_file()
                ]

            with ui.dialog() as dialog:
                with ui.card().classes("w-[600px] max-w-[95vw]"):
                    ui.label(f"Results: {result.name}").classes(
                        "text-lg font-bold mb-2"
                    )

                    with ui.column().classes("gap-1"):
                        ui.label(f"Experiment ID: {result.experiment_id}").classes(
                            "text-sm"
                        )
                        ui.label(f"State: {result.state.value}").classes("text-sm")
                        if result.start_time:
                            ui.label(
                                "Start: "
                                + result.start_time.strftime("%Y-%m-%d %H:%M:%S")
                            ).classes("text-sm")
                        if result.end_time:
                            ui.label(
                                "End: " + result.end_time.strftime("%Y-%m-%d %H:%M:%S")
                            ).classes("text-sm")
                        if result.duration_seconds:
                            ui.label(
                                "Duration: "
                                + self._format_duration(result.duration_seconds)
                            ).classes("text-sm")
                        ui.label(
                            f"Data Points: {result.data_points_collected}"
                        ).classes("text-sm")
                        if result.errors_count:
                            ui.label(f"Errors: {result.errors_count}").classes(
                                "text-sm text-red-600"
                            )

                    if metadata:
                        ui.separator()
                        ui.label("Metadata").classes("font-semibold")
                        with ui.column().classes("gap-1 max-h-40 overflow-y-auto"):
                            for key, value in metadata.items():
                                if isinstance(value, (dict, list)):
                                    continue
                                ui.label(f"{key}: {value}").classes(
                                    "text-sm text-gray-700"
                                )

                    if raw_files or proc_files:
                        ui.separator()
                        ui.label("Stored Files").classes("font-semibold")
                        with ui.column().classes("gap-1 max-h-40 overflow-y-auto"):
                            for fname in raw_files:
                                ui.label(fname).classes("text-sm text-gray-600")
                            for fname in proc_files:
                                ui.label(fname).classes("text-sm text-gray-600")

                    ui.button("Close", on_click=dialog.close).classes("self-end mt-4")

            dialog.open()
        except Exception as e:
            error(f"Error viewing results: {e}")
            ui.notify(f"Error viewing results: {e}", color="negative")

    def _delete_experiment(self, experiment_id: str) -> None:
        async def confirm_delete() -> None:
            try:
                success = self.experiment_manager.delete_experiment(experiment_id)
                if success:
                    ui.notify("Experiment deleted", color="positive")
                else:
                    ui.notify("Failed to delete experiment", color="negative")
            except Exception as e:
                error(f"Error deleting experiment: {e}")
                ui.notify(f"Error: {e}", color="negative")
            self._load_experiments()

        with ui.dialog() as dialog:
            with ui.card():
                ui.label("Delete Experiment").classes("text-lg font-bold")
                ui.label("Are you sure you want to delete this experiment?").classes(
                    "mt-2"
                )

                with ui.row().classes("gap-2 justify-end mt-4"):
                    ui.button("Cancel", on_click=dialog.close).props("flat")

                    async def _on_confirm():
                        await confirm_delete()
                        dialog.close()

                    ui.button("Delete", on_click=_on_confirm).props("color=negative")

        dialog.open()

    def _update_element(self, data: Any) -> None:
        """Update element with new data (required by BaseComponent)"""
        self._load_experiments()


class ExperimentComponent(BaseComponent):
    """Main experiment management component"""

    def __init__(
        self,
        config: ComponentConfig,
        config_service: ConfigurationService,
        sensor_manager: Optional[SensorManager] = None,
        controller_manager: Optional[ControllerManager] = None,
    ):
        super().__init__(config)

        self.config_service = config_service
        self.sensor_manager = sensor_manager
        self.controller_manager = controller_manager
        # Get or create experiment manager
        self.experiment_manager = get_experiment_manager()
        if not self.experiment_manager:
            warning("No experiment manager available - creating new instance")
            from src.experiment_handler.experiment_manager import (
                ExperimentManager,
                set_experiment_manager,
            )

            self.experiment_manager = ExperimentManager(
                config_service=config_service,
                sensor_manager=sensor_manager,
                controller_manager=controller_manager,
            )
            set_experiment_manager(self.experiment_manager)
        # ensure experiment_manager is not None for type checking
        assert (
            self.experiment_manager is not None
        ), "ExperimentManager must be initialized"

        # Ensure we have a valid experiment manager
        if not self.experiment_manager:
            raise RuntimeError("Failed to initialize experiment manager")

        # Components
        self.config_dialog: Optional[ExperimentConfigDialog] = None
        self.current_experiment_display: Optional[CurrentExperimentDisplay] = None
        self.history_table: Optional[ExperimentHistoryTable] = None

    def render(self) -> Element:
        """Render experiment management interface"""
        with ui.column().classes("w-full h-full gap-6 p-4") as container:
            # Header with title and main actions
            with ui.row().classes("items-center justify-between w-full"):
                ui.label("Experiment Management").classes("text-2xl font-bold")

                with ui.row().classes("gap-2"):
                    ui.button(
                        "New Experiment",
                        icon="add_circle",
                        on_click=self._show_new_experiment_dialog,
                    ).props("color=primary")

                    ui.button(
                        "Stop Current",
                        icon="stop",
                        on_click=self._stop_current_experiment,
                    ).props("color=negative flat")

            self.current_experiment_display = CurrentExperimentDisplay(
                cast(ExperimentManager, self.experiment_manager)
            )
            self.current_experiment_display.render()
            # History section
            self.history_table = ExperimentHistoryTable(
                cast(ExperimentManager, self.experiment_manager)
            )
            self.history_table.render()

        return container

    def _show_new_experiment_dialog(self) -> None:
        """Show new experiment configuration dialog"""
        experiment_wizard = ExperimentSetupWizardComponent(
            config_service=self.config_service,
            experiment_manager=cast(ExperimentManager, self.experiment_manager),
            sensor_manager=self.sensor_manager,
            controller_manager=self.controller_manager,
            on_close=None,
        )
        experiment_wizard.show_dialog()

    async def _stop_current_experiment(self) -> None:
        """Stop the current experiment"""
        # ensure experiment_manager is initialized
        if self.experiment_manager is None:
            ui.notify("Experiment manager not initialized", color="negative")
            return
        try:
            current_experiment = self.experiment_manager.get_current_experiment()
            if not current_experiment:
                ui.notify("No experiment is currently running", color="info")
                return

            success = await self.experiment_manager.stop_experiment()
            if success:
                ui.notify("Experiment stopped successfully", color="info")
            else:
                ui.notify("Failed to stop experiment", color="negative")

        except Exception as e:
            error(f"Error stopping experiment: {e}")
            ui.notify(f"Error: {str(e)}", color="negative")

    def _on_experiment_created(self) -> None:
        """Handle experiment creation callback"""
        # Refresh displays
        if self.current_experiment_display:
            self.current_experiment_display.update({})
        if self.history_table:
            self.history_table.update({})

    def cleanup(self) -> None:
        """Cleanup component resources"""
        if self.current_experiment_display:
            self.current_experiment_display.cleanup()
        if self.history_table:
            self.history_table.cleanup()

        super().cleanup()

    def _update_element(self, data: Any) -> None:
        """Update element with new data (required by BaseComponent)"""
        # Update child components
        if self.current_experiment_display:
            self.current_experiment_display.update(data)
        if self.history_table:
            self.history_table.update(data)


# Factory function for easy instantiation
def create_experiment_component(
    component_id: str = "experiment_component",
    config_service: Optional[ConfigurationService] = None,
    sensor_manager: Optional[SensorManager] = None,
    controller_manager: Optional[ControllerManager] = None,
) -> ExperimentComponent:
    """Create an experiment component with default configuration"""
    # Get services if not provided
    if not config_service:
        from src.utils.config_utils.config_service import get_config_service

        config_service = get_config_service()
        if not config_service:
            raise RuntimeError("Failed to get configuration service")

    config = ComponentConfig(
        component_id=component_id,
        title="Experiment Management",
        classes="experiment-component",
    )

    return ExperimentComponent(
        config=config,
        config_service=config_service,
        sensor_manager=sensor_manager,
        controller_manager=controller_manager,
    )
