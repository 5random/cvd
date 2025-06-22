from nicegui import ui
from datetime import datetime
from typing import Optional, Callable

from src.controllers.controller_manager import ControllerManager
from src.controllers.webcam import MotionDetectionResult


class MotionStatusSection:
    """Class to create a motion detection status section in the UI"""

    def __init__(
        self,
        settings: Optional[dict] = None,
        controller_manager: Optional[ControllerManager] = None,
        update_callback: Optional[Callable[[bool], None]] = None,
    ) -> None:
        """Initialize motion status section with settings and optional controller manager."""

        self.controller_manager = controller_manager
        self._update_callback = update_callback

        self.camera_active = False
        self.motion_detected = False
        self._last_motion_time: Optional[datetime] = None
        self._detection_count = 0
        self._refresh_timer: Optional[ui.timer] = None

        settings = settings or {
            "motion_detected": False,
            "confidence": 0,
            "threshold": 50,
            "roi_status": "Full Frame",
            "last_motion": "Never",
            "no_motion_detections": 0,
            "uptime": "00:00:00",
            "fps_actual": "--",
            "processing_time": "-- ms",
            "cpu_usage": "--%",
        }
        self.settings = settings

        @ui.page("/motion_status")
        def motion_status_page():
            # Create the motion status section
            self.create_motion_status_section()

    def create_motion_status_section(self):
        with ui.card().classes("cvd-card w-full"):
            ui.label("Motion Detection Status").classes("text-lg font-bold mb-2")

            # Main status display
            with ui.row().classes("items-center gap-4 mb-4"):
                self.motion_icon = ui.icon("motion_photos_off", size="3rem").classes(
                    "text-gray-500"
                )
                with ui.column():
                    self.motion_label = ui.label("No Motion Detected").classes(
                        "text-lg font-semibold"
                    )
                    self.motion_percentage = ui.label("Motion Level: 0%").classes(
                        "cvd-sensor-value text-gray-600"
                    )

            # Status details
            with ui.grid(columns=3).classes("gap-4 w-full"):
                # Detection info
                with ui.column():
                    ui.label("Detection Info").classes(
                        "text-sm font-semibold text-gray-700"
                    )
                    self.confidence_label = ui.label("Confidence: --").classes(
                        "text-sm"
                    )
                    self.threshold_label = ui.label("Threshold: 50%").classes("text-sm")
                    self.roi_status_label = ui.label("ROI: Full Frame").classes(
                        "text-sm"
                    )

                # Timing info
                with ui.column():
                    ui.label("Timing").classes("text-sm font-semibold text-gray-700")
                    self.last_motion_label = ui.label("Last Motion: Never").classes(
                        "text-sm"
                    )
                    self.detection_count_label = ui.label(
                        "No Motion Detections: 0"
                    ).classes("text-sm")
                    self.uptime_label = ui.label("Monitoring: 00:00:00").classes(
                        "text-sm"
                    )

                # Performance info
                with ui.column():
                    ui.label("Performance").classes(
                        "text-sm font-semibold text-gray-700"
                    )
                    self.fps_actual_label = ui.label("Actual FPS: --").classes(
                        "text-sm"
                    )
                    self.processing_time_label = ui.label("Processing: -- ms").classes(
                        "text-sm"
                    )
                    self.cpu_usage_label = ui.label("CPU Usage: --%").classes("text-sm")

            # periodic refresh
            self._refresh_timer = ui.timer(1.0, self._refresh_status)

    def _get_result(self) -> Optional[MotionDetectionResult]:
        """Retrieve the latest MotionDetectionResult from the controller manager"""
        if not self.controller_manager:
            return None
        controller = self.controller_manager.get_controller("motion_detection")
        if not controller:
            return None
        output = controller.get_output()
        if isinstance(output, MotionDetectionResult):
            return output
        return None

    def _refresh_status(self) -> None:
        """Update display labels with current motion detection results"""
        result = self._get_result()
        if not result:
            return

        # remember previous detection state before updating
        prev = self.motion_detected

        self.motion_detected = result.motion_detected
        self.motion_icon.name = (
            "motion_photos_on" if result.motion_detected else "motion_photos_off"
        )
        self.motion_icon.classes(
            replace="text-orange-500" if result.motion_detected else "text-gray-500"
        )
        self.motion_label.text = (
            "Motion Detected" if result.motion_detected else "No Motion Detected"
        )
        self.motion_percentage.text = f"Motion Level: {result.motion_percentage:.1f}%"
        self.confidence_label.text = f"Confidence: {result.confidence:.2f}"

        # update last motion time and count only on rising edge
        if result.motion_detected and not prev:

            self._last_motion_time = datetime.now()
            self._detection_count += 1

        if self._last_motion_time:
            self.last_motion_label.text = (
                f"Last Motion: {self._last_motion_time.strftime('%H:%M:%S')}"
            )

        self.detection_count_label.text = f"Detections: {self._detection_count}"

        if self._update_callback:
            self._update_callback(result.motion_detected)

    def cleanup(self) -> None:
        """Cancel periodic refresh timer."""
        if self._refresh_timer:
            try:
                self._refresh_timer.cancel()
            except Exception:
                pass
            self._refresh_timer = None
