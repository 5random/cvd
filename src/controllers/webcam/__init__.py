"""Webcam related controllers."""

from .camera_capture_controller import CameraCaptureController
from .motion_detection import (
    MotionDetectionController,
    MotionDetectionResult,
)

__all__ = [
    "CameraCaptureController",
    "MotionDetectionController",
    "MotionDetectionResult",
]
