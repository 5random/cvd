from nicegui import ui
from datetime import datetime
from typing import List, Optional

from src.core.experiment_manager import (
    ExperimentConfig,
    ExperimentState,
    get_experiment_manager,
)
from gui.ui_helpers import notify_later


class ExperimentManagementSection:

    def __init__(self, settings: Optional[dict] = None, callbacks: Optional[dict] = None):
        """Initialize experiment management section with settings
        Args:
            settings: optional configuration dictionary
            callbacks: optional callbacks for button actions
        """
        self.experiment_running = False
        self.callbacks = callbacks or {}
        self._experiment_start: Optional[datetime] = None
        self._experiment_duration: Optional[int] = None
        self._experiment_timer: Optional[ui.timer] = None
        self._current_experiment_id: Optional[str] = None
        self.experiment_manager = get_experiment_manager()

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
                        on_change=self._on_name_change,
                    )
                    .classes("w-full")
                )

                self.experiment_duration_input = (
                    ui.number(
                        "Duration (minutes)",
                        value=self.settings["duration"],
                        min=1,
                        max=100000,
                        on_change=self._on_duration_change,
                    )
                    .classes("w-full")
                )

                # Experiment options
                ui.label("Recording Options").classes("text-sm font-semibold")
                with ui.column().classes("ml-4 gap-1"):
                    self.record_motion_data_checkbox = ui.checkbox(
                        "Record motion detection data",
                        value=self.settings["record_motion_data"],
                        on_change=lambda e: self._on_checkbox_change(
                            "record_motion_data", e.value
                        ),
                    )
                    self.record_timestamps_checkbox = ui.checkbox(
                        "Record event timestamps",
                        value=self.settings["record_timestamps"],
                        on_change=lambda e: self._on_checkbox_change(
                            "record_timestamps", e.value
                        ),
                    )
                    self.save_alerts_checkbox = ui.checkbox(
                        "Save alert events",
                        value=self.settings["save_alerts"],
                        on_change=lambda e: self._on_checkbox_change(
                            "save_alerts", e.value
                        ),
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

            # Bind default callbacks if none provided
            cb = self.callbacks.get("toggle_experiment")
            if cb is not None:
                self.start_experiment_btn.on("click", cb)
                self.stop_experiment_btn.on("click", cb)
            else:
                self.start_experiment_btn.on("click", self.toggle_experiment)
                self.stop_experiment_btn.on("click", self.toggle_experiment)

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
        if hasattr(event, "value"):
            self.settings["experiment_name"] = event.value

    def _on_duration_change(self, event) -> None:
        """Update experiment duration in settings."""
        if hasattr(event, "value"):
            try:
                self.settings["duration"] = int(event.value)
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

    async def toggle_experiment(self) -> None:
        """Start or stop an experiment using the global ExperimentManager."""
        manager = self.experiment_manager
        if manager is None:
            notify_later("No experiment manager available", type="negative")
            return

        if not self.experiment_running:
            name = self.experiment_name_input.value
            duration = self.experiment_duration_input.value
            self._experiment_duration = int(duration) if duration else None

            config = ExperimentConfig(
                name=name,
                duration_minutes=self._experiment_duration,
            )
            exp_id = manager.create_experiment(config)
            success = await manager.start_experiment(exp_id)
            if not success:
                notify_later("Failed to start experiment", type="negative")
                return

            self._current_experiment_id = exp_id
            self.experiment_running = True
            self._experiment_start = datetime.now()
            self.start_experiment_btn.disable()
            self.stop_experiment_btn.enable()
            self.experiment_icon.classes("text-green-600")
            self.experiment_status_label.text = "Experiment running"
            self.experiment_name_label.text = f"Name: {name}"
            dur_text = (
                f"Duration: {self._experiment_duration} min"
                if self._experiment_duration
                else "Duration: unlimited"
            )
            self.experiment_duration_label.text = dur_text
            self.experiment_elapsed_label.text = "Elapsed: 0s"
            self.experiment_progress.value = 0.0
            self.experiment_details.set_visibility(True)
            if self._experiment_timer:
                self._experiment_timer.cancel()
            self._experiment_timer = ui.timer(1.0, self._update_experiment_status)
            notify_later(f'Started experiment "{name}"', type="positive")
        else:
            if manager.get_current_state() not in (
                ExperimentState.RUNNING,
                ExperimentState.PAUSED,
            ):
                # Experiment already finished, nothing to stop
                self.experiment_running = False
                self._current_experiment_id = None
                self.start_experiment_btn.enable()
                self.stop_experiment_btn.disable()
                self.experiment_icon.classes("text-gray-500")
                self.experiment_status_label.text = "No experiment running"
                self.experiment_details.set_visibility(False)
                if self._experiment_timer:
                    self._experiment_timer.cancel()
                    self._experiment_timer = None
                self.load_recent_experiments()
                return

            success = await manager.stop_experiment()
            if not success:
                notify_later("Failed to stop experiment", type="negative")
                return

            self.experiment_running = False
            self._current_experiment_id = None
            self.start_experiment_btn.enable()
            self.stop_experiment_btn.disable()
            self.experiment_icon.classes("text-gray-500")
            self.experiment_status_label.text = "No experiment running"
            self.experiment_details.set_visibility(False)
            if self._experiment_timer:
                self._experiment_timer.cancel()
                self._experiment_timer = None
            self.load_recent_experiments()
            notify_later("Experiment stopped", type="info")

    def _update_experiment_status(self) -> None:
        """Update elapsed time and progress bar during a running experiment."""
        if not self.experiment_running or not self._experiment_start:
            return

        elapsed = (datetime.now() - self._experiment_start).total_seconds()
        self.experiment_elapsed_label.text = f"Elapsed: {int(elapsed)}s"

        if self._experiment_duration:
            total = self._experiment_duration * 60
            progress = min(elapsed / total, 1.0)
            self.experiment_progress.value = progress
