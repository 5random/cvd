"""
Motion detection controller using OpenCV background subtraction.
"""

import cv2
import numpy as np
from PIL import Image
from typing import Dict, Any, Optional, Tuple, Deque
from collections import deque
from dataclasses import dataclass
import time
import math
import asyncio
import contextlib

from src.controllers.controller_base import (
    ImageController,
    ControllerResult,
    ControllerConfig,
    ControllerInput,
)
from src.utils.config_service import get_config_service
from src.utils.concurrency.process_pool import (
    ManagedProcessPool,
    ProcessPoolConfig,
    ProcessPoolType,
)
from src.utils.log_service import info, warning, error
from src.utils.concurrency.thread_pool import run_camera_io
from src.controllers.camera_utils import apply_uvc_settings
from .base_camera_capture import BaseCameraCapture


@dataclass
class MotionDetectionResult:
    """Result from motion detection"""

    motion_detected: bool
    motion_area: float  # Total area of motion
    motion_percentage: float  # Percentage of frame with motion
    motion_regions: int  # Number of motion regions
    motion_center: Optional[Tuple[int, int]]  # Center of motion
    motion_bbox: Optional[Tuple[int, int, int, int]]  # Bounding box (x, y, w, h)
    confidence: float  # Confidence score
    frame_delta: Optional[np.ndarray] = None  # Frame difference (for visualization)
    motion_mask: Optional[np.ndarray] = None  # Motion mask (for visualization)
    frame: Optional[np.ndarray] = None  # Original frame (for visualization)


def analyze_motion(
    mask: np.ndarray,
    frame: Optional[np.ndarray] = None,
    *,
    min_contour_area: int,
    roundness_enabled: bool,
    roundness_threshold: float,
    motion_threshold_percentage: float,
    confidence_threshold: float,
) -> MotionDetectionResult:
    """Analyze the motion mask to extract motion information"""
    # Find contours
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    # Filter contours by area and optional roundness
    valid_contours = []
    for c in contours:
        area = cv2.contourArea(c)
        if area < min_contour_area:
            continue
        if roundness_enabled:
            peri = cv2.arcLength(c, True)
            if peri > 0:
                circ = 4 * math.pi * area / (peri * peri)
                if circ < roundness_threshold:
                    continue
        valid_contours.append(c)

    # Calculate motion metrics
    total_motion_area = sum(cv2.contourArea(c) for c in valid_contours)
    frame_area = mask.shape[0] * mask.shape[1]
    motion_percentage = (total_motion_area / frame_area) * 100

    # Determine if motion is detected
    motion_detected = motion_percentage >= motion_threshold_percentage

    # Calculate motion center and bounding box
    motion_center = None
    motion_bbox = None

    if valid_contours:
        # Combine all contours
        all_points = np.vstack(valid_contours)

        # Calculate center
        M = cv2.moments(all_points)
        if M["m00"] != 0:
            motion_center = (int(M["m10"] / M["m00"]), int(M["m01"] / M["m00"]))

        # Calculate bounding box
        x, y, w, h = cv2.boundingRect(all_points)
        motion_bbox = (x, y, w, h)

    # Calculate confidence based on motion characteristics
    confidence = (
        min(motion_percentage / motion_threshold_percentage, 1.0)
        if motion_threshold_percentage > 0
        else 0.0
    )
    if confidence < confidence_threshold:
        motion_detected = False

    return MotionDetectionResult(
        motion_detected=motion_detected,
        motion_area=total_motion_area,
        motion_percentage=motion_percentage,
        motion_regions=len(valid_contours),
        motion_center=motion_center,
        motion_bbox=motion_bbox,
        confidence=confidence,
        motion_mask=mask,
        frame_delta=None,  # Could add frame differencing if needed
    )


