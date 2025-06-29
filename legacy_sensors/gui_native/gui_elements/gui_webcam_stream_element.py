"""
Camera Stream Component for CVD Tracker

This component displays live camera feed with optional motion detection overlays.
It integrates with the motion detection controller to show the same processed frames.
"""

import time
from typing import Optional, Any, Dict
import threading  # for protecting frame access
import cv2
import numpy as np
from nicegui import ui

from cvd.gui.gui_tab_components.gui_tab_base_component import (
    BaseComponent,
    ComponentConfig,
)
from ...controllers.controller_manager import ControllerManager
from ...controllers.webcam import MotionDetectionController, MotionDetectionResult
from cvd.utils.log_service import warning, error, debug
from cvd.utils import log_service


class CameraStreamComponent(BaseComponent):
    """Component for displaying live camera stream with motion detection overlays."""

    def __init__(
        self,
        controller_manager: ControllerManager,
        controller_id: Optional[str] = None,
        update_interval: float = 1 / 30,
        max_width: int = 640,
        max_height: int = 480,
        component_id: str = "camera_stream",
        resolution: Optional[tuple[int, int]] = None,
        overlay_options: Optional[Dict[str, Any]] = None,
        stream_path: str = "/video_feed",
    ):
        """
        Initialize camera stream component.

        Args:
            controller_manager: Controller manager instance
            controller_id: ID of the motion detection controller to display
            update_interval: Update interval in seconds (default: ~30 FPS)
            max_width: Maximum display width in pixels
            max_height: Maximum display height in pixels
            component_id: Unique identifier for this component
            stream_path: Endpoint path for the MJPEG stream
        """
        config = ComponentConfig(component_id, "Camera Stream", "w-full")
        super().__init__(config)

        self.controller_manager = controller_manager
        self.controller_id = controller_id
        self.update_interval = update_interval
        self.stream_path = stream_path
        if resolution is not None:
            try:
                self.max_width, self.max_height = int(resolution[0]), int(resolution[1])
            except Exception as e:
                log_service.error(f"Invalid resolution {resolution}: {e}")
                self.max_width = max_width
                self.max_height = max_height
        else:
            self.max_width = max_width
            self.max_height = max_height

        # Component state
        self.is_streaming = False
        self.show_motion_overlay = True
        self.show_bounding_boxes = True
        self.show_motion_mask = False
        self.show_frame_diff = False
        self.overlay_opacity = 0.3

        if overlay_options:
            self.show_motion_overlay = bool(overlay_options.get("motion_overlay", True))
            self.show_bounding_boxes = bool(overlay_options.get("bounding_boxes", True))
            self.show_motion_mask = bool(overlay_options.get("motion_mask", False))
            self.show_frame_diff = bool(overlay_options.get("frame_diff", False))
            try:
                self.overlay_opacity = float(
                    overlay_options.get("overlay_opacity", 0.3)
                )
            except (TypeError, ValueError):
                self.overlay_opacity = 0.3

        # UI elements
        self.image_element = None
        self.status_label = None
        self.fps_label = None
        self.timer = None

        # Performance tracking
        self.frame_count = 0
        self.fps_counter = 0
        self.last_fps_time = None
        # Track the last resize scale (uniform)
        self._last_scale = 1.0
        # Latest frame for MJPEG streaming
        self._latest_frame: Optional[np.ndarray] = None
        # Lock to protect latest frame access
        self._frame_lock = threading.Lock()

    def render(self) -> ui.element:
        """Render the camera stream component."""
        with ui.card().classes("w-full") as container:
            # Header with title and controls
            with ui.row().classes("w-full justify-between items-center mb-4"):
                ui.label("Camera Stream").classes("text-lg font-semibold")

                with ui.row().classes("gap-2"):
                    # Stream control buttons
                    ui.button(icon="play_arrow", on_click=self.start_streaming).props(
                        "size=sm"
                    ).props("flat round").tooltip("Start streaming")
                    ui.button(icon="stop", on_click=self.stop_streaming).props(
                        "size=sm"
                    ).props("flat round").tooltip("Stop streaming")
                    ui.button(icon="pause", on_click=self.pause_streaming).props(
                        "size=sm"
                    ).props("flat round").tooltip("Pause streaming")

            # Status and FPS info
            with ui.row().classes("w-full justify-between items-center mb-2"):
                self.status_label = ui.label("Stopped").classes("text-sm text-gray-600")
                self.fps_label = ui.label("FPS: --").classes("text-sm text-gray-600")

            # Controls for overlays
            with ui.expansion("Display Options").classes("w-full mb-4"):
                with ui.column().classes("gap-2"):
                    ui.checkbox(
                        "Motion Overlay",
                        value=self.show_motion_overlay,
                        on_change=lambda e: setattr(
                            self, "show_motion_overlay", e.value
                        ),
                    )
                    ui.checkbox(
                        "Bounding Boxes",
                        value=self.show_bounding_boxes,
                        on_change=lambda e: setattr(
                            self, "show_bounding_boxes", e.value
                        ),
                    )
                    ui.checkbox(
                        "Motion Mask",
                        value=self.show_motion_mask,
                        on_change=lambda e: setattr(self, "show_motion_mask", e.value),
                    )
                    ui.checkbox(
                        "Frame Difference",
                        value=self.show_frame_diff,
                        on_change=lambda e: setattr(self, "show_frame_diff", e.value),
                    )

                    ui.slider(
                        min=0.1,
                        max=1.0,
                        value=self.overlay_opacity,
                        step=0.1,
                        on_change=lambda e: setattr(self, "overlay_opacity", e.value),
                    ).props('label="Overlay Opacity"')

            # Image display area
            with ui.column().classes("w-full items-center"):
                # Display MJPEG feed from configured stream path
                self.image_element = (
                    ui.image(self.stream_path)
                    .classes("border rounded")
                    .props('alt="Webcam stream"')
                )

                # Initialize placeholder frame
                self._set_placeholder_image()

        return container

    def start_streaming(self):
        """Start the camera stream."""
        if not self.is_streaming:
            self.is_streaming = True
            self.frame_count = 0
            self.fps_counter = 0
            self.last_fps_time = time.time()

            # Create timer for periodic updates only when a UI context is available
            self.timer = None
            if ui.context.slot_stack and self.image_element is not None:
                self.timer = ui.timer(self.update_interval, self._update_frame)

            if self.status_label:
                self.status_label.text = "Starting..."
                self.status_label.classes("text-blue-600")

    def stop_streaming(self):
        """Stop the camera stream."""
        if self.is_streaming:
            self.is_streaming = False

            if self.timer:
                self.timer.cancel()
                self.timer = None

            if self.status_label:
                self.status_label.text = "Stopped"
                self.status_label.classes("text-gray-600")

            # Reset to placeholder
            self._set_placeholder_image()

    def pause_streaming(self):
        """Pause/unpause the camera stream."""
        if self.timer:
            if self.timer.active:
                self.timer.deactivate()
                if self.status_label:
                    self.status_label.text = "Paused"
                    self.status_label.classes("text-orange-600")
            else:
                self.timer.activate()
                if self.status_label:
                    self.status_label.text = "Streaming"
                    self.status_label.classes("text-green-600")

    def _update_frame(self) -> None:
        """Update the displayed frame with latest camera data."""
        try:
            controller = self._get_motion_detection_controller()
            if not controller:
                self._handle_no_controller()
                return

            data = self._get_latest_frame_data(controller)
            if data is None:
                self._handle_no_frame()
                return

            self._render_frame(data)

        except cv2.error as exc:
            error(f"OpenCV error updating camera frame: {exc}")
            if self.status_label:
                self.status_label.text = "OpenCV Error"
                self.status_label.classes("text-red-600")
        except Exception as exc:  # unexpected errors
            error(f"Unexpected error updating camera frame: {exc}")
            if self.status_label:
                self.status_label.text = f"Error: {str(exc)[:30]}..."
                self.status_label.classes("text-red-600")

    def _render_frame(self, frame_data: MotionDetectionResult) -> None:
        """Render a processed frame to the UI."""
        display_frame = self._prepare_display_frame(frame_data)
        if display_frame is None:
            return
        self._update_image_display(display_frame)
        self._update_fps_counter()
        if self.status_label:
            self.status_label.text = "Streaming"
            self.status_label.classes("text-green-600")

    def _get_motion_detection_controller(self) -> Optional[MotionDetectionController]:
        """Get the configured motion detection controller instance."""
        try:
            if self.controller_id:
                ctrl = self.controller_manager.get_controller(self.controller_id)
                if isinstance(ctrl, MotionDetectionController):
                    return ctrl
            # Fallback to first available motion detection controller
            for cid in self.controller_manager.list_controllers():
                ctrl = self.controller_manager.get_controller(cid)
                if isinstance(ctrl, MotionDetectionController):
                    return ctrl
        except Exception as exc:
            # Any issues should be logged but not raise exceptions during UI update
            warning(f"Error retrieving motion controller: {exc}")
        return None

    def _get_latest_frame_data(
        self, motion_controller: MotionDetectionController
    ) -> Optional[MotionDetectionResult]:
        """Get the latest frame and motion detection data."""
        try:
            output = motion_controller.get_output()
            if output is None:
                return None

            if isinstance(output, MotionDetectionResult):
                result = output
                if result.frame is None:
                    camera_frame = self._get_camera_frame()
                    if camera_frame is None:
                        warning("No camera frame available")
                        return None
                    result.frame = camera_frame
                return result

            if isinstance(output, dict):
                camera_frame = self._get_camera_frame()
                if camera_frame is None:
                    warning("No camera frame available")
                    return None
                result = MotionDetectionResult(
                    motion_detected=output.get("motion_detected", False),
                    motion_area=output.get("motion_area", 0.0),
                    motion_percentage=output.get("motion_percentage", 0.0),
                    motion_regions=output.get("motion_regions", 0),
                    motion_center=output.get("motion_center"),
                    motion_bbox=output.get("motion_bbox"),
                    confidence=output.get("confidence", 0.0),
                    frame_delta=output.get("frame_diff"),
                    motion_mask=output.get("motion_mask"),
                    frame=camera_frame,
                )
                return result

            return None

        except (AttributeError, KeyError, TypeError) as exc:
            warning(f"Error getting frame data: {exc}")
            return None

    def _get_camera_frame(self) -> Optional[np.ndarray]:
        """Get current camera frame from available sources."""
        outputs = self.controller_manager.get_controller_outputs()

        # Try specific controller first if an ID is configured
        if self.controller_id and self.controller_id in outputs:
            output = outputs[self.controller_id]
            frame = self._extract_frame(output)
            if frame is not None:
                return frame

        # Fallback: search other controller outputs
        for output in outputs.values():
            frame = self._extract_frame(output)
            if frame is not None:
                return frame

        debug("No camera frame found in controller outputs")
        return None

    @staticmethod
    def _extract_frame(output: Any) -> Optional[np.ndarray]:
        """Extract a frame array from controller output."""
        if isinstance(output, MotionDetectionResult):
            if output.frame is not None:
                return output.frame
        elif isinstance(output, dict):
            frame_data = output.get("frame")
            if isinstance(frame_data, np.ndarray):
                return frame_data

            image_data = output.get("image")
            if isinstance(image_data, np.ndarray):
                return image_data
        elif isinstance(output, np.ndarray) and len(output.shape) == 3:
            return output
        return None

    def _prepare_display_frame(
        self, frame_data: MotionDetectionResult
    ) -> Optional[np.ndarray]:
        """Prepare frame for display with overlays and resizing."""
        try:
            frame = frame_data.frame
            if frame is None:
                return None

            frame = self._resize_frame(frame)

            if self.show_motion_overlay:
                frame = self._apply_motion_overlays(frame, frame_data)

            return frame

        except cv2.error as exc:
            error(f"OpenCV error preparing display frame: {exc}")
            return None
        except Exception as exc:  # catch unexpected issues
            error(f"Error preparing display frame: {exc}")
            return None

    def _resize_frame(self, frame: np.ndarray) -> np.ndarray:
        """Resize frame to fit display constraints."""
        h, w = frame.shape[:2]

        # Calculate scaling factor
        scale_w = self.max_width / w
        scale_h = self.max_height / h
        scale = min(scale_w, scale_h, 1.0)  # Don't upscale
        # Store scale for overlay coordinate adjustments
        self._last_scale = scale

        if scale < 1.0:
            new_w = int(w * scale)
            new_h = int(h * scale)
            try:
                frame = cv2.resize(frame, (new_w, new_h), interpolation=cv2.INTER_AREA)
            except cv2.error as exc:
                error(f"OpenCV resize error: {exc}")
            except Exception as exc:
                error(f"Error resizing frame: {exc}")

        return frame

    def _apply_motion_overlays(
        self, frame: np.ndarray, frame_data: MotionDetectionResult
    ) -> np.ndarray:
        """Apply motion detection overlays to the frame."""
        try:
            overlay_frame = frame.copy()
            # capture current display scale once to keep overlays consistent
            scale = self._last_scale

            # Show frame difference overlay (if available)
            if self.show_frame_diff and frame_data.frame_delta is not None:
                frame_diff = frame_data.frame_delta
                # resize diff without updating self._last_scale
                h_f, w_f = frame_diff.shape[:2]
                frame_diff_resized = cv2.resize(
                    frame_diff,
                    (int(w_f * scale), int(h_f * scale)),
                    interpolation=cv2.INTER_AREA,
                )
                if len(frame_diff_resized.shape) == 2:
                    frame_diff_colored = cv2.applyColorMap(
                        frame_diff_resized, cv2.COLORMAP_JET
                    )
                else:
                    frame_diff_colored = frame_diff_resized
                overlay_frame = cv2.addWeighted(
                    overlay_frame,
                    1 - self.overlay_opacity,
                    frame_diff_colored,
                    self.overlay_opacity,
                    0,
                )

            # Show motion mask overlay (if available)
            if self.show_motion_mask and frame_data.motion_mask is not None:
                motion_mask = frame_data.motion_mask
                # resize mask without updating self._last_scale
                h_m, w_m = motion_mask.shape[:2]
                motion_mask_resized = cv2.resize(
                    motion_mask,
                    (int(w_m * scale), int(h_m * scale)),
                    interpolation=cv2.INTER_AREA,
                )
                channels = (
                    1
                    if len(motion_mask_resized.shape) == 2
                    else motion_mask_resized.shape[2]
                )
                if channels == 1:
                    motion_mask_colored = cv2.applyColorMap(
                        motion_mask_resized, cv2.COLORMAP_HOT
                    )
                    overlay_frame = cv2.addWeighted(
                        overlay_frame,
                        1 - self.overlay_opacity,
                        motion_mask_colored,
                        self.overlay_opacity,
                        0,
                    )
                else:
                    overlay_frame = cv2.addWeighted(
                        overlay_frame,
                        1 - self.overlay_opacity,
                        motion_mask_resized,
                        self.overlay_opacity,
                        0,
                    )

            # Draw bounding box using stored resize scale
            if self.show_bounding_boxes and frame_data.motion_bbox:
                x, y, w_box, h_box = frame_data.motion_bbox
                roi_x = getattr(self, "roi_x", 0)
                roi_y = getattr(self, "roi_y", 0)
                # adjust coordinates using captured scale and ROI offset
                x_s, y_s = int((x - roi_x) * scale), int((y - roi_y) * scale)
                w_s, h_s = int(w_box * scale), int(h_box * scale)
                cv2.rectangle(
                    overlay_frame, (x_s, y_s), (x_s + w_s, y_s + h_s), (0, 255, 0), 2
                )

                # Add motion info text
                motion_text = f"Motion: {frame_data.motion_percentage:.1f}%"
                cv2.putText(
                    overlay_frame,
                    motion_text,
                    (x_s, y_s - 10),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.5,
                    (0, 255, 0),
                    1,
                )

            # Draw motion center
            if frame_data.motion_center:
                cx, cy = frame_data.motion_center
                roi_x = getattr(self, "roi_x", 0)
                roi_y = getattr(self, "roi_y", 0)
                # scale center point using captured scale and ROI offset
                cx_s, cy_s = int((cx - roi_x) * scale), int((cy - roi_y) * scale)
                cv2.circle(overlay_frame, (cx_s, cy_s), 5, (255, 0, 0), -1)

            # Draw confidence score and other info
            confidence = frame_data.confidence
            motion_detected = frame_data.motion_detected

            # Status text
            status_text = f"Motion: {'YES' if motion_detected else 'NO'}"
            cv2.putText(
                overlay_frame,
                status_text,
                (10, 30),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.7,
                (0, 255, 0) if motion_detected else (0, 0, 255),
                2,
            )

            # Confidence text
            if confidence > 0:
                cv2.putText(
                    overlay_frame,
                    f"Confidence: {confidence:.2f}",
                    (10, 60),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.6,
                    (255, 255, 255),
                    2,
                )

            # Motion regions count
            regions = frame_data.motion_regions
            if regions > 0:
                cv2.putText(
                    overlay_frame,
                    f"Regions: {regions}",
                    (10, 90),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.6,
                    (255, 255, 255),
                    2,
                )

            return overlay_frame

        except cv2.error as exc:
            error(f"OpenCV error applying motion overlays: {exc}")
            return frame
        except (ValueError, TypeError) as exc:
            error(f"Error applying motion overlays: {exc}")
            return frame

    def _update_image_display(self, frame: np.ndarray):
        """
        Store the latest frame for MJPEG streaming.
        The GUI image element pointing to ``self.stream_path`` pulls this frame via the streaming endpoint.
        """
        # Protect latest frame update
        with self._frame_lock:
            # store a copy to avoid external modifications
            self._latest_frame = frame.copy()

    def _update_fps_counter(self):
        """Update FPS counter."""
        self.fps_counter += 1
        current_time = time.time()

        if self.last_fps_time is None:
            self.last_fps_time = current_time

        time_diff = current_time - self.last_fps_time
        if time_diff >= 1.0:  # Update every second
            fps = self.fps_counter / time_diff
            if self.fps_label:
                self.fps_label.text = f"FPS: {fps:.1f}"

            self.fps_counter = 0
            self.last_fps_time = current_time

    def get_latest_frame(self) -> Optional[np.ndarray]:
        """Return the most recent processed frame."""
        # Protect latest frame read
        with self._frame_lock:
            return None if self._latest_frame is None else self._latest_frame.copy()

    def _handle_no_controller(self):
        """Handle case when motion detection controller is not available."""
        if self.status_label:
            self.status_label.text = "No Motion Controller"
            self.status_label.classes("text-orange-600")
        warning("Motion detection controller not available")

    def _handle_no_frame(self):
        """Handle case when no frame data is available."""
        if self.status_label:
            self.status_label.text = "No Frame Data"
            self.status_label.classes("text-orange-600")
        debug("No frame data available")

    def _set_placeholder_image(self):
        """Set a placeholder image when no camera data is available."""
        try:
            # Create a simple placeholder image
            placeholder = np.zeros((240, 320, 3), dtype=np.uint8)
            placeholder.fill(64)  # Dark gray background

            # Add text
            cv2.putText(
                placeholder,
                "Camera Stream",
                (50, 120),
                cv2.FONT_HERSHEY_SIMPLEX,
                1,
                (255, 255, 255),
                2,
            )
            cv2.putText(
                placeholder,
                "Click Start to begin",
                (60, 160),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.6,
                (200, 200, 200),
                1,
            )

            self._update_image_display(placeholder)

        except cv2.error as exc:
            error(f"OpenCV error setting placeholder image: {exc}")
        except Exception as exc:
            error(f"Error setting placeholder image: {exc}")

    def cleanup(self):
        """Clean up resources."""
        self.stop_streaming()
        super().cleanup()

    def _update_element(self, data: Any) -> None:
        """Implementation-specific update logic (required by BaseComponent)."""
        # This could be used to update the stream with external data
        # For now, we handle updates through the timer mechanism
        pass


def create_camera_stream_component(
    controller_manager: ControllerManager,
    controller_id: Optional[str] = None,
    update_interval: float = 1 / 30,
    max_width: int = 640,
    max_height: int = 480,
    stream_path: str = "/video_feed",
) -> CameraStreamComponent:
    """
    Factory function to create a camera stream component.

    Args:
        controller_manager: Controller manager instance
        controller_id: Controller to source frames from
        update_interval: Update interval in seconds (default: ~30 FPS)
        max_width: Maximum display width in pixels
        max_height: Maximum display height in pixels

    Returns:
        CameraStreamComponent instance
    """
    return CameraStreamComponent(
        controller_manager=controller_manager,
        controller_id=controller_id,
        update_interval=update_interval,
        max_width=max_width,
        max_height=max_height,
        stream_path=stream_path,
    )
