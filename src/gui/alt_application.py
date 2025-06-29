"""Simplified GUI application exposing core CVD functionality.

The module provides a NiceGUI based interface for camera control, motion
detection, basic experiment management and email alert configuration.
It is intended for running the application without the full desktop GUI.
It expects the example configuration from ``src/cvd/config/simple_config.json``.
Set ``"disable_sensors": true`` in the configuration to skip starting sensors
entirely. This is useful for tests or camera-only setups.

"""

from pathlib import Path
import sys

# Allow running this file directly without installing the package
if __name__ == "__main__" and __package__ is None:
    # Add project root to path so 'main' module can be imported
    sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
    # Add src directory to path so 'cvd' package can be imported
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import asyncio
import contextlib
from datetime import datetime, timedelta
from typing import Any, Dict, Optional, Type, cast
import re

import cv2
import numpy as np
from fastapi import Request
from fastapi.responses import StreamingResponse, JSONResponse
from nicegui import app, ui

from src.controllers import controller_manager as controller_manager_module
from src.controllers.webcam import MotionDetectionController
from src.controllers.controller_base import ControllerConfig, ControllerStatus
from src.controllers.controller_manager import ControllerManager
from src.controllers.camera_utils import probe_camera_modes
from src.controllers.webcam import CameraCaptureController
from src.core.experiment_manager import (
    ExperimentConfig,
    ExperimentManager,
    ExperimentState,
    set_experiment_manager,
)
from src.gui import (
    EmailAlertStatusDisplay,
    ExperimentManagementSection,
    MotionStatusSection,
    WebcamStreamElement,
    create_demo_configurations,
    create_email_alert_wizard,
    setup_global_styles,
)
from src.gui.alt_gui_elements.alert_element import (
    load_alert_configs,
    save_alert_configs,
)
from src.gui.alt_gui_elements.webcam_stream_element import UVC_DEFAULTS
from src.core import email_alert_service
from src.utils.concurrency import (
    gather_with_concurrency,
    run_in_executor,
    run_network_io,
    run_camera_io,
)
from src.utils.concurrency.async_utils import install_signal_handlers
from src.utils.config_service import ConfigurationService, set_config_service
from src.gui.ui_helpers import notify_later
from src.gui.utils import generate_mjpeg_stream
from src.utils.log_service import info, warning, error
from src.controllers.roi_utils import clamp_roi, rotate_roi

# Maximum frames per second for the MJPEG video feed
FPS_CAP = 30


