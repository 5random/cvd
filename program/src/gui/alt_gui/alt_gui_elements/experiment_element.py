from nicegui import ui
from datetime import datetime
from typing import List
from program.src.experiment_handler.experiment_manager import get_experiment_manager


class ExperimentManagementSection:
    def __init__(self, settings):
        """Initialize experiment management section with settings"""
        self.experiment_running = False
        settings = settings or {
            "experiment_name": f'Experiment_{datetime.now().strftime("%Y%m%d_%H%M")}',
            "duration": 60,  # Default duration in minutes
            "record_video": True,
            "record_motion_data": True,
            "record_timestamps": True,
            "save_alerts": False,
        }
        self.settings = settings

        @ui.page("/experiment_management")
        def experiment_management_page():
            # Create the experiment management section
            self.create_experiment_section()

    def create_experiment_section(self):
        """Create experiment management section"""
        with ui.card().classes("cvd-card w-full"):
            ui.label("Experiment Management").classes("text-lg font-bold mb-2")

            # Current experiment status
            with ui.row().classes("items-center gap-2 mb-3"):
                self.experiment_icon = ui.icon("science", size="sm").classes(
                    "text-gray-500"
                )
                self.experiment_status_label = ui.label(
                    "No experiment running"
                ).classes("font-medium")

            # Experiment details (hidden when not running)
            self.experiment_details = ui.column().classes("gap-1 mb-3")
            with self.experiment_details:
                self.experiment_name_label = ui.label("").classes("text-sm")
                self.experiment_duration_label = ui.label("").classes("text-sm")
                self.experiment_elapsed_label = ui.label("").classes("text-sm")
                self.experiment_progress = ui.linear_progress(value=0).classes("w-full")
            self.experiment_details.set_visibility(False)

            # Quick experiment setup
            ui.label("Quick Experiment Setup").classes("text-sm font-semibold mb-2")

            with ui.column().classes("gap-3"):
                self.experiment_name_input = (
                    ui.input(
                        "Experiment Name",
                        placeholder="Enter experiment name",
                        value=self.settings["experiment_name"],
                    )
                    .on("update:model-value", self._on_name_change)
                    .classes("w-full")
                )

                self.experiment_duration_input = (
                    ui.number(
                        "Duration (minutes)",
                        value=self.settings["duration"],
                        min=1,
                        max=100000,
                    )
                    .on("update:model-value", self._on_duration_change)
                    .classes("w-full")
                )

                # Experiment options
                ui.label("Recording Options").classes("text-sm font-semibold")
                with ui.column().classes("ml-4 gap-1"):
                    self.record_motion_data_checkbox = ui.checkbox(
                        "Record motion detection data",
                        value=self.settings["record_motion_data"],
                    ).on(
                        "update:model-value",
                        lambda e: self._on_checkbox_change(
                            "record_motion_data", e.value
                        ),
                    )
                    self.record_timestamps_checkbox = ui.checkbox(
                        "Record event timestamps",
                        value=self.settings["record_timestamps"],
                    ).on(
                        "update:model-value",
                        lambda e: self._on_checkbox_change(
                            "record_timestamps", e.value
                        ),
                    )
                    self.save_alerts_checkbox = ui.checkbox(
                        "Save alert events",
                        value=self.settings["save_alerts"],
                    ).on(
                        "update:model-value",
                        lambda e: self._on_checkbox_change("save_alerts", e.value),
                    )

            # Control buttons
            with ui.row().classes("gap-2 w-full mt-4"):
                self.start_experiment_btn = (
                    ui.button(
                        "Start Experiment",
                        icon="play_arrow",
                    )
                    .props("color=positive")
                    .classes("flex-1")
                )

                self.stop_experiment_btn = (
                    ui.button(
                        "Stop Experiment",
                        icon="stop",
                    )
                    .props("color=negative")
                    .classes("flex-1")
                )
                self.stop_experiment_btn.disable()

            # Recent experiments
            ui.separator().classes("my-3")
            with ui.expansion("Recent Experiments").classes(
                "w-full"
            ) as self.recent_expansion:
                with ui.column().classes("w-full") as self.recent_list:
                    self.no_experiments_label = ui.label(
                        "No recent experiments available"
                    ).classes("text-sm text-gray-600")

        # populate recent experiments initially
        self.load_recent_experiments()

    def _on_name_change(self, event) -> None:
        """Update experiment name in settings."""
        value = getattr(event, "value", None)
        if value is not None:
            self.settings["experiment_name"] = value

    def _on_duration_change(self, event) -> None:
        """Update experiment duration in settings."""
        value = getattr(event, "value", None)
        if value is not None:
            try:
                self.settings["duration"] = int(value)
            except (TypeError, ValueError):
                return

    def _on_checkbox_change(self, key: str, value: bool) -> None:
        """Handle checkbox value changes."""
        self.settings[key] = bool(value)

    def _format_duration(self, seconds: float) -> str:
        """Return human readable duration"""
        if seconds < 60:
            return f"{int(seconds)}s"
        if seconds < 3600:
            return f"{seconds/60:.1f}m"
        return f"{seconds/3600:.1f}h"

    def load_recent_experiments(self) -> None:
        """Populate recent experiment list from global ExperimentManager."""
        if not hasattr(self, "recent_list"):
            return

        manager = get_experiment_manager()
        self.recent_list.clear()

        if not manager:
            if hasattr(self, "no_experiments_label"):
                self.no_experiments_label.set_visibility(True)
            return

        exp_ids: List[str] = manager.list_experiments()
        results = []
        for exp_id in exp_ids:
            result = manager.get_experiment_result(exp_id)
            if result and result.end_time:
                results.append(result)

        if not results:
            self.no_experiments_label.set_visibility(True)
            return

        self.no_experiments_label.set_visibility(False)
        results.sort(key=lambda r: r.end_time or r.start_time, reverse=True)
        for res in results:
            duration = res.duration_seconds or 0
            with self.recent_list:
                with ui.row().classes("justify-between w-full"):
                    ui.label(res.name).classes("font-medium")
                    ui.label(self._format_duration(duration)).classes(
                        "text-sm text-gray-600"
                    )