class MotionDetectionController(BaseCameraCapture, ImageController):
    """Controller for detecting motion in camera images using background subtraction"""

    def __init__(self, controller_id: str, config: ControllerConfig):
        super().__init__(controller_id, config)
        # Create dedicated process pool for motion analysis (CPU-bound)
        self._motion_pool = ManagedProcessPool(
            ProcessPoolConfig(), pool_type=ProcessPoolType.CPU
        )

        # Parameters from config
        params = config.parameters
        # Camera parameters
        self.device_index = params.get("device_index", 0)
        self.webcam_id = params.get("cam_id")
        self.width = params.get("width")
        self.height = params.get("height")
        self.fps = params.get("fps")
        self.capture_backend = params.get("capture_backend")
        self.rotation = params.get("rotation", 0)
        self.uvc_settings = {}
        self.uvc_settings.update(params.get("uvc", {}))
        self.uvc_settings.update(params.get("uvc_settings", {}))

        if self.webcam_id:
            service = get_config_service()
            if service:
                cam_cfg = service.get_webcam_config(self.webcam_id)
                if cam_cfg:
                    self.device_index = cam_cfg.get("device_index", self.device_index)
                    res = cam_cfg.get("resolution")
                    if res and len(res) == 2:
                        self.width, self.height = res
                    self.fps = cam_cfg.get("fps", self.fps)
                    self.rotation = cam_cfg.get("rotation", self.rotation)
                    self.capture_backend = cam_cfg.get(
                        "capture_backend", self.capture_backend
                    )
                    self.uvc_settings.update(cam_cfg.get("uvc", {}))
                    self.uvc_settings.update(cam_cfg.get("uvc_settings", {}))
        self.algorithm = params.get("algorithm", "MOG2")  # MOG2 or KNN
        self.var_threshold = params.get("var_threshold", 16)
        self.dist2_threshold = params.get("dist2_threshold", 400.0)
        self.history = params.get("history", 500)
        self.detect_shadows = params.get("detect_shadows", True)
        self.learning_rate = params.get("learning_rate", 0.01)
        self.threshold = params.get("threshold", 25)
        self.min_contour_area = params.get("min_contour_area", 500)
        self.motion_threshold_percentage = params.get(
            "motion_threshold_percentage", 1.0
        )
        if self.motion_threshold_percentage <= 0:
            warning(
                "motion_threshold_percentage must be > 0, using default",
                controller_id=self.controller_id,
                value=self.motion_threshold_percentage,
            )
            self.motion_threshold_percentage = 1.0
        self.gaussian_blur_kernel = params.get("gaussian_blur_kernel", (5, 5))
        # Validate gaussian_blur_kernel
        if (
            not isinstance(self.gaussian_blur_kernel, (tuple, list))
            or len(self.gaussian_blur_kernel) != 2
            or any(
                not isinstance(k, int) or k <= 0 or k % 2 == 0
                for k in self.gaussian_blur_kernel
            )
        ):
            warning(
                "Invalid gaussian_blur_kernel, using default",
                controller_id=self.controller_id,
                value=self.gaussian_blur_kernel,
            )
            self.gaussian_blur_kernel = (5, 5)
        else:
            self.gaussian_blur_kernel = (
                int(self.gaussian_blur_kernel[0]),
                int(self.gaussian_blur_kernel[1]),
            )

        self.morphology_kernel_size = params.get("morphology_kernel_size", 5)
        # Validate morphology_kernel_size
        if (
            not isinstance(self.morphology_kernel_size, int)
            or self.morphology_kernel_size <= 0
        ):
            warning(
                "morphology_kernel_size must be > 0, using default",
                controller_id=self.controller_id,
                value=self.morphology_kernel_size,
            )
            self.morphology_kernel_size = 5
        self.confidence_threshold = params.get("confidence_threshold", 0.5)
        # New: roundness and multi-frame criteria from config
        self.roundness_enabled = params.get("roundness_enabled", False)
        self.roundness_threshold = params.get("roundness_threshold", 0.7)
        self.multi_frame_enabled = params.get("multi_frame_enabled", False)
        self.multi_frame_window = params.get("multi_frame_window", 30)
        if self.multi_frame_window < 1:
            warning(
                "multi_frame_window must be >= 1, using default",
                controller_id=self.controller_id,
                value=self.multi_frame_window,
            )
            self.multi_frame_window = 1
        self.multi_frame_threshold = params.get("multi_frame_threshold", 0.3)

        self.multi_frame_method = params.get("multi_frame_method", "threshold")
        self.multi_frame_decay = params.get("multi_frame_decay", 0.5)

        # Decayed confidence average for probability method
        self._multi_frame_avg: float = 0.0

        self.warmup_frames = params.get("warmup_frames", 0)
        self._warmup_counter = 0

        # Optional region of interest for motion analysis
        self._roi_x: int = 0
        self._roi_y: int = 0
        self._roi_width: Optional[int] = None
        self._roi_height: Optional[int] = None
        self.roi_x = params.get("roi_x", 0)
        self.roi_y = params.get("roi_y", 0)
        self.roi_width = params.get("roi_width")
        self.roi_height = params.get("roi_height")

        # Background subtractor
        self._bg_subtractor: Optional[cv2.BackgroundSubtractor] = None
        self._frame_count = 0
        self._last_frame: Optional[np.ndarray] = None
        self._frame_size: Optional[Tuple[int, int]] = None

        # Statistics
        self._max_history = params.get("max_history", 100)
        self._motion_history: Deque[dict[str, Any]] = deque(maxlen=self._max_history)
        self._motion_history_motion_count: int = 0
        self._recent_motion_flags: Deque[bool] = deque(maxlen=self.multi_frame_window)
        self._recent_motion_count: int = 0

        # Lock to protect shared state in async processing
        self._state_lock = asyncio.Lock()

    # ------------------------------------------------------------------
    # ROI properties

    @property
    def roi_x(self) -> int:
        return self._roi_x

    @roi_x.setter
    def roi_x(self, value: int) -> None:
        if getattr(self, "_roi_x", None) != value:
            self._frame_size = None
        self._roi_x = value

    @property
    def roi_y(self) -> int:
        return self._roi_y

    @roi_y.setter
    def roi_y(self, value: int) -> None:
        if getattr(self, "_roi_y", None) != value:
            self._frame_size = None
        self._roi_y = value

    @property
    def roi_width(self) -> Optional[int]:
        return self._roi_width

    @roi_width.setter
    def roi_width(self, value: Optional[int]) -> None:
        if getattr(self, "_roi_width", None) != value:
            self._frame_size = None
        self._roi_width = value

    @property
    def roi_height(self) -> Optional[int]:
        return self._roi_height

    @roi_height.setter
    def roi_height(self, value: Optional[int]) -> None:
        if getattr(self, "_roi_height", None) != value:
            self._frame_size = None
        self._roi_height = value

    async def initialize(self) -> bool:
        """Initialize the motion detection controller"""
        try:
            # Create background subtractor based on algorithm
            if self.algorithm == "MOG2":
                self._bg_subtractor = cv2.createBackgroundSubtractorMOG2(
                    detectShadows=self.detect_shadows,
                    varThreshold=self.var_threshold,
                    history=self.history,
                )
            elif self.algorithm == "KNN":
                self._bg_subtractor = cv2.createBackgroundSubtractorKNN(
                    detectShadows=self.detect_shadows,
                    dist2Threshold=self.dist2_threshold,
                    history=self.history,
                )
            else:
                error(
                    "Unsupported background subtraction algorithm",
                    controller_id=self.controller_id,
                    algorithm=self.algorithm,
                )
                return False

            info(
                f"Initialized motion detection controller with {self.algorithm} algorithm",
                controller_id=self.controller_id,
                algorithm=self.algorithm,
            )
            info(
                "Motion detection controller initialized",
                controller_id=self.controller_id,
                algorithm=self.algorithm,
            )
            return True

        except Exception as e:
            error(
                "Failed to initialize motion detection controller",
                controller_id=self.controller_id,
                algorithm=self.algorithm,
                error=str(e),
            )
            return False

    async def process_image(
        self, image_data: Any, metadata: Dict[str, Any]
    ) -> ControllerResult:
        """Process image for motion detection"""
        try:
            # Convert image data to OpenCV format
            frame = self._convert_to_cv_frame(image_data)
            if frame is None:
                return ControllerResult.error_result(
                    "Failed to convert image data to OpenCV format"
                )

            # Crop to region of interest if configured
            if self.roi_width is not None and self.roi_height is not None:
                if self.roi_width <= 0 or self.roi_height <= 0:
                    warning(
                        "Invalid ROI dimensions, skipping crop",
                        controller_id=self.controller_id,
                        roi_width=self.roi_width,
                        roi_height=self.roi_height,
                    )
                    self.roi_width = None
                    self.roi_height = None
                else:
                    x1 = max(0, int(self.roi_x))
                    y1 = max(0, int(self.roi_y))
                    x2 = min(frame.shape[1], x1 + int(self.roi_width))
                    y2 = min(frame.shape[0], y1 + int(self.roi_height))
                    if x2 > x1 and y2 > y1:
                        frame = frame[y1:y2, x1:x2]
                    else:
                        warning(
                            "ROI results in empty region, skipping crop",
                            controller_id=self.controller_id,
                            roi=(x1, y1, self.roi_width, self.roi_height),
                        )
                        self.roi_width = None
                        self.roi_height = None

            # Store frame size for calculations
            self._frame_size = (frame.shape[1], frame.shape[0])

            # Ensure background subtractor is initialized
            if self._bg_subtractor is None:
                initialized = await self.initialize()
                if not initialized:
                    return ControllerResult.error_result(
                        "Background subtractor not initialized"
                    )
            # Explicitly handle case where background subtractor is still None
            if self._bg_subtractor is None:
                error(
                    "Background subtractor not initialized",
                    controller_id=self.controller_id,
                    algorithm=self.algorithm,
                )
                return ControllerResult.error_result(
                    "Background subtractor not initialized after initialization"
                )

            # Apply background subtraction
            fg_mask = self._bg_subtractor.apply(frame, learningRate=self.learning_rate)

            # Post-process the mask
            processed_mask = self._post_process_mask(fg_mask)

            # Offload heavy analysis to dedicated process pool
            motion_result = await self._motion_pool.submit_async(
                analyze_motion,
                processed_mask,
                min_contour_area=self.min_contour_area,
                roundness_enabled=self.roundness_enabled,
                roundness_threshold=self.roundness_threshold,
                motion_threshold_percentage=self.motion_threshold_percentage,
                confidence_threshold=self.confidence_threshold,
            )

            # Adjust bbox and center to original frame coordinates when ROI is active
            if (
                self.roi_width is not None
                and self.roi_height is not None
                and (self.roi_x or self.roi_y)
            ):
                if motion_result.motion_bbox is not None:
                    x, y, w_box, h_box = motion_result.motion_bbox
                    motion_result.motion_bbox = (
                        x + int(self.roi_x),
                        y + int(self.roi_y),
                        w_box,
                        h_box,
                    )
                if motion_result.motion_center is not None:
                    cx, cy = motion_result.motion_center
                    motion_result.motion_center = (
                        cx + int(self.roi_x),
                        cy + int(self.roi_y),
                    )

            # Update shared state atomically
            async with self._state_lock:
                # Update raw detection history
                self._update_statistics(motion_result)
                # Robust multi-frame decision
                if self.multi_frame_enabled:
                    probability = motion_result.confidence
                    if self.multi_frame_method == "threshold":
                        if len(self._recent_motion_flags) >= self.multi_frame_window:
                            probability = (
                                self._recent_motion_count / self.multi_frame_window
                            )
                        if probability < self.multi_frame_threshold:
                            motion_result.motion_detected = False
                    elif self.multi_frame_method == "probability":
                        self._multi_frame_avg = (
                            self.multi_frame_decay * self._multi_frame_avg
                            + (1 - self.multi_frame_decay) * probability
                        )
                        motion_result.motion_detected = (
                            self._multi_frame_avg >= self.multi_frame_threshold
                        )

                # Attach frame and mask for optional visualization
                motion_result.frame = frame
                motion_result.motion_mask = processed_mask

                # Update frame count and last frame
                self._frame_count += 1
                self._last_frame = frame

            return ControllerResult.success_result(
                motion_result,
                metadata={
                    "controller_type": "motion_detection",
                    "frame_count": self._frame_count,
                    "timestamp": metadata.get("timestamp", time.time()),
                    "source_sensor": metadata.get("source_sensor"),
                    "algorithm": self.algorithm,
                    "frame_size": self._frame_size,
                },
            )
        except Exception as e:
            error(
                "Error in motion detection",
                controller_id=self.controller_id,
                algorithm=self.algorithm,
                error=str(e),
            )
            return ControllerResult.error_result(f"Motion detection error: {e}")

    def _convert_to_cv_frame(self, image_data: Any) -> Optional[np.ndarray]:
        """Convert various image data formats to an OpenCV BGR frame"""
        try:
            rgb_source = False

            if isinstance(image_data, np.ndarray):
                # Already an OpenCV frame (assumed BGR/BGRA)
                frame = image_data

            elif isinstance(image_data, bytes):
                # Raw image bytes decoded with OpenCV (already BGR)
                nparr = np.frombuffer(image_data, np.uint8)
                frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

            elif isinstance(image_data, Image.Image):
                # PIL images are in RGB order by default
                frame = np.array(image_data)
                rgb_source = True

            elif hasattr(image_data, "__array__"):
                # Generic array-like objects, orientation unknown
                frame = np.array(image_data)

            else:
                error(
                    "Unsupported image data type",
                    controller_id=self.controller_id,
                    algorithm=self.algorithm,
                    data_type=str(type(image_data)),
                )
                return None

            # Convert to BGR only when the source is known to be RGB
            if rgb_source and len(frame.shape) == 3:
                if frame.shape[2] == 3:
                    frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
                elif frame.shape[2] == 4:
                    frame = cv2.cvtColor(frame, cv2.COLOR_RGBA2BGR)

            return frame

        except Exception as e:
            error(
                "Error converting image data",
                controller_id=self.controller_id,
                algorithm=self.algorithm,
                error=str(e),
            )
            return None

    def _post_process_mask(self, fg_mask: np.ndarray) -> np.ndarray:
        """Post-process the foreground mask to reduce noise"""
        # Apply threshold
        _, thresh = cv2.threshold(fg_mask, self.threshold, 255, cv2.THRESH_BINARY)

        # Apply Gaussian blur to reduce noise
        blurred = cv2.GaussianBlur(thresh, self.gaussian_blur_kernel, 0)

        # Apply morphological operations to clean up the mask
        kernel = cv2.getStructuringElement(
            cv2.MORPH_ELLIPSE,
            (self.morphology_kernel_size, self.morphology_kernel_size),
        )

        # Remove noise with opening
        opened = cv2.morphologyEx(blurred, cv2.MORPH_OPEN, kernel)

        # Fill gaps with closing
        closed = cv2.morphologyEx(opened, cv2.MORPH_CLOSE, kernel)

        return closed

    def _motion_result_to_dict(self, result: MotionDetectionResult) -> Dict[str, Any]:
        """Convert MotionDetectionResult to dictionary for serialization"""
        return {
            "motion_detected": result.motion_detected,
            "motion_area": result.motion_area,
            "motion_percentage": result.motion_percentage,
            "motion_regions": result.motion_regions,
            "motion_center": result.motion_center,
            "motion_bbox": result.motion_bbox,
            "confidence": result.confidence,
            # Note: numpy arrays (motion_mask, frame_delta) are not included for serialization
            # They can be accessed separately if needed for visualization
        }

    def _update_statistics(self, result: MotionDetectionResult) -> None:
        """Update motion detection statistics"""
        oldest: Optional[dict[str, Any]] = None
        if len(self._motion_history) == self._motion_history.maxlen:
            oldest = self._motion_history[0]
        self._motion_history.append(
            {
                "timestamp": time.time(),
                "motion_detected": result.motion_detected,
                "motion_percentage": result.motion_percentage,
                "confidence": result.confidence,
            }
        )
        if result.motion_detected:
            self._motion_history_motion_count += 1
        if oldest and oldest.get("motion_detected"):
            self._motion_history_motion_count -= 1

        old_flag: Optional[bool] = None
        if len(self._recent_motion_flags) == self._recent_motion_flags.maxlen:
            old_flag = self._recent_motion_flags[0]
        self._recent_motion_flags.append(result.motion_detected)
        if result.motion_detected:
            self._recent_motion_count += 1
        if old_flag:
            if old_flag:
                self._recent_motion_count -= 1

    def get_motion_statistics(self) -> Dict[str, Any]:
        """Get motion detection statistics"""
        if not self._motion_history:
            return {}

        motion_frames = self._motion_history_motion_count
        detections = [h for h in self._motion_history if h["motion_detected"]]

        return {
            "total_frames": len(self._motion_history),
            "motion_frames": motion_frames,
            "motion_rate": motion_frames / len(self._motion_history),
            "avg_motion_percentage": (
                np.mean([h["motion_percentage"] for h in detections])
                if detections
                else 0
            ),
            "avg_confidence": (
                np.mean([h["confidence"] for h in detections]) if detections else 0
            ),
            "last_motion_time": (
                next(
                    (
                        h["timestamp"]
                        for h in reversed(self._motion_history)
                        if h["motion_detected"]
                    ),
                    None,
                )
            ),
        }

    async def cleanup(self) -> None:
        """Cleanup motion detection resources"""
        # Stop capture loop and release camera resources
        await self.stop_capture()
        await self.cleanup_capture()
        # Ensure no pending tasks remain before shutting down the process pool
        start_time = time.monotonic()
        while getattr(self._motion_pool, "_telemetry").active:
            await asyncio.sleep(0.05)
            if time.monotonic() - start_time > 5:
                warning(
                    "Timeout waiting for motion pool tasks to finish",
                    active=getattr(self._motion_pool, "_telemetry").active,
                )
                break
        self._motion_pool.shutdown(wait=True)

        self._bg_subtractor = None
        self._last_frame = None
        self._motion_history.clear()
        self._recent_motion_flags.clear()
        self._motion_history_motion_count = 0
        self._recent_motion_count = 0
        info(
            "Motion detection controller cleaned up",
            controller_id=self.controller_id,
        )

    async def start(self) -> bool:
        if not await super().start():
            return False
        self._warmup_counter = self.warmup_frames
        if not self.config.input_controllers:
            self.start_capture()
        else:
            info(
                "Using external capture controller, skipping internal loop",
                controller_id=self.controller_id,
            )
            self._capture_task = None
        return True

    async def stop(self) -> None:
        await self.stop_capture()
        await super().stop()

    async def on_capture_opened(self) -> None:
        self._bg_subtractor = None
        self._warmup_counter = self.warmup_frames

    async def handle_frame(self, frame: Any) -> None:
        if self._warmup_counter > 0:
            self._warmup_counter -= 1
            return
        result = await self.process_image(
            frame,
            {
                "source_sensor": self.webcam_id or "camera",
                "timestamp": time.time(),
            },
        )
        if result.success:
            self._output_cache[self.controller_id] = result.data

    async def process(self, input_data: ControllerInput) -> ControllerResult:
        output = self._output_cache.get(self.controller_id)
        if output is None:
            return ControllerResult.success_result(None)
        return ControllerResult.success_result(output)

    async def apply_uvc_settings(
        self, settings: Optional[dict[str, Any]] | None = None
    ) -> None:
        """Apply UVC settings to the capture device."""
        if settings:
            self.uvc_settings.update(settings)
        if self._capture is not None:
            await apply_uvc_settings(
                self._capture,
                self.uvc_settings if settings is None else settings,
                controller_id=self.controller_id,
            )