class SimpleGUIApplication:
    """Simple GUI application skeleton with basic CVD functionality"""

    def __init__(
        self,
        controller_manager: Optional[ControllerManager] = None,
        config_dir: Optional[Path] = None,
        *,
        config_service: Optional[ConfigurationService] = None,
        email_alert_service_cls: (
            Type[email_alert_service.EmailAlertService] | None
        ) = None,
    ):
        self.camera_active = False
        self.motion_detected = False
        self.experiment_running = False
        self.alerts_enabled = False
        self.camera_controller: Optional[CameraCaptureController] = None
        self._video_feed_connections = 0

        # Determine configuration directory and initialise core services
        if config_service is None:
            if config_dir is None:
                # use the configuration bundled with the program by default
                # (located in ``src/cvd/config`` relative to this file)
                config_dir = Path(__file__).resolve().parents[2] / "config"

            self.config_service = ConfigurationService(
                config_dir / "config.json",
                config_dir / "default_config.json",
            )
        else:
            self.config_service = config_service

        set_config_service(self.config_service)

        self.controller_manager = (
            controller_manager
            if controller_manager is not None
            else controller_manager_module.create_cvd_controller_manager()
        )

        cls = email_alert_service_cls or email_alert_service.EmailAlertService
        self.email_alert_service = cls(self.config_service)
        # set global singleton so UI elements use the configured service
        email_alert_service.set_email_alert_service(self.email_alert_service)
        # use the already created controller manager for the experiment manager
        self.experiment_manager = ExperimentManager(
            config_service=self.config_service,
            controller_manager=self.controller_manager,
            auto_install_signal_handlers=False,
        )
        # track experiment state changes to keep the UI in sync
        self.experiment_manager.add_state_change_callback(
            self._on_experiment_state_change
        )
        # expose globally for UI elements
        set_experiment_manager(self.experiment_manager)

        # Additional runtime attributes
        # Ensure a container slot exists so ``ui.dark_mode`` can be created even
        # outside of a page context (e.g. during tests)
        if not ui.context.slot_stack:
            from nicegui import Client

            ui.context.slot_stack.append(Client.auto_index_client.layout.default_slot)
        self.dark_mode = ui.dark_mode()
        self._current_experiment_id: Optional[str] = None
        self._experiment_start: Optional[datetime] = None
        self._experiment_duration: Optional[int] = None
        self._experiment_timer: Optional[ui.timer] = None
        self._time_timer: Optional[ui.timer] = None
        self._processing_task: Optional[asyncio.Task] = None
        self._alert_task: Optional[asyncio.Task] = None
        self._motion_task: Optional[asyncio.Task] = None
        self.supported_camera_modes: list[tuple[int, int, int]] = []
        self._last_motion_time: datetime = datetime.now()

        # Placeholder settings
        self.settings = {
            "sensitivity": 50,
            "fps": 30,
            "fps_cap": max(self.config_service.get("webapp.fps_cap", int, FPS_CAP), 1),
            "resolution": "640x480 (30fps)",
            "rotation": 0,
            "roi_enabled": False,
            "email": "",
            "alert_delay": 5,
            "experiment_name": f'Experiment_{datetime.now().strftime("%Y%m%d_%H%M")}',
            "duration": 60,
            "record_video": True,
            "record_motion_data": True,
            "record_timestamps": True,
            "save_alerts": False,
        }

        # Load persisted alert configurations; empty list if none found
        self.alert_configurations = load_alert_configs(self.config_service)
        self._alert_configs_from_disk = bool(self.alert_configurations)
        if not self.alert_configurations:
            if callable(create_demo_configurations):
                self.alert_configurations = create_demo_configurations()
            else:
                self.alert_configurations = []
        self.alert_display = EmailAlertStatusDisplay(self.alert_configurations)
        self.alert_display.update_callback = self._on_alert_config_changed

        # Track if we have active alerts
        self._update_alerts_status()

        # Retrieve and cast controllers to their concrete types
        self.camera_controller = cast(
            Optional[CameraCaptureController],
            self.controller_manager.get_controller("camera_capture"),
        )

        self.motion_controller = cast(
            Optional[MotionDetectionController],
            self.controller_manager.get_controller("motion_detection"),
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
                        ui.icon(
                            "motion_photos_on"
                            if self.motion_detected
                            else "motion_photos_off"
                        )
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
                    ui.button(
                        icon="fullscreen",
                        on_click=self.toggle_fullscreen,
                    ).props("flat round").classes("text-white").tooltip(
                        "Toggle Fullscreen"
                    )

                    ui.button(
                        icon="refresh",
                        on_click=self.reload_page,
                    ).props(
                        "flat round"
                    ).classes("text-white").tooltip("Reload Page")

                    # Dark/Light mode toggle
                    self.dark_mode_btn = (
                        ui.button(
                            icon="light_mode" if self.dark_mode.value else "dark_mode",
                            on_click=self.toggle_dark_mode,
                        )
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
                    if self._time_timer:
                        self._time_timer.cancel()

                    self._time_timer = ui.timer(1.0, lambda: self.update_time())

    def create_main_layout(self):
        """Create the main application layout"""
        ui.page_title("CVD Tracker - Simple Monitor")

        # Setup global styles using shared theme
        setup_global_styles()

        # Header
        self.create_header()  # Instantiate shared UI sections
        self.webcam_stream = WebcamStreamElement(
            self.settings,
            available_resolutions=self.supported_camera_modes,
            available_devices=[],
            callbacks={
                "update_sensitivity": self.update_sensitivity,
                "update_fps": self.update_fps,
                "update_resolution": self.update_resolution,
                "update_rotation": self.update_rotation,
                "update_brightness": self.update_brightness,
                "update_contrast": self.update_contrast,
                "update_saturation": self.update_saturation,
                "update_hue": self.update_hue,
                "update_sharpness": self.update_sharpness,
                "update_gain": self.update_gain,
                "update_gamma": self.update_gamma,
                "update_backlight_comp": self.update_backlight_comp,
                "update_white_balance_manual": self.update_white_balance_manual,
                "update_exposure_manual": self.update_exposure_manual,
                "set_roi": self.set_roi,
                "apply_uvc_settings": self.apply_uvc_settings,
                "reset_uvc_defaults": self.reset_uvc_defaults,
                "show_camera_settings": self.show_camera_settings_context,
                "camera_toggle": self.toggle_camera,
                "scan_cameras": self.scan_cameras,
                "select_camera": self.select_camera,
            },
            on_camera_status_change=self.update_camera_status,
        )
        self.motion_section = MotionStatusSection(
            self.settings,
            controller_manager=self.controller_manager,
            update_callback=self.update_motion_status,
        )
        self.experiment_section = ExperimentManagementSection(
            self.settings,
            callbacks={"toggle_experiment": self.toggle_experiment},
        )
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
                # populate initial recent experiment list
                self.experiment_section.load_recent_experiments()

            # Email Alerts (bottom-right) - New Alert System
            with ui.element("div").style("grid-area: alerts;") as self.alerts_container:
                self._create_enhanced_alerts_section()
            # Event handlers - placeholder implementations

        # Ensure webcam widget reflects current camera state on page load
        if self.camera_active:
            self.update_camera_status(True)
        if self.motion_detected:
            self.update_motion_status(True)

    def update_time(self):
        """Update the time display in header"""
        self.time_label.text = datetime.now().strftime("%H:%M:%S")

    def update_camera_status(self, active: bool):
        """Update camera icon color based on active state."""
        self.camera_active = active
        if hasattr(self, "camera_status_icon"):
            if active:
                self.camera_status_icon.classes(
                    add="text-green-300", remove="text-gray-400"
                )
            else:
                self.camera_status_icon.classes(
                    add="text-gray-400", remove="text-green-300"
                )

        # Synchronise webcam stream widget if it exists
        ws = getattr(self, "webcam_stream", None)
        if ws and getattr(ws, "video_element", None):
            start_btn = getattr(ws, "start_camera_btn", None)
            if active:
                ws.video_element.set_source("/video_feed")
                if start_btn:
                    start_btn.set_text("Pause Video")
                    start_btn.set_icon("pause")
                    start_btn.props("color=negative")
                ws.camera_active = True
            else:
                ws.video_element.set_source("")
                if start_btn:
                    start_btn.set_text("Play Video")
                    start_btn.set_icon("play_arrow")
                    start_btn.props("color=positive")
                ws.camera_active = False

    def update_motion_status(self, detected: bool) -> None:
        """Update motion icon and state based on detection status."""
        self.motion_detected = detected
        if detected:
            self._last_motion_time = datetime.now()
        if hasattr(self, "motion_status_icon"):
            self.motion_status_icon.name = (
                "motion_photos_on" if detected else "motion_photos_off"
            )
            if detected:
                self.motion_status_icon.classes(
                    add="text-orange-300", remove="text-gray-400"
                )
            else:
                self.motion_status_icon.classes(
                    add="text-gray-400", remove="text-orange-300"
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

    # Context menu handlers
    def show_camera_settings_context(self):
        """Show camera settings from context menu"""
        if self.webcam_stream:
            self.webcam_stream.show_camera_settings()

    def start_recording_context(self):
        """Start or stop recording from context menu"""
        if self.webcam_stream:
            self.webcam_stream.toggle_recording()

    def take_snapshot(self):
        """Trigger snapshot on the webcam element."""
        if self.webcam_stream:
            self.webcam_stream.take_snapshot()

    def adjust_roi(self):
        """Open ROI adjustment dialog on the webcam element."""
        if self.webcam_stream:
            self.webcam_stream.adjust_roi()

    # Main event handlers - placeholder implementations
    async def toggle_camera(self) -> bool:
        """Toggle streaming of the camera feed without affecting capture."""

        ws = getattr(self, "webcam_stream", None)
        streaming = not self.camera_active
        success = True

        if streaming:
            try:
                if self.camera_controller is not None:
                    started = await self.camera_controller.start()
                    if started is False:
                        raise RuntimeError("camera start returned False")
                if self.motion_controller is not None:
                    await self.motion_controller.start()
            except Exception:
                notify_later("Failed to start camera", type="negative")
                streaming = False
                success = False
        else:
            try:
                if self.camera_controller is not None:
                    await self.camera_controller.stop()
                if self.motion_controller is not None:
                    await self.motion_controller.stop()
            except Exception:
                notify_later("Failed to stop camera", type="negative")
                streaming = True
                success = False

        # Update internal state and header icon
        self.update_camera_status(streaming)

        # Update play/pause button on the webcam widget
        if ws and getattr(ws, "start_camera_btn", None):
            btn = getattr(ws, "start_camera_btn")
            if streaming:
                btn.set_icon("pause")
                btn.set_text("Pause Video")
            else:
                btn.set_icon("play_arrow")
                btn.set_text("Play Video")

        return success

    def update_sensitivity(self, e):
        """Update motion detection sensitivity"""
        try:
            value = int(getattr(e, "value", e))
        except ValueError:
            notify_later("Invalid sensitivity value", type="warning")
            return

        self.settings["sensitivity"] = value
        if self.motion_controller:
            # ``motion_threshold_percentage`` expects a value in the same
            # 0-100 range as provided by the UI widgets

            self.motion_controller.motion_threshold_percentage = value
        if hasattr(self, "webcam_stream"):
            self.webcam_stream.sensitivity_number.value = value
            self.webcam_stream.sensitivity_slider.value = value
        if hasattr(self, "motion_section"):
            self.motion_section.update_threshold_label(value)
        notify_later(f"Sensitivity set to {value}%", type="positive")

    def _set_camera_params(
        self,
        *,
        width: int | None = None,
        height: int | None = None,
        fps: int | None = None,
        rotation: int | None = None,
    ) -> None:
        """Apply camera parameters to all available controllers."""

        for controller in (self.camera_controller, self.motion_controller):
            if controller is None:
                continue
            if width is not None:
                controller.width = width
            if height is not None:
                controller.height = height
            if fps is not None:
                controller.fps = fps
            if rotation is not None:
                controller.rotation = rotation

    def update_fps(self, e):
        """Update camera FPS setting"""
        try:
            value = int(getattr(e, "value", e))
        except ValueError:
            notify_later("Invalid FPS value", type="warning")
            return

        self.settings["fps"] = value
        self._set_camera_params(fps=value)
        if hasattr(self, "webcam_stream"):
            self.webcam_stream.fps_select.value = value
        notify_later(f"FPS set to {value}", type="positive")

    def update_resolution(self, e):
        """Update camera resolution setting"""
        res = getattr(e, "value", e)
        try:
            dims = res.split()[0]
            width_str, height_str = dims.split("x")
            width = int(width_str)
            height = int(height_str)
        except ValueError:
            notify_later("Invalid resolution value", type="warning")
            return

        self.settings["resolution"] = res
        if width and height:
            self._set_camera_params(width=width, height=height)
        if hasattr(self, "webcam_stream"):
            self.webcam_stream.resolution_select.value = res
            if hasattr(self.webcam_stream, "update_video_aspect"):
                self.webcam_stream.update_video_aspect(width, height)
        notify_later(f"Resolution set to {res}", type="positive")

    def update_rotation(self, e):
        """Update camera rotation setting."""
        try:
            value = int(getattr(e, "value", e)) % 360
        except ValueError:
            notify_later("Invalid rotation value", type="warning")
            return
        if value not in {0, 90, 180, 270}:
            value = ((value + 45) // 90 * 90) % 360

        old_rotation = self.settings.get("rotation", 0)
        if value == old_rotation:
            if hasattr(self, "webcam_stream") and hasattr(
                self.webcam_stream, "rotation_select"
            ):
                self.webcam_stream.rotation_select.value = value
            return

        self.settings["rotation"] = value
        self._set_camera_params(rotation=value)

        # Swap video container dimensions when switching between portrait and
        # landscape orientations
        if hasattr(self, "webcam_stream") and hasattr(
            self.webcam_stream, "video_container"
        ):
            old_portrait = old_rotation in {90, 270}
            new_portrait = value in {90, 270}
            if old_portrait != new_portrait:
                try:
                    self.webcam_stream.swap_video_container_dimensions()
                except Exception:
                    pass

        # Transform existing ROI to maintain orientation
        if self.settings.get("roi_enabled") and hasattr(self, "webcam_stream"):
            width = None
            height = None
            if (
                self.camera_controller
                and self.camera_controller.width
                and self.camera_controller.height
            ):
                width = self.camera_controller.width
                height = self.camera_controller.height
            elif (
                self.motion_controller
                and self.motion_controller.width
                and self.motion_controller.height
            ):
                width = self.motion_controller.width
                height = self.motion_controller.height
            if width is None or height is None:
                try:
                    dims = self.settings.get("resolution", "").split()[0]
                    width, height = map(int, dims.split("x"))
                except Exception:
                    width = height = None

            if width and height:
                roi = (
                    self.webcam_stream.roi_x,
                    self.webcam_stream.roi_y,
                    self.webcam_stream.roi_width,
                    self.webcam_stream.roi_height,
                )
                roi = rotate_roi(roi, old_rotation, value, width, height)
                roi = clamp_roi(
                    roi,
                    width if value in {0, 180} else height,
                    height if value in {0, 180} else width,
                )
                x, y, w, h = roi
                self.webcam_stream.roi_x = x
                self.webcam_stream.roi_y = y
                self.webcam_stream.roi_width = w
                self.webcam_stream.roi_height = h
                if self.motion_controller:
                    self.motion_controller.roi_x = x
                    self.motion_controller.roi_y = y
                    self.motion_controller.roi_width = w
                    self.motion_controller.roi_height = h
                self.settings.update(
                    {"roi_x": x, "roi_y": y, "roi_width": w, "roi_height": h}
                )

        if hasattr(self, "webcam_stream") and hasattr(
            self.webcam_stream, "rotation_select"
        ):
            self.webcam_stream.rotation_select.value = value

        notify_later(f"Rotation set to {value}°", type="positive")

    # ------------------------------------------------------------------
    # UVC property update callbacks
    # ------------------------------------------------------------------

    def _update_uvc_setting(self, name: str, value: Any) -> None:
        """Helper to store a UVC value and schedule application."""
        self.settings[name] = value
        asyncio.create_task(self.apply_uvc_settings())

    def update_brightness(self, e):
        value = getattr(e, "value", e)
        self._update_uvc_setting("brightness", value)

    def update_contrast(self, e):
        value = getattr(e, "value", e)
        self._update_uvc_setting("contrast", value)

    def update_saturation(self, e):
        value = getattr(e, "value", e)
        self._update_uvc_setting("saturation", value)

    def update_hue(self, e):
        value = getattr(e, "value", e)
        self._update_uvc_setting("hue", value)

    def update_sharpness(self, e):
        value = getattr(e, "value", e)
        self._update_uvc_setting("sharpness", value)

    def update_gain(self, e):
        value = getattr(e, "value", e)
        self._update_uvc_setting("gain", value)

    def update_gamma(self, e):
        value = getattr(e, "value", e)
        self._update_uvc_setting("gamma", value)

    def update_backlight_comp(self, e):
        value = getattr(e, "value", e)
        self._update_uvc_setting("backlight_compensation", value)

    def update_white_balance_manual(self, e):
        value = getattr(e, "value", e)
        self._update_uvc_setting("white_balance", value)

    def update_exposure_manual(self, e):
        value = getattr(e, "value", e)
        self._update_uvc_setting("exposure", value)

    async def scan_cameras(self):
        """Scan for connected camera devices."""
        # The simplified implementation always exposes a single camera with
        # index ``0``. The UI elements for scanning and device selection remain
        # intact but will only ever show this one option.
        devices = ["0"]

        if self.webcam_stream:
            self.webcam_stream.update_devices(devices)

        notify_later("Found 1 camera", type="positive")

    def select_camera(self, e):
        """Select the active camera device.

        The new implementation ignores the provided value and always selects
        camera index ``0``. Existing controllers are updated accordingly so the
        rest of the application continues to operate as before.
        """

        index = 0
        self.settings["device_index"] = index
        if self.camera_controller:
            self.camera_controller.device_index = index
        if self.motion_controller:
            self.motion_controller.device_index = index
        notify_later("Camera device set to 0", type="positive")

    def set_roi(self):
        """Set region of interest"""
        if not hasattr(self, "webcam_stream"):
            return
        enabled = self.webcam_stream.roi_checkbox.value
        self.settings["roi_enabled"] = enabled
        if self.motion_controller:
            if not enabled:
                self.motion_controller.roi_x = 0
                self.motion_controller.roi_y = 0
                self.motion_controller.roi_width = None
                self.motion_controller.roi_height = None
            else:
                self.motion_controller.roi_x = self.webcam_stream.roi_x
                self.motion_controller.roi_y = self.webcam_stream.roi_y
                self.motion_controller.roi_width = self.webcam_stream.roi_width
                self.motion_controller.roi_height = self.webcam_stream.roi_height
                self.settings.update(
                    {
                        "roi_x": self.webcam_stream.roi_x,
                        "roi_y": self.webcam_stream.roi_y,
                        "roi_width": self.webcam_stream.roi_width,
                        "roi_height": self.webcam_stream.roi_height,
                    }
                )
        self.webcam_stream.refresh_roi_overlay()
        if hasattr(self, "motion_section"):
            self.motion_section.update_roi_status_label(
                enabled,
                self.webcam_stream.roi_x,
                self.webcam_stream.roi_y,
                self.webcam_stream.roi_width,
                self.webcam_stream.roi_height,
            )
        notify_later("ROI updated", type="positive")

    async def apply_uvc_settings(self):
        """Apply UVC camera settings"""
        if not hasattr(self, "webcam_stream"):
            return
        settings = {
            "brightness": self.webcam_stream.brightness_number.value,
            "contrast": self.webcam_stream.contrast_number.value,
            "saturation": self.webcam_stream.saturation_number.value,
            "hue": self.webcam_stream.hue_number.value,
            "sharpness": self.webcam_stream.sharpness_number.value,
            "gain": self.webcam_stream.gain_number.value,
            "gamma": self.webcam_stream.gamma_number.value,
            "backlight_compensation": self.webcam_stream.backlight_comp_number.value,
            "white_balance_auto": self.webcam_stream.wb_auto_checkbox.value,
            "white_balance": self.webcam_stream.wb_manual_number.value,
            "exposure_auto": self.webcam_stream.exposure_auto_checkbox.value,
            "exposure": self.webcam_stream.exposure_manual_number.value,
        }
        self.settings.update(settings)
        # Apply UVC settings asynchronously using controller helpers
        tasks = []
        if self.camera_controller is not None:
            tasks.append(
                asyncio.create_task(self.camera_controller.apply_uvc_settings(settings))
            )
        if self.motion_controller is not None:
            tasks.append(
                asyncio.create_task(self.motion_controller.apply_uvc_settings(settings))
            )
        if tasks:
            results = await asyncio.gather(*tasks, return_exceptions=True)
            for res in results:
                if isinstance(res, Exception):
                    error("apply_uvc_failed", exc_info=res)
        notify_later("UVC settings applied", type="positive")

    async def reset_uvc_defaults(self):
        """Reset all UVC controls to their default values."""
        if not hasattr(self, "webcam_stream") or not self.webcam_stream:
            return

        defaults = UVC_DEFAULTS.copy()

        ws = self.webcam_stream

        ws.brightness_number.value = defaults["brightness"]
        ws.brightness_slider.value = defaults["brightness"]
        ws.contrast_number.value = defaults["contrast"]
        ws.contrast_slider.value = defaults["contrast"]
        ws.saturation_number.value = defaults["saturation"]
        ws.saturation_slider.value = defaults["saturation"]
        ws.hue_number.value = defaults["hue"]
        ws.hue_slider.value = defaults["hue"]
        ws.sharpness_number.value = defaults["sharpness"]
        ws.sharpness_slider.value = defaults["sharpness"]
        ws.gain_number.value = defaults["gain"]
        ws.gain_slider.value = defaults["gain"]
        ws.gamma_number.value = defaults["gamma"]
        ws.gamma_slider.value = defaults["gamma"]
        ws.backlight_comp_number.value = defaults["backlight_compensation"]
        ws.backlight_comp_slider.value = defaults["backlight_compensation"]
        ws.wb_auto_checkbox.value = defaults["white_balance_auto"]
        ws.wb_manual_number.value = defaults["white_balance"]
        ws.wb_manual_slider.value = defaults["white_balance"]
        ws.exposure_auto_checkbox.value = defaults["exposure_auto"]
        ws.exposure_manual_number.value = defaults["exposure"]
        ws.exposure_manual_slider.value = defaults["exposure"]

        ws.toggle_white_balance_auto(defaults["white_balance_auto"])
        ws.toggle_exposure_auto(defaults["exposure_auto"])

        self.settings.update(defaults)

        tasks = []
        if self.camera_controller:
            tasks.append(
                asyncio.create_task(self.camera_controller.apply_uvc_settings(defaults))
            )

        if self.motion_controller:
            tasks.append(
                asyncio.create_task(self.motion_controller.apply_uvc_settings(defaults))
            )

        if tasks:
            results = await asyncio.gather(*tasks, return_exceptions=True)
            for res in results:
                if isinstance(res, Exception):
                    error("apply_uvc_failed", exc_info=res)

        notify_later("UVC settings reset to defaults", type="positive")

    def toggle_alerts(self, value):
        """Enable or disable alerts based on checkbox value."""
        value = getattr(value, "value", value)
        self.alerts_enabled = bool(value)
        self._update_alerts_status()

    async def send_test_alert(self):
        """Send a test email alert"""
        await self._send_test_to_all_configs()

    def show_alert_history(self):
        """Show alert history dialog"""
        self._show_alert_history()

    async def toggle_experiment(self):
        """Toggle experiment running state"""

        if not self.experiment_running:
            name = self.experiment_section.experiment_name_input.value
            duration = self.experiment_section.experiment_duration_input.value
            if duration:
                try:
                    self._experiment_duration = int(duration)
                except ValueError:
                    notify_later("Invalid duration value", type="warning")
                    return
            else:
                self._experiment_duration = None

            # Instantiate ExperimentConfig using positional args to satisfy Pylance
            config = ExperimentConfig(
                name,
                "",
                self._experiment_duration,
            )
            exp_id = self.experiment_manager.create_experiment(config)
            success = await self.experiment_manager.start_experiment(exp_id)
            if not success:
                notify_later("Failed to start experiment", type="negative")
                return

            self._current_experiment_id = exp_id
            self.experiment_running = True
            self._experiment_start = datetime.now()
            self.experiment_section.start_experiment_btn.disable()
            self.experiment_section.stop_experiment_btn.enable()
            self.experiment_section.experiment_icon.classes("text-green-600")
            self.experiment_section.experiment_status_label.text = "Experiment running"
            self.experiment_section.experiment_name_label.text = f"Name: {name}"
            dur_text = (
                f"Duration: {self._experiment_duration} min"
                if self._experiment_duration
                else "Duration: unlimited"
            )
            self.experiment_section.experiment_duration_label.text = dur_text
            self.experiment_section.experiment_elapsed_label.text = "Elapsed: 0s"
            self.experiment_section.experiment_progress.value = 0.0
            self.experiment_section.experiment_details.set_visibility(True)
            if self._experiment_timer:
                self._experiment_timer.cancel()
            self._experiment_timer = ui.timer(1.0, self._update_experiment_status)
            notify_later(f'Started experiment "{name}"', type="positive")
        else:
            if self.experiment_manager.get_current_state() not in (
                ExperimentState.RUNNING,
                ExperimentState.PAUSED,
            ):
                # Experiment already stopped
                self.experiment_running = False
                self._current_experiment_id = None
                self.experiment_section.start_experiment_btn.enable()
                self.experiment_section.stop_experiment_btn.disable()
                self.experiment_section.experiment_icon.classes("text-gray-500")
                self.experiment_section.experiment_status_label.text = (
                    "No experiment running"
                )
                self.experiment_section.experiment_details.set_visibility(False)
                if self._experiment_timer:
                    self._experiment_timer.cancel()
                    self._experiment_timer = None
                self.experiment_section.load_recent_experiments()
                return

            success = await self.experiment_manager.stop_experiment()
            if not success:
                notify_later("Failed to stop experiment", type="negative")
                return

            self.experiment_running = False
            self._current_experiment_id = None
            self.experiment_section.start_experiment_btn.enable()
            self.experiment_section.stop_experiment_btn.disable()
            self.experiment_section.experiment_icon.classes("text-gray-500")
            self.experiment_section.experiment_status_label.text = (
                "No experiment running"
            )
            self.experiment_section.experiment_details.set_visibility(False)
            if self._experiment_timer:
                self._experiment_timer.cancel()
                self._experiment_timer = None
            # update recent experiments display
            self.experiment_section.load_recent_experiments()
            notify_later("Experiment stopped", type="info")

    def _update_experiment_status(self) -> None:
        """Update elapsed time and progress display while running"""
        if not self.experiment_running or not self._experiment_start:
            return

        elapsed = (datetime.now() - self._experiment_start).total_seconds()
        self.experiment_section.experiment_elapsed_label.text = (
            f"Elapsed: {int(elapsed)}s"
        )

        if self._experiment_duration:
            total = self._experiment_duration * 60
            progress = min(elapsed / total, 1.0)
            self.experiment_section.experiment_progress.value = progress
            if elapsed >= total:
                asyncio.create_task(self.toggle_experiment())

    def _update_alerts_status(self):
        """Update the alerts_enabled status based on current configurations."""
        if not getattr(self, "_alert_configs_from_disk", True):
            # Demo configurations should not enable alerts by default
            self.alerts_enabled = False
        else:
            # Check if any alert configuration has active alert types
            self.alerts_enabled = any(
                any(
                    settings.get("enabled", False)
                    for settings in config.get("settings", {}).values()
                )
                for config in self.alert_configurations
            )

        if hasattr(self, "alert_status_icon"):
            cls = "text-yellow-300" if self.alerts_enabled else "text-gray-400"
            self.alert_status_icon.classes(cls)

    def _on_alert_config_changed(self) -> None:
        """Handle alert configuration updates from the status display."""
        if hasattr(self, "alert_overview_container"):
            self.alert_overview_container.clear()
            with self.alert_overview_container:
                self.alert_display.create_alert_overview()
        if hasattr(self, "alerts_container"):
            self.alerts_container.clear()
            with self.alerts_container:
                self._create_enhanced_alerts_section()
        self._update_alerts_status()

    def show_alert_setup_wizard(self):
        """Show the email alert setup wizard in a dialog"""

        def _on_save(config: Dict[str, Any]):
            self.alert_configurations.append(config)
            self.alert_display.alert_configurations = self.alert_configurations
            save_alert_configs(self.alert_configurations, service=self.config_service)
            self._on_alert_config_changed()
            self._update_alerts_status()
            service = self.email_alert_service
            if service and config.get("emails"):
                service.recipient = config["emails"][0]

        with ui.dialog() as dialog, ui.card().classes("w-full max-w-4xl"):
            create_email_alert_wizard(
                on_save=_on_save, service=self.email_alert_service
            )
            with ui.row().classes("w-full justify-end mt-4"):
                ui.button("Close", on_click=dialog.close).props("flat")

        dialog.open()

    def show_alert_management(self):
        """Show the alert management interface in a dialog"""
        with ui.dialog() as dialog, ui.card().classes("w-full max-w-6xl"):
            ui.label("Email Alert Management").classes("text-xl font-bold mb-4")

            with ui.column() as self.alert_overview_container:
                self.alert_display.create_alert_overview()

            with ui.row().classes("w-full justify-end mt-4"):
                ui.button("Close", on_click=dialog.close).props("flat")
        dialog.open()

    def _create_enhanced_alerts_section(self):
        """Create the enhanced email alerts section using the new alert system"""
        with ui.card().classes("w-full h-full"):
            with ui.card_section():
                # Header with action buttons
                with ui.row().classes("w-full items-center justify-between mb-4"):
                    ui.label("Email Alerts").classes("text-lg font-semibold")

                    with ui.row().classes("gap-2"):
                        ui.button(
                            "Configure",
                            icon="settings",
                            on_click=self.show_alert_setup_wizard,
                        ).props("size=sm color=primary")

                        ui.button(
                            "Manage",
                            icon="list",
                            on_click=self.show_alert_management,
                        ).props("size=sm color=secondary")

                        ui.button(
                            "Alert History",
                            icon="history",
                            on_click=self.show_alert_history,
                        ).props("size=sm color=secondary")

                        ui.button(
                            "Test Alert",
                            icon="send",
                            on_click=self.send_test_alert,
                        ).props("size=sm color=warning")

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
                        status_text = "Active"
                    else:
                        ui.icon("warning").classes("text-orange-600 text-2xl")
                        status_text = "Inactive"

                    with ui.column().classes("gap-1"):
                        ui.label(f"Status: {status_text}").classes("font-medium")
                        ui.label(
                            f"{active_configs} of {total_configs} configurations active"
                        ).classes(
                            "text-sm text-gray-600"
                        )  # Quick summary of active configurations
                if active_configs > 0:
                    ui.separator().classes("my-3")
                    ui.label("Active Configurations:").classes(
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
                                            f"{email_count} recipient(s)", color="blue"
                                        ).props("dense")

    async def _send_test_to_all_configs(self):
        """Send test alerts to all active configurations"""
        active_configs = [
            cfg
            for cfg in self.alert_configurations
            if any(
                settings.get("enabled", False)
                for settings in cfg.get("settings", {}).values()
            )
        ]

        if not active_configs:
            notify_later("No active alert configurations available", type="warning")
            return

        service = self.email_alert_service
        if service is None:
            notify_later("EmailAlertService unavailable", type="warning")
            return

        frame_bytes = None
        if self.camera_controller is not None:
            output = self.camera_controller.get_output()
            frame = None
            if isinstance(output, dict):
                frame = output.get("frame") or output.get("image")
            elif output is not None:
                frame = output
            if frame is not None:
                success, buf = await run_in_executor(cv2.imencode, ".jpg", frame)
                if success:
                    frame_bytes = buf.tobytes()

        motion_detected = False
        if self.motion_controller is not None:
            m_out = self.motion_controller.get_output()
            if isinstance(m_out, dict):
                motion_detected = bool(m_out.get("motion_detected", False))
            elif m_out is not None:
                motion_detected = bool(getattr(m_out, "motion_detected", False))

        status_text = (
            "Motion detected: Yes" if motion_detected else "Motion detected: No"
        )

        async def _send(recipient: str, subject: str, body: str) -> bool:
            return await run_network_io(
                service.send_alert,
                subject,
                body,
                recipient=recipient,
                status_text=status_text,
                image_attachment=frame_bytes,
            )

        tasks = [
            _send(
                email,
                f"Test Alert ({cfg.get('name', 'Alert')})",
                "This is a test of the email alert system.",
            )
            for cfg in active_configs
            for email in cfg.get("emails", [])
        ]

        if tasks:
            try:
                results = await gather_with_concurrency(
                    tasks, label="test_alerts", cancel_on_exception=False
                )
            except Exception as exc:  # noqa: BLE001
                error("test_alerts_failed", exc_info=exc)
                total_sent = 0
            else:
                total_sent = sum(1 for ok in results if ok)
        else:
            total_sent = 0

        notify_later(
            f"Test alerts sent to {total_sent} recipients across {len(active_configs)} configurations",
            type="positive" if total_sent else "warning",
        )

    async def _send_alerts_for_condition(self, condition: str, message: str) -> None:
        """Send an alert for the given condition to all matching configurations."""
        service = self.email_alert_service
        if service is None:
            return

        active_configs = [
            cfg
            for cfg in self.alert_configurations
            if cfg.get("settings", {}).get(condition, {}).get("enabled")
        ]

        tasks = [
            run_network_io(
                service.send_alert,
                f"Alert ({cfg.get('name', 'Alert')})",
                message,
                recipient=email,
            )
            for cfg in active_configs
            for email in cfg.get("emails", [])
        ]

        if tasks:
            await gather_with_concurrency(
                tasks, label="alerts", cancel_on_exception=False
            )

        if (
            hasattr(self.alert_display, "update_callback")
            and self.alert_display.update_callback
        ):
            self.alert_display.update_callback()

    def _show_alert_history(self):
        """Show alert history dialog"""
        with ui.dialog() as dialog, ui.card().classes("w-full max-w-4xl"):
            ui.label("Alert History").classes("text-xl font-bold mb-4")

            service = self.email_alert_service
            history_entries = service.get_history() if service else []

            with ui.column().classes("gap-3"):
                ui.label("Recently sent alerts:").classes("font-medium")

                for entry in history_entries:
                    with ui.card().classes("w-full p-3"):
                        with ui.row().classes("items-center justify-between"):
                            with ui.row().classes("items-center gap-3"):
                                ui.icon("schedule").classes("text-gray-600")
                                ui.label(str(entry.get("time", "Unknown"))).classes(
                                    "font-mono"
                                )
                                ui.label(str(entry.get("subject", "Alert"))).classes(
                                    "font-medium"
                                )
                                ui.label(
                                    str(entry.get("recipient", "Unknown"))
                                ).classes("text-gray-600")

                            ui.icon("email").classes("text-blue-600")

            with ui.row().classes("w-full justify-end mt-4"):
                ui.button("Close", on_click=dialog.close).props("flat")

        dialog.open()

    async def _evaluate_alert_conditions(self) -> None:
        """Check configured alert conditions and send alerts if triggered."""
        if not self.alerts_enabled:
            return

        now = datetime.now()

        # No motion detected for configured delay
        if not self.motion_detected:
            for cfg in self.alert_configurations:
                settings = cfg.get("settings", {}).get("no_motion_detected", {})
                if not settings.get("enabled"):
                    continue
                delay = int(settings.get("delay_minutes", 5))
                if now - self._last_motion_time >= timedelta(minutes=delay):
                    await self._send_alerts_for_condition(
                        "no_motion_detected",
                        f"No motion detected for {delay} minute(s)",
                    )
                    break

        # Camera offline
        if (
            self.camera_controller is None
            or self.camera_controller.status != ControllerStatus.RUNNING
        ):
            await self._send_alerts_for_condition(
                "camera_offline",
                "Camera is offline",
            )

    async def _alert_check_loop(self) -> None:
        """Periodically evaluate alert conditions."""
        while True:
            try:
                await asyncio.sleep(60)
                await self._evaluate_alert_conditions()
            except asyncio.CancelledError:
                break
            except Exception as exc:  # pragma: no cover - logging only
                error("alert_check_failed", exc_info=exc)

    async def _processing_loop(self) -> None:
        """Continuously process controller data."""
        while True:
            try:
                interval_ms = self.config_service.get(
                    "controller_manager.processing_interval_ms", int, 30
                )
                interval = max(0.001, interval_ms / 1000.0)
                await asyncio.sleep(interval)
                await self.controller_manager.process_data({})
            except asyncio.CancelledError:
                break
            except Exception as exc:
                error("Processing loop error", exc_info=exc)
                await asyncio.sleep(0.1)

    async def _motion_detection_loop(self) -> None:
        """Periodically poll motion detection results."""
        while True:
            try:
                await asyncio.sleep(0.1)
                detected = False
                if self.motion_controller is not None:
                    output = self.motion_controller.get_output()
                    if isinstance(output, dict):
                        detected = bool(output.get("motion_detected", False))
                    elif output is not None:
                        detected = bool(getattr(output, "motion_detected", False))
                self.update_motion_status(detected)
            except asyncio.CancelledError:
                break
            except Exception as exc:
                error("motion_detection_loop_error", exc_info=exc)
                await asyncio.sleep(0.1)

    def _on_experiment_state_change(
        self, old_state: ExperimentState, new_state: ExperimentState
    ) -> None:
        """Synchronize UI when an experiment stops automatically."""

        if not self.experiment_running:
            return

        if new_state == ExperimentState.COMPLETED:
            asyncio.create_task(
                self._send_alerts_for_condition(
                    "experiment_complete_alert", "Experiment completed"
                )
            )

        if new_state in {
            ExperimentState.COMPLETED,
            ExperimentState.CANCELLED,
            ExperimentState.FAILED,
            ExperimentState.IDLE,
        }:
            self.experiment_running = False
            self._current_experiment_id = None
            if self._experiment_timer:
                self._experiment_timer.cancel()
                self._experiment_timer = None

            exp_section = getattr(self, "experiment_section", None)
            if exp_section is not None:
                exp_section.start_experiment_btn.enable()
                exp_section.stop_experiment_btn.disable()
                exp_section.experiment_icon.classes("text-gray-500")
                exp_section.experiment_status_label.text = "No experiment running"
                exp_section.experiment_details.set_visibility(False)
                exp_section.load_recent_experiments()
            notify_later("Experiment stopped", type="info")

    def register_components(self) -> None:
        """Register NiceGUI pages"""

        @ui.page("/")
        def index() -> None:
            self.create_main_layout()

        @ui.page("/video_feed")
        async def video_feed(request: Request):
            first_connection = self._video_feed_connections == 0
            self._video_feed_connections += 1

            if first_connection:
                if self.camera_controller is None:
                    self.camera_controller = cast(
                        Optional[CameraCaptureController],
                        self.controller_manager.get_controller("camera_capture"),
                    )

                if (
                    self.camera_controller is not None
                    and self.camera_controller.status != ControllerStatus.RUNNING
                ):
                    try:
                        started = await self.camera_controller.start()
                    except Exception as exc:  # pragma: no cover - defensive
                        self._video_feed_connections -= 1
                        error("camera_start_failed", exc_info=exc)
                        self.update_camera_status(False)
                        return JSONResponse(
                            {"detail": "Failed to start video feed"},
                            status_code=500,
                        )
                    if not started:
                        self._video_feed_connections -= 1
                        error("camera_start_failed")
                        self.update_camera_status(False)
                        return JSONResponse(
                            {"detail": "Failed to start video feed"},
                            status_code=500,
                        )
                    self.update_camera_status(True)

            async def frame_source() -> Optional[np.ndarray]:
                frame = None
                if self.camera_controller is not None:
                    output = self.camera_controller.get_output()
                    if isinstance(output, dict):
                        frame = output.get("frame") or output.get("image")
                    elif output is not None:
                        frame = output
                return frame

            try:
                stream_gen = generate_mjpeg_stream(
                    frame_source,
                    fps_cap=self.settings.get("fps_cap", FPS_CAP),
                    request=request,
                )
            except Exception as exc:  # pragma: no cover
                self._video_feed_connections -= 1
                error("generate_mjpeg_stream failed", exc_info=exc)
                if self._video_feed_connections == 0:
                    self.update_camera_status(False)
                return JSONResponse(
                    {"detail": "Failed to start video feed"}, status_code=500
                )

            async def gen():
                try:
                    async for chunk in stream_gen:
                        yield chunk
                finally:
                    self._video_feed_connections -= 1
                    if self._video_feed_connections == 0:
                        if (
                            self.camera_controller is not None
                            and self.camera_controller.status
                            == ControllerStatus.RUNNING
                        ):
                            try:
                                await self.camera_controller.stop()
                                await self.camera_controller.cleanup()
                            except Exception as exc:  # pragma: no cover - defensive
                                error("camera_stop_failed", exc_info=exc)
                            self.camera_controller = None
                        self.update_camera_status(False)

            return StreamingResponse(
                gen(),
                media_type="multipart/x-mixed-replace; boundary=frame",
            )

    async def startup(self) -> None:
        """Start controllers and processing loop"""
        install_signal_handlers(self.experiment_manager._task_manager)
        try:
            self.supported_camera_modes = await probe_camera_modes()
        except Exception:
            self.supported_camera_modes = []

        if getattr(self, "webcam_stream", None):
            self.webcam_stream.available_resolutions = self.supported_camera_modes
            self.webcam_stream.update_resolutions(self.supported_camera_modes)
            await self.scan_cameras()

        if self.camera_controller is not None:
            accessible = await self.camera_controller.test_camera_access()
            if not accessible:
                ui.notify("Camera access failed", type="warning")
                warning("Camera access test failed")
                return

        success = await self.controller_manager.start_all_controllers()

        if success:
            self._processing_task = asyncio.create_task(self._processing_loop())
            self._alert_task = asyncio.create_task(self._alert_check_loop())
            self._motion_task = asyncio.create_task(self._motion_detection_loop())

            if (
                self.camera_controller is not None
                and self.camera_controller.status == ControllerStatus.RUNNING
            ):
                # Camera capture runs immediately for motion detection. The
                # video stream remains disabled until toggled by the user.
                self.camera_active = False
                self.update_camera_status(False)
            else:
                warning("Camera controller failed to start")
        else:
            ui.notify("Some controllers failed to start", type="warning")
            error("Failed to start controllers")

    async def shutdown(self) -> None:
        """Shutdown controllers and cleanup"""
        if self._processing_task:
            self._processing_task.cancel()
            with contextlib.suppress(Exception):
                await self._processing_task
            self._processing_task = None
        if self._alert_task:
            self._alert_task.cancel()
            with contextlib.suppress(Exception):
                await self._alert_task
            self._alert_task = None
        if self._motion_task:
            self._motion_task.cancel()
            with contextlib.suppress(Exception):
                await self._motion_task
            self._motion_task = None
        if self._experiment_timer:
            try:
                self._experiment_timer.cancel()
            except Exception:
                pass
            self._experiment_timer = None
        if self._time_timer:
            try:
                self._time_timer.cancel()
            except Exception:
                pass
            self._time_timer = None
        await self.controller_manager.stop_all_controllers()
        if self.motion_section:
            self.motion_section.cleanup()

    def run(self, host: str = "localhost", port: int = 8080):
        """Run the simple GUI application."""

        self.register_components()

        @app.on_startup
        async def _startup() -> None:  # pragma: no cover - event hook
            await self.startup()

        @app.on_shutdown
        async def _shutdown() -> None:  # pragma: no cover - event hook
            await self.shutdown()

        info(f"Starting Simple CVD GUI on http://{host}:{port}")

        ui.run(
            host="0.0.0.0",
            port=8080,
            title="CVD Tracker - Simple",
            favicon="https://www.tuhh.de/favicon.ico",
            dark=False,
            show=True,
        )


# Entry point
def main() -> None:
    """Delegate to the project-wide entry point."""
    from main import main as entry_point

    entry_point()


# The check for "__mp_main__" allows compatibility with multiprocessing on Windows,
# where the module name is set to "__mp_main__" in subprocesses.
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
#    - "Configure" button opens the four-step setup wizard
#    - "Manage" button opens the full alert overview
#    - Quick status display shows active configurations
#    - Header alert icon reflects the current alert status
#
# 4. Demo Data:
#    - 3 sample configurations are loaded by default
#    - Includes active and inactive configurations for testing
#    - Email addresses are partially anonymized in the display
#
# Usage:

#   python src/cvd/gui/alt_application.py
# or
#   python -m gui.alt_application

# The application uses the configuration in ``src/cvd/config/simple_config.json``.
# The email alert section will show in the bottom-right grid area.
# Click "Configure" to set up new alerts or "Manage" to view existing ones.
